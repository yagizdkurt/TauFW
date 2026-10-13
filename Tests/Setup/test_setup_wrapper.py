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
        shutil.copyfile(REPO / "setup.sh", self.original / "setup.sh")
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
source "$TEST_ORIGINAL/setup.sh"
[[ $PWD == "$TEST_INSTALLED" && $CMSSW_BASE == "$TEST_RELEASE" ]]
[[ $before_options == "$(set +o)" && $before_shopts == "$(shopt -p)" ]]
[[ $before_traps == "$(trap -p)" ]]
[[ $(type -t _taufw_setup_main || true) == '' ]]
source ./setup.sh
[[ $(wc -l < "$TEST_ROOT/runs") == 1 ]]
''')

    def test_explicit_install_and_options_forwarded(self):
        self.shell(r'''
source "$TEST_ORIGINAL/setup.sh" || exit
source ./setup.sh --install --jobs 7 --cmssw-dir "$TEST_RELEASE" || exit
source ./setup.sh --skip-htt || exit
[[ $(wc -l < "$TEST_ROOT/runs") == 3 ]]
''')
        self.assertEqual((self.root / "arguments").read_text().splitlines(),
                         ["", "--jobs", "7", "--cmssw-dir",
                          self.shell('printf "%s" "$TEST_RELEASE"').stdout, "--skip-htt"])

    def test_activation_summary_log_handoff_and_cleanup(self):
        result = self.shell(r'''
export LC_ALL=C NO_COLOR=1 TEST_LOG=true
export TMPDIR="$TEST_ROOT"
source "$TEST_ORIGINAL/setup.sh" || exit
[[ -z $(find "$TEST_ROOT" -maxdepth 1 -name 'TauFW-setup-result.*' -print) ]]
unset TEST_LOG
source ./setup.sh || exit
''')
        self.assertEqual(result.stdout.count("[OK] TauFW environment active"), 2)
        self.assertEqual(result.stdout.count("Installation log:"), 1)
        self.assertIn("source setup.sh --install", result.stdout)
        self.assertIn("Next session:", result.stdout)
        self.assertNotIn("\x1b[", result.stdout)
        self.assertNotIn("?", result.stdout)

    def test_grid_proxy_initialization_and_status_follow_activation(self):
        result = self.shell(r'''
export LC_ALL=C NO_COLOR=1
source "$TEST_ORIGINAL/setup.sh" || exit
''')
        self.assertEqual((self.root / "voms-commands").read_text().splitlines(),
                         ["init -voms cms", "info --all", "info --exists --valid 0:01"])
        self.assertIn("[OK] Grid proxy active", result.stdout)
        self.assertLess(result.stdout.index("TauFW environment active"),
                        result.stdout.index("CMS grid proxy:"))

    def test_grid_proxy_failure_keeps_environment_active(self):
        result = self.shell(r'''
export LC_ALL=C NO_COLOR=1 TEST_VOMS_STATUS=1
set -Eeu -o pipefail
source "$TEST_ORIGINAL/setup.sh"
[[ $PWD == "$TEST_INSTALLED" && $CMSSW_BASE == "$TEST_RELEASE" ]]
''')
        self.assertIn("Grid proxy initialization failed", result.stdout)
        self.assertIn("No valid grid proxy is active", result.stdout)
        self.assertNotIn("[OK] Grid proxy active", result.stdout)
        self.assertEqual((self.root / "voms-commands").read_text().splitlines(),
                         ["init -voms cms", "info --all", "info --exists --valid 0:01"])

    def test_help_and_execution_do_not_install(self):
        self.shell(r'''
source "$TEST_ORIGINAL/setup.sh" --help || exit
if bash "$TEST_ORIGINAL/setup.sh"; then exit 1; fi
[[ ! -e "$TEST_ROOT/runs" ]]
''')

    def test_failure_and_cancellation_return_status_without_activation(self):
        for status in (7, 130):
            with self.subTest(status=status):
                self.shell(f'''
export TEST_STATUS={status}
before=$PWD
if source "$TEST_ORIGINAL/setup.sh"; then exit 1; else status=$?; fi
[[ $status == {status} && $PWD == "$before" && -z ${{CMSSW_BASE:-}} ]]
[[ ! -e "$TEST_ORIGINAL/.git/taufw-setup-state" ]]
''')

    def test_copy_records_original_and_installed_locations(self):
        self.shell(r'''
export TEST_COPY=true
source "$TEST_ORIGINAL/setup.sh" || exit
source "$TEST_ORIGINAL/setup.sh" || exit
[[ $PWD == "$TEST_INSTALLED" && $(wc -l < "$TEST_ROOT/runs") == 1 ]]
cmp "$TEST_ORIGINAL/.git/taufw-setup-state" "$TEST_INSTALLED/.git/taufw-setup-state"
export TEST_STATUS=7
if source "$TEST_INSTALLED/setup.sh" --install; then exit 1; fi
if source "$TEST_ORIGINAL/setup.sh"; then exit 1; fi
[[ $(wc -l < "$TEST_ROOT/runs") == 3 ]]
''')

    def test_stale_record_reinstalls_and_failed_reinstall_invalidates(self):
        self.shell(r'''
source "$TEST_ORIGINAL/setup.sh" || exit
export TEST_ORIGINAL=$TEST_INSTALLED
printf 'stale' > .git/taufw-setup-state
source ./setup.sh || exit
[[ $(wc -l < "$TEST_ROOT/runs") == 2 ]]
export TEST_STATUS=7
if source ./setup.sh --install; then exit 1; fi
[[ ! -e .git/taufw-setup-state ]]
''')

    def test_pending_clean_marker_reinstalls(self):
        self.shell(r'''
source "$TEST_ORIGINAL/setup.sh" || exit
export TEST_ORIGINAL=$TEST_INSTALLED
touch "$TEST_RELEASE/.FastSetup-needs-clean"
# Mock verification has to remove the clean marker before reporting success.
sed -i '/repo_dir=$target/a rm -f -- "$cmssw_dir/.FastSetup-needs-clean"' Utilities/FastSetup.sh
source ./setup.sh || exit
[[ $(wc -l < "$TEST_ROOT/runs") == 2 ]]
''')

    def test_bad_result_and_activation_failure(self):
        self.shell(r'''
export TEST_BAD_RESULT=true
if source "$TEST_ORIGINAL/setup.sh"; then exit 1; fi
[[ -z ${CMSSW_BASE:-} ]]
''')
        self.shell(r'''
export TEST_ORIGINAL=$TEST_INSTALLED
source "$TEST_INSTALLED/setup.sh" || exit
printf 'scram() { return 1; }\n' > "$TEST_ROOT/cms.sh"
before_options=$(set +o)
if source ./setup.sh; then exit 1; fi
[[ $before_options == "$(set +o)" ]]
''')


if __name__ == "__main__":
    unittest.main()
