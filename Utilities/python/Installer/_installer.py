"""Python operations used by FastSetup; optional tools load only when checked."""
import importlib
import os
from pathlib import Path


# =============================================================================
# ==== Checkout relocation ====

def rename_directory(source, destination):
    """Rename without replacing a destination; propagate EXDEV to the caller."""
    if os.path.lexists(destination):
        raise FileExistsError("Destination already exists: " + str(destination))
    os.rename(source, destination)


# =============================================================================
# ==== Python and native bindings ====

def verify_modules(specs, expected_root=None, instantiate=False):
    """Import MODULE[:SYMBOL] specs, check their origin, and optionally construct symbols."""
    root = Path(expected_root).resolve() if expected_root is not None else None
    for spec in specs:
        name, _, symbol = spec.partition(":")
        module = importlib.import_module(name)
        location = getattr(module, "__file__", None)
        if not location:
            raise RuntimeError("%s has no implementation file" % name)
        path = Path(location).resolve()
        if root is not None:
            # Reject modules shadowed by another PYTHONPATH entry.
            path.relative_to(root)
        if symbol:
            value = getattr(module, symbol)
            if instantiate:
                value()
        elif instantiate:
            raise ValueError("Construction requires MODULE:SYMBOL: " + spec)
        print("%s: %s" % (name, path))


# =============================================================================
# ==== HTT correction files ====

def verify_htt_files(directory, files):
    """Open the required correction files with ROOT and reject empty payloads."""
    ROOT = importlib.import_module("ROOT")
    for relative in files:
        path = Path(directory) / relative
        handle = ROOT.TFile.Open(str(path), "READ")
        if not handle:
            raise RuntimeError("Cannot open HTT correction file: %s" % path)
        try:
            if handle.IsZombie():
                raise RuntimeError("Cannot open HTT correction file: %s" % path)
            if handle.GetListOfKeys().GetSize() == 0:
                raise RuntimeError("HTT correction file contains no objects: %s" % path)
        finally:
            handle.Close()
    print("HTT correction files are readable")
