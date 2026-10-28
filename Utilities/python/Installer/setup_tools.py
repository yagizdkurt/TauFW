# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Direct FastSetup entry point, usable from a checkout before cmsenv or scram b."""
from argparse import ArgumentParser
import errno
from pathlib import Path
import sys

if __package__:
    from . import (COMPONENTS, rename_directory, verify_modules, verify_htt_files, write_setup_manifest,
                   python_environment_warnings)
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from Installer import (COMPONENTS, rename_directory, verify_modules, verify_htt_files, write_setup_manifest,
                           python_environment_warnings)


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

    manifest = commands.add_parser("manifest", help="Record the components this installation selected.")
    manifest.add_argument("--path", required=True, help="The setup manifest (Framework/python/_internal/).")
    manifest.add_argument("components", nargs="*", choices=[name for name, _ in COMPONENTS])

    args = parser.parse_args(argv)
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
    elif args.command == "userconfig":  # imported here: the other commands need only Installer
        if __package__:
            from ..UserConfig import manage
        else:
            from UserConfig import manage
        path = Path(args.path) if args.path else manage.location()
        print(("Created %s" if manage.create(path) else "Kept %s") % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
