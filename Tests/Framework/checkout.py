"""Import TauFW.Framework, TauFW.Utilities and the Fitter/Histogrammer APIs from this checkout, with or without CMSSW
(no PicoProducer, no ROOT)."""
import importlib.util
from pathlib import Path
import sys
import types

REPO = Path(__file__).resolve().parents[2]


def _package(name, source):
    spec = importlib.util.spec_from_file_location(name, str(source / "__init__.py"),
                                                  submodule_search_locations=[str(source)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    setattr(sys.modules["TauFW"], name.split(".")[1], module)
    spec.loader.exec_module(module)
    return module


if "TauFW" not in sys.modules:
    package = types.ModuleType("TauFW")
    package.__path__ = []  # Only the packages registered below are importable.
    sys.modules["TauFW"] = package
for _name in ("Utilities", "Framework"):
    if "TauFW." + _name not in sys.modules:
        _package("TauFW." + _name, REPO / _name / "python")
for _name in ("Fitter", "Histogrammer"):  # no tracked __init__.py (SCRAM generates it): namespace modules for their api/
    if "TauFW." + _name not in sys.modules:
        _namespace = types.ModuleType("TauFW." + _name)
        _namespace.__path__ = [str(REPO / _name / "python")]
        sys.modules["TauFW." + _name] = _namespace
        setattr(sys.modules["TauFW"], _name, _namespace)
TAUFW_SCRIPT = REPO / "Framework" / "scripts" / "taufw.py"


def reviewed_user_config(test):
    """Point $TAUFW_USER_CONFIG at a reviewed user config of a temporary directory for the duration of `test` (a
    TestCase): the checkout's own Analyses/UserConfig.yaml is personal, and taufw.py warns while it is missing or not
    reviewed. Returns the file's path."""
    import os
    import tempfile
    from unittest import mock
    directory = tempfile.TemporaryDirectory()
    test.addCleanup(directory.cleanup)
    path = os.path.join(directory.name, "UserConfig.yaml")
    with open(path, "w") as stream:
        stream.write("taufw_user:\n  version: 1\n  reviewed: true\n")
    patcher = mock.patch.dict(os.environ, {"TAUFW_USER_CONFIG": path})
    patcher.start()
    test.addCleanup(patcher.stop)
    return path
