"""Test-only package setup and temporary copies of the current implementation."""
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import types

TESTS = Path(__file__).resolve().parents[1]
REPO = TESTS.parent


class MissingDependency(RuntimeError):
    pass


def _package(name, directory, initialize=False):
    init = directory / "__init__.py"
    if initialize and init.exists():
        spec = importlib.util.spec_from_file_location(name, str(init), submodule_search_locations=[str(directory)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    else:
        module = types.ModuleType(name)
        module.__path__ = [str(directory)]
        module.__package__ = name
        sys.modules[name] = module
    if "." in name:
        parent, attribute = name.rsplit(".", 1)
        setattr(sys.modules[parent], attribute, module)
    return module


def prepare(workspace, resources=True):
    """Use fresh source copies so config writes and ACLiC cannot touch the checkout."""
    workspace = Path(workspace).resolve()
    mirror = workspace / "TauFW"
    mirror.mkdir()
    _package("TauFW", mirror)
    for name in ("common", "Plotter", "PicoProducer", "Fitter"):
        source = REPO / name
        target = mirror / name
        target.mkdir()
        shutil.copytree(source / "python", target / "python",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.so", "*.pcm", "*.d", "*.dll", "*.pyd"))
        for resource in (("data", "samples") if resources else ()):
            if (source / resource).exists():
                (target / resource).symlink_to(source / resource, target_is_directory=True)
        # PicoProducer's initializer otherwise selects CMSSW_BASE's checkout.
        cmssw = os.environ.pop("CMSSW_BASE", None)
        try:
            _package("TauFW." + name, target / "python", initialize=True)
        finally:
            if cmssw is not None:
                os.environ["CMSSW_BASE"] = cmssw
    sys.path.insert(0, str(REPO))  # Makes relocated Tests.PicoProducer.analysis.TestModule importable.
    sys.path.insert(0, str(TESTS))
    return mirror


def dependencies(names):
    import importlib
    for name in names:
        try:
            module = importlib.import_module(name)
            if name == "ROOT":
                module.PyConfig.IgnoreCommandLineOptions = True
        except (ImportError, OSError) as error:
            raise MissingDependency("Missing/unusable %s: %s. Activate the lxplus Python 3.9/PyROOT environment; "
                               "NanoAODTools cases also require PhysicsTools.NanoAODTools. No case was skipped."
                               % (name, error)) from error


def configure_root(workspace, single_thread=False):
    import ROOT
    ROOT.PyConfig.IgnoreCommandLineOptions = True
    ROOT.gROOT.SetBatch(True)
    build = Path(workspace) / "aclic"
    build.mkdir(exist_ok=True)
    ROOT.gSystem.SetBuildDir(str(build), True)
    ROOT.gRandom.SetSeed(1777)
    if single_thread:
        ROOT.DisableImplicitMT()
    import numpy
    numpy.random.seed(1777)
    return ROOT
