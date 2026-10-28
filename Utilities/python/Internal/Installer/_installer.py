# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Python operations used by FastSetup; optional tools load only when checked."""
import importlib
import json
import os
from pathlib import Path
import tempfile


# =============================================================================
# ==== Optional components ====

# The optional components of the setup checklist: (ID, label). Recipes name the IDs (`requires:`).
COMPONENTS = (
    ("tauidsfs", "TauIDSFs"),
    ("htt", "HTT lepton efficiencies"),
    ("combine", "Combine + CombineHarvester"),
    ("run2-jme", "Standalone NanoAODTools (Run 2 JEC/JER)"),
)


def write_setup_manifest(path, components):
    """Record the components a successful installation selected: {"schema_version": 1, "components": [...]}.
    Replaces the file atomically; an unknown component ID is an error."""
    known = [name for name, _ in COMPONENTS]
    unknown = [name for name in components if name not in known]
    if unknown:
        raise ValueError("Unknown setup component: " + ", ".join(unknown))
    path = Path(path)
    data = {"schema_version": 1, "components": [name for name in known if name in components]}
    handle, stage = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(stage, str(path))
    except BaseException:
        if os.path.exists(stage):
            os.remove(stage)
        raise


def read_setup_manifest(path):
    """The component IDs the installation selected (a frozenset), or None if the file is missing or not a
    setup manifest (then nothing is known about the components)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("components"), list):
        return None
    return frozenset(name for name in data["components"] if isinstance(name, str))


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
    roots = [root] if root is not None else []
    if root is not None:
        for parent in root.parents:
            if parent.name == "src" and (parent.parent / ".SCRAM").is_dir():
                # SCRAM generates package initializers and exposes Python files
                # under <release>/python/<subsystem>/<package>. Limit acceptance
                # to the corresponding checkout, not the whole release.
                # Keep this root unresolved so links to other installs fail.
                roots.append(parent.parent / "python" / root.relative_to(parent))
                break
    for spec in specs:
        name, _, symbol = spec.partition(":")
        module = importlib.import_module(name)
        location = getattr(module, "__file__", None)
        if not location:
            raise RuntimeError("%s has no implementation file" % name)
        path = Path(location).resolve()
        if roots and not any(path == allowed or allowed in path.parents for allowed in roots):
            raise RuntimeError("%s resolves to %s, outside expected module roots: %s" %
                               (name, path, ", ".join(str(allowed) for allowed in roots)))
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
