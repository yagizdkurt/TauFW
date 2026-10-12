"""Lazy ROOT resource handling; callers retain scientific object/schema ownership."""

from contextlib import contextmanager
import importlib
from typing import Mapping, Optional, Union


def root_module():
    try:
        return importlib.import_module("ROOT")
    except ModuleNotFoundError as error:
        if error.name != "ROOT":
            raise
        raise ModuleNotFoundError("FileIO ROOT operations require PyROOT.", name="ROOT") from error


def validate_mode(mode: str) -> str:
    mode = mode.upper()
    if mode == "CREATE":
        mode = "NEW"
    if mode not in ("READ", "NEW", "RECREATE", "UPDATE"):
        raise ValueError("ROOT mode must be READ, NEW/CREATE, RECREATE, or UPDATE.")
    return mode


def compression_settings(compression: Optional[Union[int, str]], root) -> tuple:
    if compression is None:
        return None, None
    algorithm = None
    if isinstance(compression, int):
        level = compression
    elif isinstance(compression, str) and compression.isdigit():
        level = int(compression)
    elif isinstance(compression, str) and compression.count(":") == 1:
        name, value = compression.split(":")
        if name.upper() not in ("ZLIB", "LZMA", "LZ4", "ZSTD"):
            raise ValueError(f"Unsupported ROOT compression algorithm: {name!r}.")
        namespace = getattr(root, "ROOT", root)
        algorithm = getattr(namespace, "k" + name.upper())
        level = int(value)
    else:
        raise ValueError("Compression must be a level or ALGORITHM:level, such as LZMA:9.")
    if not 0 <= level <= 9:
        raise ValueError("ROOT compression level must be between 0 and 9.")
    return level, algorithm


@contextmanager
def open_file(location: str, mode: str, compression: Optional[Union[int, str]]):
    root = root_module()
    level, algorithm = compression_settings(compression, root)
    # TContext restores ROOT's current directory when this scope ends.
    directory_context = root.TDirectory.TContext() if hasattr(root, "TDirectory") else None
    try:
        root_file = root.TFile.Open(location, mode)
        if not root_file or root_file.IsZombie():
            if root_file:
                root_file.Close()
            raise OSError(f"Could not open ROOT file {location!r} in mode {mode!r}.")
        try:
            if level is not None:
                root_file.SetCompressionLevel(level)
            if algorithm is not None:
                root_file.SetCompressionAlgorithm(algorithm)
            yield root_file
        finally:
            root_file.Close()
    finally:
        del directory_context


def read_histogram(root_file, object_name: str):
    histogram = root_file.Get(object_name)
    if not histogram:
        raise KeyError(f"ROOT histogram not found: {object_name!r}.")
    if not histogram.InheritsFrom("TH1"):
        raise TypeError(f"ROOT object {object_name!r} is not a histogram.")
    detached_histogram = histogram.Clone()
    detached_histogram.SetDirectory(0)
    return detached_histogram


def validate_object_names(objects: Mapping[str, object]) -> None:
    for object_path in objects:
        if not isinstance(object_path, str) or any(part in ("", ".", "..") for part in object_path.split("/")):
            raise ValueError("ROOT object names must be nonempty relative paths without '.' or '..'.")


def write_objects(root_file, objects: Mapping[str, object]) -> None:
    for object_path, root_object in objects.items():
        *directories, object_name = object_path.split("/")
        directory = root_file
        for directory_name in directories:
            child = directory.GetDirectory(directory_name)
            if not child:
                child = directory.mkdir(directory_name)
            if not child:
                raise OSError(f"Could not create ROOT directory {directory_name!r}.")
            directory = child
        if directory.WriteObject(root_object, object_name, "Overwrite") <= 0:
            raise OSError(f"Could not write ROOT object {object_path!r}.")
