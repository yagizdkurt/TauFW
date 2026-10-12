"""Portable runtime identity; no hostname, absolute paths, or kernel release."""
import hashlib
import importlib
import importlib.metadata
from pathlib import Path
import platform


def provenance(dependencies):
    result = {"python": platform.python_version(), "implementation": platform.python_implementation(),
              "system": platform.system(), "machine": platform.machine()}
    for name in dependencies:
        module = importlib.import_module(name)
        if name == "ROOT":
            result["ROOT"] = module.gROOT.GetVersion()
        elif name == "numpy":
            result["numpy"] = module.__version__
        elif name == "past":
            try:
                result["future"] = importlib.metadata.version("future")
            except importlib.metadata.PackageNotFoundError:
                # CMSSW/LCG can provide modules without wheel distribution metadata.
                result["future"] = {"version": getattr(module, "__version__", None),
                                    "source_sha256": hashlib.sha256(Path(module.__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
        elif name.startswith("PhysicsTools."):
            # NanoAODTools may be checked out inside CMSSW rather than installed as a distribution.
            modules = ("postprocessor", "eventloop", "datamodel", "treeReaderArrayTools", "output", "preskimming")
            hashes = {}
            for component in modules:
                source = importlib.import_module("PhysicsTools.NanoAODTools.postprocessing.framework." + component)
                hashes[component] = hashlib.sha256(Path(source.__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            result["NanoAODTools"] = hashes
    return result
