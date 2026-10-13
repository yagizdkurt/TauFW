"""Direct FastSetup entry point, usable from a checkout before cmsenv or scram b."""
from argparse import ArgumentParser
import errno
from pathlib import Path
import sys

if __package__:
    from . import rename_directory, verify_modules, verify_htt_files
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from Installer import rename_directory, verify_modules, verify_htt_files


# =============================================================================
# ==== Command dispatch ====

def main(argv=None):
    parser = ArgumentParser(description="Filesystem and verification helpers for FastSetup.")
    commands = parser.add_subparsers(dest="command", required=True)

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

    args = parser.parse_args(argv)
    if args.command == "rename":
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
