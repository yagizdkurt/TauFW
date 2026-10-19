"""Build the Marp deck using the locally installed Marp CLI."""

import argparse
import base64
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("html", "pdf", "pptx", "all"), default="html",
                        help="default: html; all builds HTML and PDF")
    args = parser.parse_args()

    marp = shutil.which("marp.cmd") or shutil.which("marp")
    if not marp:
        parser.exit(1, "Marp CLI bulunamadı. Marp'ın PATH üzerinde olduğundan emin olun.\n")

    output = ROOT / "output"
    temp = output / ".tmp"
    temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    # Embed header assets so the HTML can be opened or shared as one file.
    markdown = (ROOT / "slides.md").read_text(encoding="utf-8")
    for asset in (ROOT / "assets").iterdir():
        if asset.is_file() and asset.suffix in (".svg", ".png"):
            mime = mimetypes.guess_type(asset.name)[0]
            encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
            markdown = markdown.replace(f'src="assets/{asset.name}"',
                                        f'src="data:{mime};base64,{encoded}"')
    source = temp / "slides.md"
    source.write_text(markdown, encoding="utf-8")
    formats = ("html", "pdf") if args.format == "all" else (args.format,)

    for fmt in formats:
        target = output / f"TauFWModernization.{fmt}"
        command = [marp, str(source), "--theme", str(ROOT / "cern.css"),
                   "--html", "--output", str(target)]
        if fmt != "html":
            command.append(f"--{fmt}")
        print(f"Build: {target}", flush=True)
        try:
            subprocess.run(command, cwd=ROOT, env=env, check=True)
        except subprocess.CalledProcessError as exc:
            return exc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
