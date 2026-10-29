"""Focused installer regressions; no network downloads or CMSSW builds."""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "Framework/python/_internal/installer/setup_tools.py"
BASH = shutil.which("bash")
if BASH is None:
    git = shutil.which("git")
    candidate = Path(git).parent.parent / "bin" / "bash.exe" if git else None
    if candidate and candidate.is_file():
        BASH = str(candidate)


def write_lf(path, text):
    """Write a shell script with LF line endings (Path.write_text(newline=) needs Python 3.10)."""
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


@unittest.skipUnless(BASH, "Bash is unavailable")
class FastSetupTests(unittest.TestCase):
    def run_script(self, body, *args, expected=0, directory=None, helper_from_checkout=False):
        source = (REPO / "Utilities/FastSetup.sh").read_text(encoding="utf-8")
        source = source.rsplit('main "$@"', 1)[0]
        if directory is None:
            fixture = tempfile.TemporaryDirectory()
            self.addCleanup(fixture.cleanup)
            directory = Path(fixture.name)
        script = directory / "setup.sh"
        # Fixture checkouts omit Utilities; use the real helper with fixture inputs.
        source += '\npython3() { "$FASTSETUP_TEST_PYTHON" "$@"; }\n'
        if not helper_from_checkout:
            source += 'installer_python() { python3 "$FASTSETUP_TEST_INSTALLER" "$@"; }\n'
        write_lf(script, source + body)
        env = dict(os.environ, FASTSETUP_TEST_PYTHON=sys.executable,
                   FASTSETUP_TEST_INSTALLER=str(INSTALLER), MSYS="winsymlinks:sys",
                   PYTHONDONTWRITEBYTECODE="1")
        # Python scripts, unlike stdin probes, do not add the fixture cwd to sys.path.
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(directory), env.get("PYTHONPATH")]))
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
invalidate_setup_record() { :; }
publish_setup_record() { :; }
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

    def test_compact_summary_component_status_and_direct_activation(self):
        output, _ = self.run_script(r'''
export LC_ALL=C
repo_dir=/installed/TauFW
SCRAM_ARCH=el9_amd64_gcc12
tauidsfs=true
htt=false
combine=false
run2_jme=false
print_summary
''')
        self.assertEqual(output.count("Setup complete"), 1)
        self.assertIn("[OK]   TauIDSFs: Verified this run", output)
        self.assertIn("HTT efficiencies: Not selected", output)
        self.assertIn("NanoAODTools: using the CMSSW version", output)
        self.assertIn("source /installed/TauFW/taufw.sh", output)
        self.assertNotIn("Manual activation", output)
        self.assertNotIn("checkout was moved", output)
        self.assertNotIn("\x1b[", output)

    def test_user_config_is_created_once_and_named_in_the_summary(self):
        """Analyses/UserConfig.yaml of the installed checkout (Utilities/python/UserConfig, CL §40)."""
        output, directory = self.run_script(r'''
unset TAUFW_USER_CONFIG
export LC_ALL=C
repo_dir=$PWD
mkdir Analyses
create_user_config
printf 'reviewed: true\n' >> Analyses/UserConfig.yaml
create_user_config
SCRAM_ARCH=el9_amd64_gcc12
tauidsfs=false
htt=false
combine=false
run2_jme=false
print_summary
mv Analyses elsewhere
user_config=
create_user_config
printf 'after:%s\n' "$user_config"
''')
        path = directory / "Analyses" / "UserConfig.yaml"
        self.assertEqual(output.count("[FastSetup] Created "), 1)
        self.assertEqual(output.count("[FastSetup] Kept "), 1)
        self.assertIn("User config  ", output)
        self.assertIn("UserConfig.yaml (review it)", output)
        self.assertIn("WARNING: Could not create the user config", output)  # no Analyses/: a warning, not a failure
        self.assertIn("after:\n", output)
        text = (directory / "elsewhere" / "UserConfig.yaml").read_text(encoding="utf-8")
        self.assertIn("reviewed: false", text)
        self.assertTrue(text.endswith("reviewed: true\n"))  # the second run kept the file
        self.assertFalse(path.exists())

    def test_environment_warning_precedes_verification_and_is_retained(self):
        output, _ = self.run_script(r'''
exec 2>&1
repo_dir=/checkout
CMSSW_RELEASE_BASE=/release
run2_jme=false
tauidsfs=false
htt=false
combine=false
installer_python() {
  if [[ $1 == environment ]]; then
    printf 'numpy imports from ~/.local instead of /cvmfs. Run: pip3 uninstall numpy\n'
  fi
}
verify_python_modules() { printf 'module verification\n'; }
verify_install
printf 'retained:%s\n' "${warnings[@]}"
''')
        self.assertIn("WARNING: numpy imports", output)
        self.assertIn("retained:numpy imports", output)
        self.assertLess(output.index("pip3 uninstall numpy"), output.index("module verification"))

    def test_event_summary_is_plain_and_wrapper_has_activation_prompt(self):
        output, directory = self.run_script(r'''
export LC_ALL=C
repo_dir=/installed/TauFW
SCRAM_ARCH=el9_amd64_gcc12
tauidsfs=false
htt=false
combine=false
run2_jme=false
copied_from=/original
warnings=('one warning')
export FASTSETUP_RESULT_FILE=/tmp/result
exec 9>events.bin
export FASTSETUP_EVENT_FD=9
print_summary
exec 9>&-
''')
        self.assertIn("None selected", output)
        self.assertIn("Press Enter to close and activate", output)
        self.assertIn("Original checkout retained at: /original", output)
        self.assertNotIn("one warning", output)
        self.assertNotIn("\x1b[", output)
        self.assertNotIn(b"\x1b", (directory / "events.bin").read_bytes())

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

    def test_reporting_pipe_keeps_plain_output_and_exact_retry(self):
        output, directory = self.run_script(r'''
exec 9>events.bin
export FASTSETUP_EVENT_FD=9
repo_dir='/installed clone'
args=(--non-interactive --jobs 7 --skip-combine)
banner Build
log 'Building with 7 jobs'
warn 'Architecture mismatch'
print_retry
exec 9>&-
''')
        events = (directory / "events.bin").read_bytes().split(b"\0")
        self.assertEqual(events[:6], [b"stage", b"Build", b"activity", b"Building with 7 jobs",
                                     b"warning", b"[FastSetup] WARNING: Architecture mismatch"])
        self.assertEqual(events[6], b"retry")
        self.assertIn(b"--jobs 7 --skip-combine", events[7])
        self.assertIn("==== Build ====", output)
        self.assertIn("WARNING: Architecture mismatch", output)

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

    def test_same_filesystem_move_uses_python_helper(self):
        _, directory = self.run_script(r'''
mkdir original destination
printf 'original\n' > original/file.txt
move_dir "$PWD/original" "$PWD/destination/TauFW"
''')
        self.assertFalse((directory / "original").exists())
        self.assertEqual((directory / "destination/TauFW/file.txt").read_text(), "original\n")

    def test_shell_finds_helper_before_and_after_checkout_relocation(self):
        with tempfile.TemporaryDirectory() as fixture:
            directory = Path(fixture)
            shutil.copytree(INSTALLER.parent, directory / "original/Framework/python/_internal/installer",
                            ignore=shutil.ignore_patterns("__pycache__"))
            output, _ = self.run_script(r'''
repo_dir=$PWD/original
target=$PWD/installed
installer_python --help
move_checkout
installer_python modules --root "$repo_dir" installer:rename_directory
''', directory=directory, helper_from_checkout=True)
            self.assertIn("installer:", output)
            self.assertFalse((directory / "original").exists())
            self.assertTrue((directory / "installed/Framework/python/_internal/installer/setup_tools.py").is_file())

    def test_move_rejects_existing_destination_without_changing_either_copy(self):
        output, directory = self.run_script(r'''
mkdir original installed
printf 'original\n' > original/file.txt
printf 'installed\n' > installed/file.txt
move_dir "$PWD/original" "$PWD/installed"
''', expected=1)
        self.assertIn("Destination already exists", output)
        self.assertEqual((directory / "original/file.txt").read_text(), "original\n")
        self.assertEqual((directory / "installed/file.txt").read_text(), "installed\n")

    def test_explicit_failure_preserves_exact_retry_options(self):
        output, _ = self.run_script(r'''
repo_dir=/new/location/TauFW
args=(--non-interactive --skip-htt --jobs 2)
die 'injected conflict'
''', expected=1)
        self.assertIn("bash /new/location/TauFW/Utilities/FastSetup.sh --non-interactive --skip-htt --jobs 2", output)

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

    def test_python_verification_accepts_cmssw_generated_package(self):
        output, _ = self.run_script(r'''
mkdir -p release/.SCRAM release/src/TauFW release/python/TauFW/PicoProducer
printf '' > release/python/TauFW/__init__.py
printf 'Symbol = object()\n' > release/python/TauFW/PicoProducer/__init__.py
export PYTHONPATH="$PWD/release/python"
verify_python_modules "$PWD/release/src/TauFW" TauFW.PicoProducer:Symbol
''')
        self.assertIn("TauFW.PicoProducer:", output)

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


class InstallerHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = INSTALLER.parent / "_installer.py"
        spec = importlib.util.spec_from_file_location("installer_helpers", path)
        cls.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helpers)

    def test_direct_entry_point_works_before_cmssw(self):
        result = subprocess.run([sys.executable, "-B", str(INSTALLER), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("rename", result.stdout)
        self.assertIn("modules", result.stdout)
        self.assertIn("htt", result.stdout)

    def test_cross_device_rename_keeps_its_distinct_error(self):
        import errno
        with patch.object(self.helpers.os, "rename", side_effect=OSError(errno.EXDEV, "other filesystem")):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(OSError) as error:
                    self.helpers.rename_directory(directory, Path(directory) / "absent")
        self.assertEqual(error.exception.errno, errno.EXDEV)

    def test_native_binding_failure_is_not_reported_as_success(self):
        constructor = Mock(side_effect=RuntimeError("native library unavailable"))
        module = SimpleNamespace(__file__=__file__, Native=constructor)
        with patch.object(self.helpers.importlib, "import_module", return_value=module):
            with self.assertRaisesRegex(RuntimeError, "native library unavailable"):
                self.helpers.verify_modules(["Tool:Native"], instantiate=True)
        constructor.assert_called_once()

    def test_cmssw_source_and_python_origins(self):
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory).resolve() / "release"
            (release / ".SCRAM").mkdir(parents=True)
            for checkout, module_file in (
                ("TauFW", "TauFW/PicoProducer/__init__.py"),
                ("TauFW", "TauFW/Plotter/__init__.py"),
                ("TauFW", "TauFW/Fitter/__init__.py"),
                ("TauPOG/TauIDSFs", "TauPOG/TauIDSFs/TauIDSFTool.py"),
                ("PhysicsTools/NanoAODTools", "PhysicsTools/NanoAODTools/postprocessing/framework/postprocessor.py"),
                ("HiggsAnalysis/CombinedLimit", "HiggsAnalysis/CombinedLimit/PhysicsModel.py"),
                ("CombineHarvester", "CombineHarvester/CombineTools/ch.py"),
            ):
                root = release / "src" / checkout
                for location in (root / "python/tool.py", release / "python" / module_file):
                    with self.subTest(checkout=checkout, location=location):
                        module = SimpleNamespace(__file__=str(location), Symbol=object())
                        with patch.object(self.helpers.importlib, "import_module", return_value=module):
                            self.helpers.verify_modules(["Tool:Symbol"], root)

            for location in (
                release.parent / "other-release/python/TauFW/PicoProducer/__init__.py",
                release / "python/TauFWOther/PicoProducer/__init__.py",
                release / "python/TauPOG/TauIDSFs/TauIDSFTool.py",
            ):
                with self.subTest(rejected=location):
                    module = SimpleNamespace(__file__=str(location))
                    with patch.object(self.helpers.importlib, "import_module", return_value=module):
                        with self.assertRaisesRegex(RuntimeError, "outside expected module roots"):
                            self.helpers.verify_modules(["Tool"], release / "src/TauFW")

    def test_python_mapping_requires_a_cmssw_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            module = SimpleNamespace(__file__=str(root / "python/TauFW/tool.py"))
            with patch.object(self.helpers.importlib, "import_module", return_value=module):
                with self.assertRaisesRegex(RuntimeError, "outside expected module roots"):
                    self.helpers.verify_modules(["Tool"], root / "src/TauFW")

    def test_cmssw_python_symlinks_check_their_resolved_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory).resolve() / "release"
            source = release / "src/TauFW/PicoProducer/python/tool.py"
            source.parent.mkdir(parents=True)
            source.write_text("Symbol = object()\n")
            (release / ".SCRAM").mkdir()
            installed = release / "python/TauFW/PicoProducer/tool.py"
            installed.parent.mkdir(parents=True)
            external = release.parent / "other-install/tool.py"
            external.parent.mkdir()
            external.write_text("Symbol = object()\n")
            try:
                installed.symlink_to(source)
            except OSError as error:
                self.skipTest("File symlinks unavailable: %s" % error)
            module = SimpleNamespace(__file__=str(installed))
            with patch.object(self.helpers.importlib, "import_module", return_value=module):
                self.helpers.verify_modules(["Tool"], release / "src/TauFW")
                installed.unlink()
                installed.symlink_to(external)
                with self.assertRaisesRegex(RuntimeError, "outside expected module roots"):
                    self.helpers.verify_modules(["Tool"], release / "src/TauFW")

    def test_htt_verification_closes_an_unusable_root_file(self):
        handle = SimpleNamespace(IsZombie=lambda: True, Close=Mock())
        root = SimpleNamespace(TFile=SimpleNamespace(Open=lambda *args: handle))
        with patch.object(self.helpers.importlib, "import_module", return_value=root):
            with self.assertRaisesRegex(RuntimeError, "Cannot open HTT correction file"):
                self.helpers.verify_htt_files("corrections", ["broken.root"])
        handle.Close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
