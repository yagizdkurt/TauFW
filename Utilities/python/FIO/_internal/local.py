"""Local filesystem mechanics with explicit overwrite and recursion."""

import errno
import glob
import gzip
import os
from pathlib import Path
import shutil
import stat
from typing import Optional, TextIO

from .locations import Kind


def kind(location: str) -> Optional[Kind]:
    try:
        mode = Path(location).stat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    raise OSError(f"Unsupported filesystem object: {location!r}.")


def list_directory(location: str) -> list[str]:
    return sorted(str(child) for child in Path(location).iterdir())


def expand_glob(pattern: str) -> list[str]:
    return sorted(glob.glob(pattern))


def open_text(location: str, mode: str, encoding: str) -> TextIO:
    opener = gzip.open if location.endswith(".gz") else open
    return opener(location, mode + "t", encoding=encoding, newline="")


def make_directory(location: str, parents: bool, exist_ok: bool) -> None:
    Path(location).mkdir(parents=parents, exist_ok=exist_ok)


def copy_file(source: str, destination: str, overwrite: bool) -> None:
    if os.path.lexists(destination) and os.path.samefile(source, destination):
        raise shutil.SameFileError(source, destination, "Source and destination are the same file.")
    created = False
    try:
        with open(source, "rb") as input_file:
            with open(destination, "wb" if overwrite else "xb") as output_file:
                created = True
                shutil.copyfileobj(input_file, output_file)
    except BaseException:
        if created and not overwrite:
            Path(destination).unlink(missing_ok=True)
        raise


def move_file(source: str, destination: str, overwrite: bool) -> None:
    if overwrite:
        try:
            os.replace(source, destination)
            return
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
    # Exclusive destination creation also works across local filesystems.
    copy_file(source, destination, overwrite)
    Path(source).unlink()


def remove_file(location: str, missing_ok: bool) -> None:
    Path(location).unlink(missing_ok=missing_ok)


def remove_directory(location: str, recursive: bool, missing_ok: bool) -> None:
    try:
        if Path(location).is_symlink():
            raise NotADirectoryError("Use remove_file to remove a directory symlink.")
        if recursive:
            shutil.rmtree(location)
        else:
            Path(location).rmdir()
    except FileNotFoundError:
        if not missing_ok:
            raise


def set_permissions(location: str, permissions: int) -> None:
    os.chmod(location, permissions)
