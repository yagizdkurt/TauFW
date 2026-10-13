"""Import TauFW.Utilities and TauFW.Fitter from this checkout, with or without CMSSW (no ROOT)."""
import importlib.util
from pathlib import Path
import sys
import types

REPO = Path(__file__).resolve().parents[3]

if "TauFW" not in sys.modules:
    package = types.ModuleType("TauFW")
    package.__path__ = []  # Only the packages registered below are importable.
    sys.modules["TauFW"] = package
if "TauFW.Utilities" not in sys.modules:
    source = REPO / "Utilities" / "python"
    spec = importlib.util.spec_from_file_location("TauFW.Utilities", str(source / "__init__.py"),
                                                  submodule_search_locations=[str(source)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["TauFW.Utilities"] = module
    sys.modules["TauFW"].Utilities = module
    spec.loader.exec_module(module)
if "TauFW.Fitter" not in sys.modules:  # no tracked __init__.py: SCRAM generates it, so register a namespace
    module = types.ModuleType("TauFW.Fitter")
    module.__path__ = [str(REPO / "Fitter" / "python")]
    module.__package__ = "TauFW.Fitter"
    sys.modules["TauFW.Fitter"] = module
    sys.modules["TauFW"].Fitter = module
BASEDIR = REPO / "Fitter"
