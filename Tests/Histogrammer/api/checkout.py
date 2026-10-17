"""Import TauFW.Utilities and TauFW.Histogrammer from this checkout, with or without CMSSW (no ROOT)."""
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
if "TauFW.Histogrammer" not in sys.modules:  # no tracked __init__.py: SCRAM generates it, so register a namespace
    module = types.ModuleType("TauFW.Histogrammer")
    module.__path__ = [str(REPO / "Histogrammer" / "python")]
    module.__package__ = "TauFW.Histogrammer"
    sys.modules["TauFW.Histogrammer"] = module
    sys.modules["TauFW"].Histogrammer = module
BASEDIR = REPO / "Histogrammer"
