"""Import TauFW.Utilities from this checkout, with or without CMSSW; its installed copy may be another checkout."""
import importlib.util
from pathlib import Path
import sys
import types

SOURCE = Path(__file__).resolve().parents[2] / "Utilities" / "python"

if "TauFW" not in sys.modules:
    package = types.ModuleType("TauFW")
    package.__path__ = []  # Other TauFW packages stay unimportable; Utilities must not depend on them.
    sys.modules["TauFW"] = package
if "TauFW.Utilities" not in sys.modules:
    spec = importlib.util.spec_from_file_location("TauFW.Utilities", str(SOURCE / "__init__.py"),
                                                  submodule_search_locations=[str(SOURCE)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["TauFW.Utilities"] = module
    spec.loader.exec_module(module)
    sys.modules["TauFW"].Utilities = module
