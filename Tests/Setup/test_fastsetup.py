"""Focused installer regressions; no network downloads or CMSSW builds."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
if BASH is None:
    git = shutil.which("git")
    candidate = Path(git).parent.parent / "bin" / "bash.exe" if git else None
    if candidate and candidate.is_file():
        BASH = str(candidate)


@unittest.skipUnless(BASH, "Bash is unavailable")
class FastSetupTests(unittest.TestCase):
    def run_script(self, body, *args, expected=0, directory=None):
        source = (REPO / "FastSetup.sh").read_text(encoding="utf-8")
        source = source.rsplit('main "$@"', 1)[0]
        if directory is None:
            fixture = tempfile.TemporaryDirectory()
            self.addCleanup(fixture.cleanup)
            directory = Path(fixture.name)
        script = directory / "setup.sh"
        # Git Bash can use the current Python executable for the real inline probes.
        source += '\npython3() { "$FASTSETUP_TEST_PYTHON" "$@"; }\n'
        script.write_text(source + body, encoding="utf-8", newline="\n")
        env = dict(os.environ, FASTSETUP_TEST_PYTHON=sys.executable,
                   MSYS="winsymlinks:sys")
        result = subprocess.run([BASH, str(script), *args], cwd=directory,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr, directory

    def run_setup(self, *args):
        # Replace external operations only; run the actual parser, selection,
        # pipeline dispatch, verification, and resume-argument construction.
        body = r"""
check_host() { :; }
locate_checkout() { repo_dir=/checkout; }
choose_release_area() { cmssw_dir=/release; }
preflight_install() { :; }
choose_scram_arch() { :; }
load_cms_software() { :; }
create_release() { :; }
activate_release() { CMSSW_RELEASE_BASE=/release; }
move_checkout() { :; }
install_nanoaodtools() { printf 'nano:%s\n' "$run2_jme"; }
install_tauidsfs() { printf 'install:tauidsfs\n'; }
install_htt_efficiencies() { printf 'install:htt\n'; }
install_combine() { printf 'install:combine\n'; }
build_release() { printf 'build\n'; }
python3() { printf 'verify:%s\n' "$2"; }
verify_python_modules() { printf 'modules:%s\n' "$@"; }
verify_htt() { printf 'verify:htt\n'; }
verify_combine() { printf 'verify:combine\n'; }
print_summary() { printf 'retry:%s\n' "${args[@]}"; }
main "$@"
"""
        return self.run_script(body, *args)[0]

    def test_default_nonterminal_selection_preserves_installations(self):
        output = self.run_setup()
        self.assertIn("install:tauidsfs", output)
        self.assertIn("install:htt", output)
        self.assertIn("install:combine", output)
        self.assertIn("nano:false", output)
        self.assertIn("TauPOG.TauIDSFs.TauIDSFTool:TauIDSFTool", output)
        self.assertIn("TauFW.Framework:Framework", output)
        self.assertIn("verify:htt", output)
        self.assertIn("verify:combine", output)
        self.assertIn("retry:--non-interactive", output)

    def test_skipped_components_do_not_install_or_verify(self):
        output = self.run_setup("--non-interactive", "--skip-tauidsfs", "--skip-htt", "--skip-combine", "--run2-jme")
        self.assertNotIn("install:", output)
        self.assertNotIn("TauPOG.TauIDSFs", output)
        self.assertNotIn("verify:htt", output)
        self.assertNotIn("verify:combine", output)
        self.assertIn("nano:true", output)
        self.assertIn("build", output)
        for flag in ("--skip-tauidsfs", "--skip-htt", "--skip-combine", "--run2-jme"):
            self.assertIn("retry:" + flag, output)

    def test_main_clone_with_linked_worktrees_is_rejected_before_move(self):
        output, directory = self.run_script(r'''
git init -q main
printf 'original\n' > main/README.md
git -C main add README.md
git -C main -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm fixture
git -C main worktree add --detach ../linked HEAD
repo_dir=$PWD/main
target=$PWD/release/src/TauFW
check_checkout_move
''', expected=1)
        self.assertIn("owns linked worktrees", output)
        self.assertTrue((directory / "main/README.md").is_file())
        self.assertFalse((directory / "release").exists())

    def test_empty_repository_is_not_reused(self):
        output, _ = self.run_script(r'''
git init -q dependency
git -C dependency remote add origin "$HTT_URL"
check_repo "$HTT_URL" "$PWD/dependency" required.root
''', expected=1)
        self.assertIn("has no checked-out commit", output)

    def test_missing_required_file_is_not_reused(self):
        output, _ = self.run_script(r'''
git init -q dependency
printf 'original\n' > dependency/README.md
git -C dependency add README.md
git -C dependency -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm fixture
git -C dependency remote add origin "$HTT_URL"
check_repo "$HTT_URL" "$PWD/dependency" required.root
''', expected=1)
        self.assertIn("Missing or empty dependency file", output)

    def test_reused_modified_dependency_is_preserved_and_warned(self):
        output, directory = self.run_script(r'''
git init -q dependency
printf 'original\n' > dependency/required.py
git -C dependency add required.py
git -C dependency -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm fixture
git -C dependency remote add origin "$TAUIDSFS_URL"
printf 'local changes\n' > dependency/required.py
install_repo "$TAUIDSFS_URL" "$PWD/dependency" "$TAUIDSFS_REF" required.py
''')
        self.assertIn("not the pinned", output)
        self.assertIn("has local changes", output)
        self.assertEqual((directory / "dependency/required.py").read_text(), "local changes\n")

    def test_download_uses_requested_commit_or_tag_instead_of_remote_head(self):
        output, _ = self.run_script(r'''
git init -q remote
printf 'pinned\n' > remote/required.py
git -C remote add required.py
git -C remote -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm pinned
ref=$(git -C remote rev-parse HEAD)
git -C remote tag vfixture
printf 'later\n' > remote/required.py
git -C remote -c user.name=Fixture -c user.email=fixture@example.invalid commit -qam later
download_repo "$PWD/remote" "$PWD/by-commit" "$ref"
download_repo "$PWD/remote" "$PWD/by-tag" vfixture
[[ $(git -C by-commit rev-parse HEAD) == "$ref" ]]
[[ $(git -C by-tag rev-parse HEAD) == "$ref" ]]
[[ $(cat by-commit/required.py) == pinned && $(cat by-tag/required.py) == pinned ]]
printf 'pins:ok\n'
''')
        self.assertIn("pins:ok", output)

    def test_interrupted_download_is_unpublished_and_clean_requirement_survives(self):
        output, directory = self.run_script(r'''
cmssw_dir=$PWD/release
mkdir -p "$cmssw_dir/src"
clean_marker=$cmssw_dir/.FastSetup-needs-clean
download_repo() { mkdir -p "$2"; printf 'partial\n' > "$2/partial"; return 1; }
install_repo "$COMBINE_URL" "$cmssw_dir/src/HiggsAnalysis/CombinedLimit" "$COMBINE_TAG" "${COMBINE_FILES[@]}"
''', expected=1)
        self.assertIn("then rerun", output)
        self.assertFalse((directory / "release/src/HiggsAnalysis/CombinedLimit").exists())
        self.assertFalse(list((directory / "release/src/HiggsAnalysis").glob(".FastSetup-*")))
        self.assertTrue((directory / "release/.FastSetup-needs-clean").is_file())
        self.run_script(r'''
cmssw_dir=$PWD/release
clean_marker=$cmssw_dir/.FastSetup-needs-clean
scram() { printf '%s\n' "$*" >> "$cmssw_dir/build.log"; }
build_release
build_release
''', directory=directory)
        self.assertEqual((directory / "release/build.log").read_text().splitlines(),
                         ["b clean", "b -j4", "b -j4"])
        self.assertFalse((directory / "release/.FastSetup-needs-clean").exists())

    def test_failed_clean_keeps_marker_for_retry(self):
        _, directory = self.run_script(r'''
cmssw_dir=$PWD/release
mkdir -p "$cmssw_dir/src"
clean_marker=$cmssw_dir/.FastSetup-needs-clean
touch "$clean_marker"
scram() { return 1; }
build_release
''', expected=1)
        self.assertTrue((directory / "release/.FastSetup-needs-clean").is_file())

    def test_nanoaod_conflict_is_detected_before_checkout_move(self):
        output, directory = self.run_script(r'''
cmssw_dir=$PWD/release
repo_dir=$PWD/main
target=$cmssw_dir/src/TauFW
mkdir -p "$repo_dir" "$cmssw_dir/.SCRAM" "$cmssw_dir/src/PhysicsTools/NanoAODTools"
git init -q "$repo_dir"
preflight_install
''', expected=1)
        self.assertIn("already overrides the release", output)
        self.assertTrue((directory / "main/.git").is_dir())
        self.assertFalse((directory / "release/src/TauFW").exists())

    def test_cross_filesystem_copy_keeps_original_and_late_edits(self):
        output, directory = self.run_script(r'''
mkdir -p original destination
printf 'before copy\n' > original/file.txt
python3() { return 3; } # Force the EXDEV fallback, independent of host drives.
cp() {
  command cp "$@"
  printf 'edit during copy\n' > "$PWD/original/file.txt"
}
move_dir "$PWD/original" "$PWD/destination/TauFW"
''')
        self.assertIn("Original checkout retained", output)
        self.assertEqual((directory / "original/file.txt").read_text(), "edit during copy\n")
        self.assertEqual((directory / "destination/TauFW/file.txt").read_text(), "before copy\n")

    def test_explicit_failure_preserves_exact_retry_options(self):
        output, _ = self.run_script(r'''
repo_dir=/new/location/TauFW
args=(--non-interactive --skip-htt --jobs 2)
die 'injected conflict'
''', expected=1)
        self.assertIn("bash /new/location/TauFW/FastSetup.sh --non-interactive --skip-htt --jobs 2", output)

    def test_python_verification_rejects_namespace_only_package(self):
        output, _ = self.run_script(r'''
mkdir EmptyTool
verify_python_modules "$PWD" EmptyTool
''', expected=1)
        self.assertIn("has no implementation file", output)

    def test_python_verification_rejects_shadowed_module(self):
        output, _ = self.run_script(r'''
mkdir expected
printf 'Symbol = object()\n' > InstalledTool.py
verify_python_modules "$PWD/expected" InstalledTool:Symbol
''', expected=1)
        self.assertIn("comes from another installation", output)

    def test_python_verification_accepts_local_implementation_and_symbol(self):
        output, _ = self.run_script(r'''
printf 'Symbol = object()\n' > InstalledTool.py
verify_python_modules "$PWD" InstalledTool:Symbol
''')
        self.assertIn("InstalledTool:", output)

    def test_htt_links_preserve_tracked_placeholder_and_recover_after_failure(self):
        # MSYS link emulation lets Bash exercise link semantics on Windows too.
        fixture_body = r'''
repo_dir=$PWD/main
cmssw_dir=$PWD/release
htt_path=$repo_dir/$HTT_PATH
mkdir -p "$htt_path" "$cmssw_dir"
git init -q "$repo_dir"
printf 'tracked placeholder\n' > "$htt_path/README.md"
git -C "$repo_dir" add "$HTT_PATH/README.md"
git -C "$repo_dir" -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm fixture
git -C "$repo_dir" update-index --skip-worktree -- "$HTT_PATH/README.md"
download_repo() {
  git init -q "$2"
  git -C "$2" remote add origin "$1"
  local file
  for file in "${HTT_FILES[@]}"; do
    mkdir -p "$(dirname -- "$2/$file")"
    printf 'fixture payload\n' > "$2/$file"
  done
  git -C "$2" add .
  git -C "$2" -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm fixture
}
ln() {
  if [[ ${@: -1} == */Muon ]]; then return 1; fi
  command ln "$@"
}
install_htt_efficiencies
'''
        _, directory = self.run_script(fixture_body, expected=1)
        placeholder = directory / "main" / "PicoProducer/data/lepton/HTT/README.md"
        self.assertEqual(placeholder.read_text(), "tracked placeholder\n")
        output, _ = self.run_script(r'''
repo_dir=$PWD/main
cmssw_dir=$PWD/release
install_htt_efficiencies
git -C "$repo_dir" status --porcelain > "$PWD/status.txt"
git -C "$repo_dir" ls-files -v -- "$HTT_PATH" > "$PWD/tracking.txt"
[[ -L $repo_dir/$HTT_PATH/Electron && -L $repo_dir/$HTT_PATH/Muon ]]
printf 'links:ok\n'
''', directory=directory)
        self.assertEqual((directory / "status.txt").read_text(), "")
        self.assertIn("links:ok", output)
        self.assertFalse((directory / "tracking.txt").read_text().startswith("S "))


if __name__ == "__main__":
    unittest.main()
