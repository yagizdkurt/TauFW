"""Exercise setup selection/dispatch with Bash and stubbed installation steps."""
from pathlib import Path
import shutil
import subprocess
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
    def run_setup(self, *args):
        source = (REPO / "FastSetup.sh").read_text(encoding="utf-8")
        source = source.rsplit('main "$@"', 1)[0]
        # Replace external operations only; run the actual parser, selection,
        # pipeline dispatch, verification, and resume-argument construction.
        source += r"""
check_host() { :; }
locate_checkout() { repo_dir=/checkout; }
choose_release_area() { cmssw_dir=/release; }
choose_scram_arch() { :; }
load_cms_software() { :; }
create_release() { :; }
activate_release() { :; }
move_checkout() { :; }
install_nanoaodtools() { printf 'nano:%s\n' "$run2_jme"; }
install_tauidsfs() { printf 'install:tauidsfs\n'; }
install_htt_efficiencies() { printf 'install:htt\n'; }
install_combine() { printf 'install:combine\n'; }
build_release() { printf 'build\n'; }
python3() { printf 'verify:%s\n' "$2"; }
combine() { :; }
command() {
  if [[ $* == '-v combine' ]]; then printf 'verify:combine\n' >&2; fi
  builtin command "$@"
}
print_summary() { printf 'retry:%s\n' "${args[@]}"; }
main "$@"
"""
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "setup.sh"
            script.write_text(source, encoding="utf-8", newline="\n")
            result = subprocess.run([BASH, str(script), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout + result.stderr

    def test_default_nonterminal_selection_preserves_installations(self):
        output = self.run_setup()
        self.assertIn("install:tauidsfs", output)
        self.assertIn("install:htt", output)
        self.assertIn("install:combine", output)
        self.assertIn("nano:false", output)
        self.assertIn("import TauPOG.TauIDSFs", output)
        self.assertIn("verify:combine", output)
        self.assertIn("retry:--non-interactive", output)

    def test_skipped_components_do_not_install_or_verify(self):
        output = self.run_setup("--non-interactive", "--skip-tauidsfs", "--skip-htt", "--skip-combine", "--run2-jme")
        self.assertNotIn("install:", output)
        self.assertNotIn("import TauPOG.TauIDSFs", output)
        self.assertNotIn("verify:combine", output)
        self.assertIn("nano:true", output)
        self.assertIn("build", output)
        for flag in ("--skip-tauidsfs", "--skip-htt", "--skip-combine", "--run2-jme"):
            self.assertIn("retry:" + flag, output)


if __name__ == "__main__":
    unittest.main()
