"""Record what a sample-set function asks the Histogrammer core (the former Plotter) to do, without building any sample.

The old Histogrammer/config/samples_v15.py getsampleset() and the new TauFW.Histogrammer.sample.model.getsampleset() both end
in the same core calls: setera(), the core getsampleset(datasample, expsamples, **kwargs) and the SampleSet's stitch,
join, split and printtable. record() replaces those core functions by recorders and returns the list of calls (every
positional and keyword argument, in order), or the exception the function raised. Equal lists mean the core builds
the same SampleSet: the same samples, cross sections, weights and files, joined and split the same way.

Two environments:
  stub_utils()   a stand-in for TauFW.Histogrammer.sample.utils without ROOT (Windows, unit tests): the pure helpers are the
                 real ones (getyear, ensurelist, repkey, joinweights, joincuts); LOG and STYLE are small stand-ins
  the real module on lxplus (BBB case plotter.sample_model): only the core functions are replaced

Used by test_sample_model.py, export.py and the BBB case plotter.sample_model.
"""
import ast
import contextlib
import copy
import importlib.util
import io
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SAMPLES_V15 = REPO / "Histogrammer" / "config" / "samples_v15.py"
CMSSTYLE = REPO / "Utilities" / "python" / "Drawing" / "CMSStyle.py"
UTILS = "TauFW.Histogrammer.sample.utils"

# The eras samples_v15.py knows (the era choices of plot.py it accepts) and one channel of every channel kind.
ERAS = ('2022_preEE', '2022_postEE', '2023C', '2023D', '2024', '2025', '2026', '2526')
CHANNELS = ('mutau', 'etau', 'tautau', 'mumu', 'ee', 'emu')

# Caller options: what plot.py and createinputsTES.py pass, and every other option getsampleset reads.
OPTIONS = {
    'default':      {},
    'plot':         {'fname': "$PICODIR/$SAMPLE_$CHANNEL$TAG.root", 'rmsf': [], 'addsf': [], 'split': ['DY'],
                     'tuples': "/eos/tuples/$ERA/$GROUP"},
    'plot_nosf':    {'fname': "$PICODIR/$SAMPLE_$CHANNEL$TAG.root", 'rmsf': ['idweight_2', 'ltfweight_2'],
                     'addsf': [], 'split': [], 'tuples': None},
    'createinputs': {'fname': "$PICODIR/$SAMPLE_$CHANNEL$TAG.root", 'join': ['VV', 'TT', 'ST'], 'split': [],
                     'table': False, 'rmsf': ['idweight_2'], 'addsf': ['extra_weight'], 'tuples': "/t/$ERA/$GROUP"},
    'split_all':    {'split': ['DY', 'TT', 'ST'], 'join': ['VV', 'Top']},
    'filters':      {'filter': ['DY', 'WJ', 'TT'], 'vetoes': ['ST'], 'weight': "custom_weight",
                     'dyweight': "zptweight", 'ttweight': "", 'verbosity': 2},
    'split_dm':     {'split': ['DM']},
}


def table_lumi(era):
    """The luminosity setera() looked up before the sample model had one (schema 2, CL §26): CMSStyle.lumi_dict[era],
    else of the era's year. The table is read from the source (CMSStyle imports ROOT)."""
    from TauFW.common.tools.utils import getyear
    tree = ast.parse(CMSSTYLE.read_text(encoding="utf-8"))
    table = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                 and getattr(node.targets[0], "id", None) == "lumi_dict")
    return table.get(era, table.get(str(getyear(era))))


# =============================================================================
# ================================= RECORDING =================================


def record(function, targets, channel, era, **kwargs):
    """The core calls of function(channel, era, **kwargs): a list of [name, args, kwargs], ending with
    ['raised', type, message] if it raised. targets: (module, attribute, kind) to replace while it runs, kind
    'core' (the core getsampleset) or 'setera'."""
    calls = []
    replacements = {'core': _core(calls), 'setera': _recorded('setera', calls)}
    saved = [(module, name, getattr(module, name)) for module, name, _ in targets]
    try:
        for module, name, kind in targets:
            setattr(module, name, replacements[kind])
        with contextlib.redirect_stdout(io.StringIO()):  # prints are not calls (see D3 of the plan)
            function(channel, era, **copy.deepcopy(kwargs))
    except Exception as error:
        calls.append(['raised', type(error).__name__, str(error)])
    finally:
        for module, name, value in saved:
            setattr(module, name, value)
    return calls


def record_grid(function, targets, eras=ERAS, channels=CHANNELS, options=OPTIONS):
    """{"<era>|<channel>|<option>": calls} for every era, channel and caller option."""
    return {"%s|%s|%s" % (era, channel, name): record(function, targets, channel, era, **kwargs)
            for era in eras for channel in channels for name, kwargs in options.items()}


def _core(calls):
    def getsampleset(datasample, expsamples, sigsamples=[], **kwargs):
        calls.append(['getsampleset', _plain([datasample, list(expsamples), list(sigsamples)]), _plain(kwargs)])
        return RecordingSampleSet(calls)
    return getsampleset


def _recorded(name, calls):
    def function(*args, **kwargs):
        calls.append([name, _plain(list(args)), _plain(kwargs)])
    return function


class RecordingSampleSet(object):
    """Stands for the SampleSet the core would return: records the calls the sample-set function makes on it."""

    def __init__(self, calls):
        self._calls = calls

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return _recorded('SampleSet.' + name, self._calls)


def _plain(value):
    """A JSON-like copy (tuples become lists, so the BBB snapshot and the comparison see the same thing)."""
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    return value


# =============================================================================
# ================================== MODULES ==================================


def load_samples_v15():
    """A fresh copy of Histogrammer/config/samples_v15.py (imports TauFW.Histogrammer.sample.utils: the stub or the real one)."""
    spec = importlib.util.spec_from_file_location("samples_v15_recorded", str(SAMPLES_V15))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def old_targets(samples_v15):
    """What to replace for the old function: the names samples_v15.py imported from the utils module."""
    return [(samples_v15, '_getsampleset', 'core'), (samples_v15, 'setera', 'setera')]


def model_targets(utils):
    """What to replace for TauFW.Histogrammer.sample.model.getsampleset: it imports them from the utils module per call."""
    return [(utils, 'getsampleset', 'core'), (utils, 'setera', 'setera')]


@contextlib.contextmanager
def stub_utils():
    """Install a ROOT-free TauFW.Histogrammer.sample.utils in sys.modules (and remove it afterwards); yields it."""
    from TauFW.common.tools.utils import ensurelist, repkey, getyear
    from TauFW.Utilities.Expressions import joinweights, joincuts
    module = types.ModuleType(UTILS)
    module.LOG = _Log()
    module.STYLE = types.SimpleNamespace(sample_titles={'ZTT': "Z -> #tau_{{l}}#tau_{h}"})
    module.ensurelist, module.repkey, module.getyear = ensurelist, repkey, getyear
    module.joinweights, module.joincuts = joinweights, joincuts
    for name in ('ensuredir', 'loadmacro', 'Sel', 'Var', 'getsampleset', 'setera'):
        setattr(module, name, _unused(name))
    previous = sys.modules.get(UTILS)
    sys.modules[UTILS] = module
    try:
        yield module
    finally:
        if previous is None:
            sys.modules.pop(UTILS, None)
        else:
            sys.modules[UTILS] = previous


class _Log(object):
    """The parts of the Histogrammer's Logger that getsampleset uses."""

    def getverbosity(self, *args):
        for arg in args:
            if isinstance(arg, dict):
                return arg.get('verbosity', arg.get('verb', 0))
        return 0

    def verb(self, *args, **kwargs):
        pass

    def throw(self, error, message):
        raise error(message)


def _unused(name):
    def function(*args, **kwargs):
        raise RuntimeError("%s is not available in the stub utils module" % (name))
    return function
