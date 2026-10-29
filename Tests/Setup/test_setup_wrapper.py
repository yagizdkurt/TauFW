"""Sourceable setup regressions with fake installation and CMS runtime."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from test_fastsetup import BASH, REPO, write_lf


@unittest.skipUnless(BASH, "Bash is unavailable")
class SetupWrapperTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix="TauFW setup ")
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.original = self.root / "original clone"
        (self.original / "Utilities").mkdir(parents=True)
        (self.original / ".git").mkdir()
        for package in ("PicoProducer", "Fitter"):
            (self.original / package).mkdir()
        shutil.copyfile(REPO / "taufw.sh", self.original / "taufw.sh")
        worker = (REPO / "Utilities/FastSetup.sh").read_text()
        publication = worker[worker.index("invalidate_setup_record() {"):
                             worker.index("selection_label() {")]
        write_lf(self.original / "Utilities/FastSetup.sh",
            "#!/usr/bin/env bash\nset -eu\n" + publication + r'''
cleanup_paths=()
if [[ ${1:-} == --help ]]; then echo 'worker help'; exit 0; fi
printf '%s\n' "$@" >> "$TEST_ROOT/arguments"
echo 'installer screen' >> "$TEST_ROOT/runs"
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
target=$TEST_INSTALLED
cmssw_dir=$TEST_RELEASE
cms_setup=$TEST_ROOT/cms.sh
SCRAM_ARCH=el9_amd64_gcc12
copied_from=
invalidate_setup_record
if [[ ${TEST_STATUS:-0} != 0 ]]; then exit "$TEST_STATUS"; fi
if [[ $repo_dir != "$target" ]]; then
  if [[ ${TEST_COPY:-false} == true ]]; then
    cp -R -- "$repo_dir" "$target"
    copied_from=$repo_dir
  else
    # Windows cannot rename a directory while Bash sources a file inside it.
    # Copy models the relocated checkout/result on Windows; Linux tests rename.
    if [[ $OSTYPE == msys* ]]; then cp -R -- "$repo_dir" "$target";
    else mv -- "$repo_dir" "$target"; fi
  fi
fi
repo_dir=$target
if [[ ${TEST_BAD_RESULT:-false} == true ]]; then
  printf 'broken' > "$FASTSETUP_RESULT_FILE"
else
  publish_setup_record
  if [[ ${TEST_LOG:-false} == true ]]; then
    printf '%s\n' "$TEST_ROOT/retained installation.log" > "$FASTSETUP_RESULT_FILE.log-path"
  fi
fi
''')
        write_lf(self.root / "cms.sh", r'''
set +u
set +o pipefail
shopt -s nullglob
scram() {
  [[ $* == 'runtime -sh' ]] || return 1
  printf 'runtime\n' >> "$TEST_ROOT/scram-calls"
  printf 'export CMSSW_VERSION=CMSSW_14_1_0_pre4; export CMSSW_BASE=%q\n' "$TEST_RELEASE"
}
voms-proxy-init() {
  printf 'init %s\n' "$*" >> "$TEST_ROOT/voms-commands"
  return "${TEST_VOMS_STATUS:-0}"
}
voms-proxy-info() {
  printf 'info %s\n' "$*" >> "$TEST_ROOT/voms-commands"
  return "${TEST_VOMS_STATUS:-0}"
}
''')

    def shell(self, body, expected=0):
        bootstrap = r'''
cd "$TEST_FIXTURE" || exit 1
export TEST_ROOT=$PWD
export TEST_ORIGINAL="$PWD/original clone"
export TEST_RELEASE="$PWD/CMSSW_14_1_0_pre4"
export TEST_INSTALLED="$TEST_RELEASE/src/TauFW"
mkdir -p "$TEST_RELEASE/.SCRAM/el9_amd64_gcc12" "$TEST_RELEASE/src"
python3() {
  if [[ $1 == -c ]]; then return "${TEST_IMPORT_STATUS:-0}"; fi
  if [[ $1 == "$TEST_INSTALLED/Framework/python/_internal/installer/setup_tools.py" && $2 == report ]]; then
    printf 'success\tComponents: fake\nwarning\tUser config: not reviewed\n'
    return 0
  fi
  [[ $1 == "$TEST_INSTALLED/Framework/scripts/taufw.py" ]] || return 1
  if [[ $# == 2 && $2 == --on-start && $PWD == "$TEST_INSTALLED" ]]; then
    printf 'menu\n' >> "$TEST_ROOT/launches"
  else
    shift
    printf '%s\n' "$*" >> "$TEST_ROOT/commands"
  fi
}
'''
        result = subprocess.run(
            [BASH, "-c", bootstrap + body],
            env=dict(os.environ, TEST_FIXTURE=str(self.root)),
            text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_first_install_move_and_later_activation_preserve_shell(self):
        self.shell(r'''
set -Eeu -o pipefail
trap 'echo unexpected-error >&2' ERR
before_options=$(set +o)
before_shopts=$(shopt -p)
before_traps=$(trap -p)
source "$TEST_ORIGINAL/taufw.sh"
[[ $PWD == "$TEST_INSTALLED" && $CMSSW_BASE == "$TEST_RELEASE" ]] || exit 1
[[ $before_options == "$(set +o)" && $before_shopts == "$(shopt -p)" ]] || exit 1
[[ $before_traps == "$(trap -p)" ]] || exit 1
[[ $(type -t _taufw_setup_main || true) == '' ]] || exit 1
source ./taufw.sh
[[ $(wc -l < "$TEST_ROOT/runs") == 1 ]] || exit 1
[[ $(wc -l < "$TEST_ROOT/launches") == 2 ]] || exit 1
''')

    def test_explicit_install_and_options_forwarded(self):
        self.shell(r'''
source "$TEST_ORIGINAL/taufw.sh" || exit
source ./taufw.sh --install --jobs 7 --cmssw-dir "$TEST_RELEASE" || exit
source ./taufw.sh --skip-htt || exit
[[ $(wc -l < "$TEST_ROOT/runs") == 3 ]] || exit 1
''')
        self.assertEqual((self.root / "arguments").read_text().splitlines(),
                         ["", "--jobs", "7", "--cmssw-dir",
                          self.shell('printf "%s" "$TEST_RELEASE"').stdout, "--skip-htt"])

    def test_activation_summary_log_handoff_and_cleanup(self):
        result = self.shell(r'''
export LC_ALL=C NO_COLOR=1 TEST_LOG=true
export TMPDIR="$TEST_ROOT"
source "$TEST_ORIGINAL/taufw.sh" || exit
[[ -z $(find "$TEST_ROOT" -maxdepth 1 -name 'TauFW-setup-result.*' -print) ]] || exit 1
unset TEST_LOG
source ./taufw.sh || exit
''')
        self.assertEqual(result.stdout.count("[OK] TauFW environment active"), 2)
        self.assertEqual(result.stdout.count("Installation log:"), 1)
        self.assertNotIn("Change installed components:", result.stdout)
        self.assertNotIn("source taufw.sh --install", result.stdout)
        self.assertNotIn("Next session:", result.stdout)
        self.assertNotIn("Working directory:", result.stdout)
        self.assertNotIn("CMSSW_14_1_0_pre4 |", result.stdout)
        self.assertNotIn("\x1b[", result.stdout)
        self.assertNotIn("?", result.stdout)

    def test_activation_opens_menu_without_prompting_for_grid_proxy(self):
        result = self.shell(r'''
export LC_ALL=C NO_COLOR=1 TEST_VOMS_STATUS=1
set -Eeu -o pipefail
source "$TEST_ORIGINAL/taufw.sh"
[[ $PWD == "$TEST_INSTALLED" && $CMSSW_BASE == "$TEST_RELEASE" ]] || exit 1
''')
        self.assertFalse((self.root / "voms-commands").exists())
        self.assertEqual((self.root / "launches").read_text().splitlines(), ["menu"])
        self.assertNotIn("grid certificate password", result.stdout)

    def test_activation_defines_the_taufw_command(self):
        """CL §53: after `source taufw.sh` the shell keeps `taufw` (exported to child shells) and $TAUFW_BASE, and
        nothing else of the script; taufw.sh asked the command line once with --on-start (the menu)."""
        self.shell(r'''
source "$TEST_ORIGINAL/taufw.sh" || exit
[[ $(type -t taufw) == function && $TAUFW_BASE == "$TEST_INSTALLED" ]] || exit 1
[[ -z $(compgen -A function _taufw_setup_ || true) ]] || exit 1
cd "$TEST_ROOT"
taufw plan "Analyses/my analysis"
taufw
export -f python3  # the stand-in of this test, for the child shell
bash -c 'taufw status run1' || exit
[[ $(cat "$TEST_ROOT/launches") == menu ]] || exit 1
''')
        self.assertEqual((self.root / "commands").read_text().splitlines(),
                         ["plan Analyses/my analysis", "", "status run1"])

    def test_help_and_execution_do_not_install(self):
        self.shell(r'''
source "$TEST_ORIGINAL/taufw.sh" --help || exit
if bash "$TEST_ORIGINAL/taufw.sh"; then exit 1; fi
[[ ! -e "$TEST_ROOT/runs" ]] || exit 1
''')

    def test_failure_and_cancellation_return_status_without_activation(self):
        for status in (7, 130):
            with self.subTest(status=status):
                self.shell(f'''
export TEST_STATUS={status}
before=$PWD
before_cmssw_base_set=${{CMSSW_BASE+x}}
before_cmssw_base=${{CMSSW_BASE-}}
if source "$TEST_ORIGINAL/taufw.sh"; then exit 1; else status=$?; fi
[[ $status == {status} && $PWD == "$before" ]] || exit 1
[[ ${{CMSSW_BASE+x}} == "$before_cmssw_base_set" && ${{CMSSW_BASE-}} == "$before_cmssw_base" ]] || exit 1
[[ ! -e "$TEST_ORIGINAL/.git/taufw-setup-state" ]] || exit 1
[[ ! -e "$TEST_ROOT/launches" ]] || exit 1
''')

    def test_copy_records_original_and_installed_locations(self):
        self.shell(r'''
export TEST_COPY=true
source "$TEST_ORIGINAL/taufw.sh" || exit
source "$TEST_ORIGINAL/taufw.sh" || exit
[[ $PWD == "$TEST_INSTALLED" && $(wc -l < "$TEST_ROOT/runs") == 1 ]] || exit 1
cmp "$TEST_ORIGINAL/.git/taufw-setup-state" "$TEST_INSTALLED/.git/taufw-setup-state"
export TEST_STATUS=7
if source "$TEST_INSTALLED/taufw.sh" --install; then exit 1; fi
if source "$TEST_ORIGINAL/taufw.sh"; then exit 1; fi
[[ $(wc -l < "$TEST_ROOT/runs") == 3 ]] || exit 1
''')

    def test_stale_record_reinstalls_and_failed_reinstall_invalidates(self):
        self.shell(r'''
source "$TEST_ORIGINAL/taufw.sh" || exit
export TEST_ORIGINAL=$TEST_INSTALLED
printf 'stale' > .git/taufw-setup-state
source ./taufw.sh || exit
[[ $(wc -l < "$TEST_ROOT/runs") == 2 ]] || exit 1
export TEST_STATUS=7
if source ./taufw.sh --install; then exit 1; fi
[[ ! -e .git/taufw-setup-state ]] || exit 1
''')

    def test_pending_clean_marker_reinstalls(self):
        self.shell(r'''
source "$TEST_ORIGINAL/taufw.sh" || exit
export TEST_ORIGINAL=$TEST_INSTALLED
touch "$TEST_RELEASE/.FastSetup-needs-clean"
# Mock verification has to remove the clean marker before reporting success.
sed -i '/repo_dir=$target/a rm -f -- "$cmssw_dir/.FastSetup-needs-clean"' Utilities/FastSetup.sh
source ./taufw.sh || exit
[[ $(wc -l < "$TEST_ROOT/runs") == 2 ]] || exit 1
''')

    def test_bad_result_and_activation_failure(self):
        self.shell(r'''
export TEST_BAD_RESULT=true
before_cmssw_base_set=${CMSSW_BASE+x}
before_cmssw_base=${CMSSW_BASE-}
if source "$TEST_ORIGINAL/taufw.sh"; then exit 1; fi
[[ ${CMSSW_BASE+x} == "$before_cmssw_base_set" && ${CMSSW_BASE-} == "$before_cmssw_base" ]] || exit 1
''')
        self.shell(r'''
export TEST_ORIGINAL=$TEST_INSTALLED
source "$TEST_INSTALLED/taufw.sh" || exit
printf 'scram() { return 1; }\n' > "$TEST_ROOT/cms.sh"
unset CMSSW_BASE CMSSW_VERSION  # a new terminal: the release is not active
before_options=$(set +o)
if source ./taufw.sh; then exit 1; fi
[[ $before_options == "$(set +o)" ]] || exit 1
''')

    def test_a_shell_with_the_release_active_is_not_activated_again(self):
        """CL §54: the second source in one shell runs no cmsenv (scram runtime) again, still enters the checkout
        and opens the menu; a new shell (no CMSSW_BASE) and an installation activate as before."""
        result = self.shell(r'''
export LC_ALL=C NO_COLOR=1
source "$TEST_ORIGINAL/taufw.sh" || exit
cd "$TEST_ROOT"
source "$TEST_INSTALLED/taufw.sh" || exit
[[ $PWD == "$TEST_INSTALLED" ]] || exit 1
[[ $(wc -l < "$TEST_ROOT/scram-calls") == 1 && $(wc -l < "$TEST_ROOT/launches") == 2 ]] || exit 1
unset CMSSW_BASE
source ./taufw.sh || exit
[[ $(wc -l < "$TEST_ROOT/scram-calls") == 2 ]] || exit 1
source ./taufw.sh --install || exit
[[ $(wc -l < "$TEST_ROOT/scram-calls") == 3 ]] || exit 1
''')
        self.assertEqual(result.stdout.count("[OK] TauFW environment active"), 4)

    def test_stale_pycache_folders_of_moved_packages_are_removed(self):
        """CL §54: in the python/ trees, a folder with nothing but __pycache__ goes (and its parent, if that leaves
        it empty); folders with any other file, an empty folder of the user, the python/ folders and everything
        outside the python/ trees stay."""
        result = self.shell(r'''
export LC_ALL=C NO_COLOR=1
source "$TEST_ORIGINAL/taufw.sh" || exit
cd "$TEST_INSTALLED"
mkdir -p Stray/Old/__pycache__
source ./taufw.sh || exit  # no python/ tree at all: nothing is searched, not even the current folder
[[ -d Stray/Old/__pycache__ ]] || exit 1
mkdir -p Pkg/python/Gone/__pycache__ Pkg/python/Outer/Inner/__pycache__ Pkg/python/Kept/__pycache__ \
         Pkg/python/Data/__pycache__ Pkg/python/Empty Other/python/__pycache__ Stray/Old/__pycache__
touch Pkg/python/Gone/__pycache__/a.pyc Pkg/python/Outer/Inner/__pycache__/b.pyc Pkg/python/Kept/mod.py \
      Pkg/python/Kept/__pycache__/mod.pyc Pkg/python/Data/table.json Stray/Old/__pycache__/c.pyc
cd "$TEST_ROOT"
source "$TEST_INSTALLED/taufw.sh" || exit
cd "$TEST_INSTALLED"
[[ ! -e Pkg/python/Gone && ! -e Pkg/python/Outer ]] || exit 1
[[ -f Pkg/python/Kept/mod.py && -d Pkg/python/Kept/__pycache__ && -f Pkg/python/Data/table.json ]] || exit 1
[[ -d Pkg/python/Empty && -d Other/python/__pycache__ && -d Stray/Old/__pycache__ ]] || exit 1
source ./taufw.sh || exit
''')
        self.assertEqual(result.stdout.count("[OK] Removed 3 stale __pycache__ folder(s) of moved packages"), 1)

    def test_check_changes_nothing_and_reports(self):
        """CL §54: source taufw.sh --check installs nothing, leaves the directory and the environment of the shell
        as they were, and fails only when TauFW cannot work."""
        result = self.shell(r'''
export LC_ALL=C NO_COLOR=1
if source "$TEST_ORIGINAL/taufw.sh" --check; then exit 1; fi
[[ ! -e "$TEST_ROOT/runs" ]] || exit 1
source "$TEST_ORIGINAL/taufw.sh" || exit
unset CMSSW_BASE CMSSW_VERSION
cd "$TEST_ROOT"
before=$(wc -l < "$TEST_ROOT/scram-calls")
source "$TEST_INSTALLED/taufw.sh" --check || exit
[[ $PWD == "$TEST_ROOT" && -z ${CMSSW_BASE:-} ]] || exit 1
[[ $(wc -l < "$TEST_ROOT/runs") == 1 && $(wc -l < "$TEST_ROOT/launches") == 1 ]] || exit 1
[[ $(wc -l < "$TEST_ROOT/scram-calls") == $((before + 1)) ]] || exit 1  # in a subshell
export TEST_IMPORT_STATUS=1
if source "$TEST_INSTALLED/taufw.sh" --check; then exit 1; fi
if source "$TEST_INSTALLED/taufw.sh" --check --install; then exit 1; fi
[[ $(wc -l < "$TEST_ROOT/runs") == 1 ]] || exit 1
''')
        self.assertIn("[FAIL] Installation: no valid installation record", result.stdout)
        self.assertIn("[!] CMSSW: not active in this shell", result.stdout)
        self.assertIn("[OK] TauFW: imports", result.stdout)
        self.assertIn("[OK] Components: fake", result.stdout)
        self.assertIn("[!] User config: not reviewed", result.stdout)
        self.assertIn("[!] Grid proxy: none or expired", result.stdout)
        self.assertIn("[FAIL] TauFW: import failed", result.stdout)
        self.assertIn("--check takes no other option", result.stderr)

    def test_status_marks_in_a_utf8_terminal(self):
        result = self.shell(r'''
export LC_ALL=C.UTF-8 NO_COLOR=1
source "$TEST_ORIGINAL/taufw.sh" || exit
''')
        self.assertIn("\u2713 TauFW environment active", result.stdout)

    def test_tab_completion(self):
        """CL §54: commands, the options of a command, recipe files and folders, and the choices of configs."""
        result = self.shell(r'''
source "$TEST_ORIGINAL/taufw.sh" || exit
complete -p taufw | grep -q _taufw_complete || exit 1
mkdir -p "$TEST_ROOT/recipes/sub" && cd "$TEST_ROOT/recipes" && touch a.yml b.json c.txt
complete_words() { COMP_WORDS=("$@"); COMP_CWORD=$(($# - 1)); _taufw_complete; printf '%s ' "${COMPREPLY[@]}"; echo; }
complete_words taufw pl
complete_words taufw advance --ta
complete_words taufw configs u
complete_words taufw check ""
complete_words taufw start --run-root ""
''')
        lines = result.stdout.splitlines()[-5:]
        self.assertEqual(lines[0].split(), ["plan"])
        self.assertEqual(lines[1].split(), ["--take-lock"])
        self.assertEqual(lines[2].split(), ["update"])
        self.assertEqual(sorted(lines[3].split()), ["a.yml", "b.json", "sub"])
        self.assertEqual(lines[4].split(), ["sub"])


if __name__ == "__main__":
    unittest.main()
