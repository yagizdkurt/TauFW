# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Direct FastSetup entry point, usable from a checkout before cmsenv or scram b."""
from argparse import ArgumentParser
import errno
from pathlib import Path
import sys

if __package__:
    from . import (COMPONENTS, rename_directory, verify_modules, verify_htt_files, write_setup_manifest,
                   read_setup_manifest, python_environment_warnings)
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from installer import (COMPONENTS, rename_directory, verify_modules, verify_htt_files, write_setup_manifest,
                           read_setup_manifest, python_environment_warnings)


# =============================================================================
# ==== Command dispatch ====

def main(argv=None):
    parser = ArgumentParser(description="Filesystem and verification helpers for FastSetup.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("environment", help="Warn about user packages shadowing CMSSW's CVMFS packages.")

    rename = commands.add_parser("rename", help="Rename a checkout; exit 3 for another filesystem.")
    rename.add_argument("source")
    rename.add_argument("destination")

    modules = commands.add_parser("modules", help="Check Python implementations and native bindings.")
    modules.add_argument("--root", help="Require module files in this directory or its corresponding CMSSW Python directory.")
    modules.add_argument("--instantiate", action="store_true", help="Construct each requested symbol.")
    modules.add_argument("specs", nargs="+", metavar="MODULE[:SYMBOL]")

    htt = commands.add_parser("htt", help="Open the required HTT ROOT correction files.")
    htt.add_argument("directory")
    htt.add_argument("files", nargs="+")

    userconfig = commands.add_parser("userconfig", help="Write a new user config if there is none; print its path.")
    userconfig.add_argument("--path", help="The file (default: $TAUFW_USER_CONFIG, else Analyses/UserConfig.yaml).")

    report = commands.add_parser("report", help="For source taufw.sh --check: one ROLE<TAB>TEXT line each for the "
                                                "components, the Python packages and the user config.")
    report.add_argument("--manifest", required=True, help="The setup manifest (Framework/python/_internal/).")

    manifest = commands.add_parser("manifest", help="Record the components this installation selected.")
    manifest.add_argument("--path", required=True, help="The setup manifest (Framework/python/_internal/).")
    # Checked by hand: before Python 3.12, argparse tests an empty nargs="*" list against choices and rejects it.
    manifest.add_argument("components", nargs="*", metavar="{%s}" % ",".join(name for name, _ in COMPONENTS))

    args = parser.parse_args(argv)
    if args.command == "manifest":
        known = [name for name, _ in COMPONENTS]
        for name in args.components:
            if name not in known:
                manifest.error("argument components: invalid choice: %r (choose from %s)"
                               % (name, ", ".join(repr(k) for k in known)))
    if args.command == "environment":
        for warning in python_environment_warnings():
            print(warning)
    elif args.command == "rename":
        try:
            rename_directory(args.source, args.destination)
        except OSError as error:
            if error.errno == errno.EXDEV:
                return 3
            print(str(error), file=sys.stderr)
            return 1
    elif args.command == "modules":
        verify_modules(args.specs, args.root, args.instantiate)
    elif args.command == "htt":
        verify_htt_files(args.directory, args.files)
    elif args.command == "manifest":
        write_setup_manifest(args.path, args.components)
        print("Recorded the selected components in %s" % args.path)
    elif args.command == "userconfig":
        manage = _user_config()
        path = Path(args.path) if args.path else manage.location()
        print(("Created %s" if manage.create(path) else "Kept %s") % path)
    elif args.command == "report":
        for role, text in report_lines(args.manifest):
            print("%s\t%s" % (role, text))
    return 0


# =============================================================================
# ==== source taufw.sh --check ====

def report_lines(manifest_path):
    """(role, text) lines of source taufw.sh --check (role: success, warning or failure; warnings do not fail the
    check): the components FastSetup installed, ~/.local packages that shadow CMSSW's, and the user config."""
    lines = []
    selected = read_setup_manifest(manifest_path)
    if selected is None:
        lines.append(("warning", "Components: not recorded (an older installation; "
                                 "source taufw.sh --install records them)"))
    else:
        labels = [label for name, label in COMPONENTS if name in selected]
        lines.append(("success", "Components: %s" % (", ".join(labels) or "none of the optional ones")))
    warnings = python_environment_warnings()
    lines += [("warning", "Python packages: %s" % (warning)) for warning in warnings]
    if not warnings:
        lines.append(("success", "Python packages: none in ~/.local shadows CMSSW's"))
    try:
        manage = _user_config()
        problems = manage.check()
    except Exception as error:  # a broken UserConfig must not hide the other lines
        problems = ["User config: cannot be checked: %s" % (error)]
        manage = None
    lines += [("warning", problem) for problem in problems]
    if not problems:
        lines.append(("success", "User config: %s" % (manage.location())))
    return lines


# =============================================================================
# ==== Helpers ====

def _user_config():
    """UserConfig.manage, imported here: the other commands need only the installer."""
    if __package__:
        from TauFW.Utilities.UserConfig import manage
    else:  # UserConfig is in <checkout>/Utilities/python
        sys.path.insert(1, str(Path(__file__).resolve().parents[4] / "Utilities" / "python"))
        from UserConfig import manage
    return manage


if __name__ == "__main__":
    sys.exit(main())
