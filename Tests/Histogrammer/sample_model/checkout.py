"""Import TauFW.Utilities, TauFW.common and TauFW.Histogrammer from this checkout, with or without CMSSW (no ROOT): the
sample model reader and the recorder's stub need only these pure-Python parts."""
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
for _name, _directory in (("Histogrammer", "Histogrammer"), ("common", "common")):  # no tracked __init__.py: namespaces
    if "TauFW." + _name not in sys.modules:
        module = types.ModuleType("TauFW." + _name)
        module.__path__ = [str(REPO / _directory / "python")]
        module.__package__ = "TauFW." + _name
        sys.modules["TauFW." + _name] = module
        setattr(sys.modules["TauFW"], _name, module)
