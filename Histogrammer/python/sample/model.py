# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Sample model: the samples of one era as data (a template of Configs/Plotter/samples/, copied into a bundle).

    load_sample_model(path) ─▶ SampleModel (ROOT-free: YAML only)
    pick(paths, era)         ─▶ the model of one era from a list of files
    getsampleset(channel, era, model, **kwargs) ─▶ SampleSet (imports TauFW.Histogrammer.sample.utils, so ROOT, when called)

getsampleset() is Histogrammer/config/samples_v15.py getsampleset() with its era-specific part read from the model: the MC
table, the data dataset per channel kind, the MC weight per channel kind, the stitching and the era's extra joins.
The rest is copied as it was (the caller's options, the joins, the genmatch split, the table), including its
behaviour where it is odd: the caller's options are passed on to the core getsampleset (and so to every sample),
a caller `weight` wins over the model's weight, split 'DM' raises NameError (Histogrammer BUGS L14). The call-by-call
equality with samples_v15.py is tested in Tests/Histogrammer/sample_model/ and by the BBB case plotter.sample_model.
Not copied: the debug print of the data dataset for 2022_preEE muon channels.

The file (schema 1; the taufw_config header: Configs/README.md):

    era: '2025'                  the era of the file (exact)
    cme: 13.6                    centre-of-mass energy [TeV], for setera and the stitching
    extraweights: {dyweight: zptweight_nnlo, ttweight: ttptweight}   defaults; a caller may override them by name
    mc: [{group, name, title, xsec, extraweight (optional: a key of extraweights)}, ...]   in this order
    data: {tautau|muon|electron|emu: dataset pattern}   by channel kind (CHANNEL KINDS below)
    weights: {semileptonic|ditau|other: MC weight}      by channel kind
    stitch: [{pattern, incl, name}, ...]                SampleSet.stitch, in this order
    join: [{patterns: [...], name}, ...]                SampleSet.join right after the DY join, in this order

Channel kinds (the channel name decides, as in samples_v15.py, first match):
    data:    'tautau' in channel -> tautau; 'mutau' or 'mumu' -> muon; 'etau' or 'ee' -> electron; 'emu' -> emu
    weights: 'mutau' or 'etau' in channel -> semileptonic; channel 'tautau' or 'ditau' -> ditau; else other

Public API:
  load_sample_model(path) -> SampleModel, pick(paths, era) -> SampleModel, sample_names(model, channel)
  getsampleset(channel, era, model, **kwargs) -> SampleSet
  SampleModel, SampleModelError, SCHEMA
"""
import os
from dataclasses import dataclass
from typing import Tuple

__all__ = ['load_sample_model', 'pick', 'sample_names', 'getsampleset', 'SampleModel', 'SampleModelError', 'SCHEMA']


# =============================================================================
# ================================= CONSTANTS =================================


SCHEMA       = 1                                    # the format this module reads (taufw_config.schema)
HEADER_KEY   = 'taufw_config'                       # the template header (Framework/python/configs.py)
KEYS         = ('era', 'cme', 'extraweights', 'mc', 'data', 'weights', 'stitch', 'join')
MC_KEYS      = ('group', 'name', 'title', 'xsec', 'extraweight')
DATA_KINDS   = ('tautau', 'muon', 'electron', 'emu')
WEIGHT_KINDS = ('semileptonic', 'ditau', 'other')


# =============================================================================
# ================================= SAMPLESET =================================


def getsampleset(channel, era, model, **kwargs):
  """The SampleSet of a channel and era: Histogrammer/config/samples_v15.py getsampleset() with the model's samples."""
  from TauFW.Histogrammer.sample.utils import LOG, STYLE, ensurelist, setera, joinweights
  from TauFW.Histogrammer.sample.utils import getsampleset as _getsampleset
  if era != model.era:
    LOG.throw(IOError,"Sample model %s is for era %r, not %r!"%(model.path,model.era,era))
  verbosity = LOG.getverbosity(kwargs)
  fname    = kwargs.get('fname', "$PICODIR/$SAMPLE_$CHANNEL$TAG.root" ) # file name pattern of pico files
  split    = kwargs.get('split',    ['DY'] if 'tau' in channel else [ ] ) # split samples (e.g. DY) into genmatch components
  join     = kwargs.get('join',     ['VV','Top'] ) # join samples (e.g. VV, top)
  rmsfs    = ensurelist(kwargs.get('rmsf', [ ])) # remove the tau ID SF, e.g. rmsf=['idweight_2','ltfweight_2']
  addsfs   = ensurelist(kwargs.get('addsf', [ ])) # add extra weight to all samples
  weight   = kwargs.get('weight',   None         ) # weight for all MC samples
  extraweights = {name: kwargs.get(name, value) for name, value in model.extraweights.items()} # e.g. dyweight, ttweight
  filter   = kwargs.get('filter',   None         ) # only include these MC samples
  vetoes   = kwargs.get('vetoes',   None         ) # veto these MC samples
  table    = kwargs.get('table',    True         ) # print sample set table
  setera(era,cme=model.cme) # set era for plot style and lumi-xsec normalization
  if 'TT' in split and 'Top' in join: # don't join TT & ST
    join.remove('Top')
    join += ['TT','ST']

  # SM BACKGROUND MC SAMPLES
  expsamples = [ ] # table of MC samples to be converted to Sample objects
  for row in model.mc:
    if 'extraweight' in row:
      expsamples.append((row['group'],row['name'],row['title'],row['xsec'],{'extraweight': extraweights[row['extraweight']]}))
    else:
      expsamples.append((row['group'],row['name'],row['title'],row['xsec']))

  # OBSERVED DATA SAMPLES
  datasample = ('Data',_kind_value(model,'data',_data_kind(channel,LOG),channel,LOG)) # GROUP, NAME

  # FILTER
  if filter:
    expsamples = [s for s in expsamples if any(f in s[0] for f in filter)]
  if vetoes:
    expsamples = [s for s in expsamples if not any(v in s[0] for v in vetoes)]

  # SAMPLE SET
  weight = _kind_value(model,'weights',_weight_kind(channel),channel,LOG)
  for sf in rmsfs: # remove (old) SFs, e.g. for SF measurement
    weight = weight.replace(sf,"").replace("**","*").strip('*')
  for sf in addsfs:  # add extra SFs, e.g. for SF measurement
    weight = joinweights(weight,sf)
  kwargs.setdefault('weight',weight) # common weight for MC
  kwargs.setdefault('fname', fname)  # default filename pattern
  sampleset = _getsampleset(datasample,expsamples,channel=channel,era=era,**kwargs)
  LOG.verb("weight = %r"%(weight),verbosity,1)

  # STITCH
  for stitch in model.stitch:
    sampleset.stitch(stitch['pattern'], incl=stitch['incl'], name=stitch['name'], cme=model.cme)

  # JOIN
  sampleset.join('DY', name='DY' ) # Drell-Yan, M < 50 GeV + M > 50 GeV
  for extra in model.join: # the era's extra joins, e.g. W + jets (NLO) decay modes
    sampleset.join(*extra['patterns'], name=extra['name'] )
  if 'VV' in join:
    sampleset.join('VV','WZ','WW','ZZ', name='VV' ) # Diboson
  if 'TT' in join and era!='year':
    sampleset.join('TT', name='TT' ) # ttbar
  if 'ST' in join:
    sampleset.join('ST', name='ST' ) # single top
  if 'Top' in join:
    sampleset.join('TT','ST', name='Top' ) # ttbar + single top

  # SPLIT
  # Note: titles are set via STYLE.sample_titles
  if split and channel.count('tau')==1:
    ZTT = STYLE.sample_titles.get('ZTT',"Z -> %s"%channel) # title
    if channel.count('tau')==1:
      ZTT = ZTT.replace("{l}","{mu}" if "mu" in channel else "{e}")
      GMR = "genmatch_2==5"
      GML = "genmatch_2>0 && genmatch_2<5"
      GMJ = "genmatch_2==0"
      GMF = "genmatch_2<5"
    elif channel.count('tau')==2:
      ZTT = ZTT.replace("{l}","{h}")
      GMR = "genmatch_1==5 && genmatch_2==5"
      GML = "(genmatch_1<5 || genmatch_2<5) && genmatch_1>0 && genmatch_2>0"
      GMJ = "(genmatch_1==0 || genmatch_2==0)"
      GMF = "(genmatch_1<5 || genmatch_2<5)"
    else:
      LOG.throw(IOError,"Did not recognize channel %r!"%(channel))
    if 'DM' in split: # split DY by decay modes; BUGS L14: `samples` is undefined (NameError), as in samples_v15.py
      samples.split('DY', [('ZTTDM0', ZTT+", h^{#pm}",                   GMR+" && dm_2==0"),
                           ('ZTTDM1', ZTT+", h^{#pm}h^{0}",              GMR+" && dm_2==1"),
                           ('ZTTDM10',ZTT+", h^{#pm}h^{#mp}h^{#pm}",     GMR+" && dm_2==10"),
                           ('ZTTDM11',ZTT+", h^{#pm}h^{#mp}h^{#pm}h^{0}",GMR+" && dm_2==11"),
                           ('ZL',GML),('ZJ',GMJ),])
    elif 'DY' in split:
      sampleset.split('DY',[('ZTT',ZTT,GMR),('ZL',GML),('ZJ',GMJ),])
    if 'TT' in split:
      sampleset.split('TT',[('TTT',GMR),('TTJ',GMF),('TTL',"genmatch_2>0 && genmatch_2<5")])
    if 'ST' in split:
      sampleset.split('ST',[('TTT',"genmatch_2==5 && genmatch_2<5"),('STJ',"genmatch_2<5")])

  if table:
    sampleset.printtable(merged=True,split=True)
  print(">>> common weight: %r"%(weight))
  return sampleset


# =============================================================================
# ================================== READING ==================================


def load_sample_model(path):
  """The SampleModel of a file (raises SampleModelError, listing every problem). Needs only YAML."""
  import yaml
  try:
    with open(path) as stream:
      data = yaml.safe_load(stream)
  except Exception as error:
    raise SampleModelError(path, ["cannot read the YAML: %s" % (error)])
  problems = _problems(data)
  if problems:
    raise SampleModelError(path, problems)
  return SampleModel(path=os.path.abspath(path), era=data['era'], cme=data['cme'],
                     extraweights=dict(data['extraweights']), mc=tuple(dict(row) for row in data['mc']),
                     data=dict(data['data']), weights=dict(data['weights']),
                     stitch=tuple(dict(entry) for entry in data['stitch']),
                     join=tuple(dict(entry) for entry in data['join']))


def pick(paths, era):
  """The model of `era` among the files `paths` (raises SampleModelError if no file or more than one is for it)."""
  models = [load_sample_model(path) for path in paths]
  found = [model for model in models if model.era == era]
  if len(found) != 1:
    raise SampleModelError(", ".join(paths), ["%s sample file(s) for era %r (eras: %s)"
                                              % ("no" if not found else len(found), era,
                                                 ", ".join(model.era for model in models) or "none")])
  return found[0]


def sample_names(model, channel):
  """(MC sample names in table order, data dataset pattern or None) a channel reads, without building anything."""
  kind = _data_kind(channel)
  return tuple(row['name'] for row in model.mc), model.data.get(kind) if kind else None


# =============================================================================
# ================================== RECORDS ==================================


@dataclass(frozen=True)
class SampleModel:
  """The samples of one era (see the format at the top of this file). path: absolute."""
  path:         str
  era:          str
  cme:          float
  extraweights: dict
  mc:           Tuple[dict, ...]
  data:         dict
  weights:      dict
  stitch:       Tuple[dict, ...] = ()
  join:         Tuple[dict, ...] = ()


class SampleModelError(ValueError):
  """A sample model file that cannot be used; .problems lists every problem."""

  def __init__(self, path, problems):
    self.path, self.problems = path, list(problems)
    ValueError.__init__(self, "%s: %s" % (path, "; ".join(self.problems)))


# =============================================================================
# ================================== HELPERS ==================================


def _data_kind(channel, LOG=None):
  """The data kind of a channel (samples_v15.py order); None, or LOG.throw, if none matches."""
  if   'tautau' in channel: return 'tautau'
  elif 'mutau'  in channel or 'mumu' in channel: return 'muon'
  elif 'etau'   in channel or 'ee' in channel: return 'electron'
  elif 'emu'    in channel: return 'emu'
  if LOG is not None:
    LOG.throw(IOError,"Did not recognize channel %r!"%(channel))
  return None


def _weight_kind(channel):
  if 'mutau' in channel or 'etau' in channel:
    return 'semileptonic'
  elif channel in ['tautau','ditau']:
    return 'ditau'
  return 'other'


def _kind_value(model, field, kind, channel, LOG):
  """The model's value of a channel kind; LOG.throw if the file has none (an era where samples_v15.py failed)."""
  values = getattr(model, field)
  if kind not in values:
    LOG.throw(IOError,"Sample model %s has no %s for channel %r (kind %r)!"%(model.path,field,channel,kind))
  return values[kind]


def _problems(data):
  """Every problem of a parsed sample model file (empty: valid)."""
  if not isinstance(data, dict):
    return ["a sample model is a mapping with the keys %s" % (", ".join(KEYS))]
  problems = []
  header = data.get(HEADER_KEY)
  if isinstance(header, dict) and header.get('schema') != SCHEMA:
    problems.append("%s.schema is %r: this reader understands schema %d" % (HEADER_KEY, header.get('schema'), SCHEMA))
  unknown = sorted(set(data) - set(KEYS) - {HEADER_KEY})
  if unknown:
    problems.append("unknown key(s) %s (known: %s)" % (", ".join(map(str, unknown)), ", ".join(KEYS)))
  missing = [key for key in KEYS if key not in data]
  if missing:
    return problems + ["missing key(s) %s" % (", ".join(missing))]
  if not isinstance(data['era'], str) or not data['era']:
    problems.append("era must be a text, e.g. '2025' (quoted)")
  if not isinstance(data['cme'], (int, float)) or isinstance(data['cme'], bool):
    problems.append("cme must be a number")
  extraweights = data['extraweights']
  if not isinstance(extraweights, dict) or not all(isinstance(v, str) for v in extraweights.values()):
    problems.append("extraweights must map names to weights")
    extraweights = {}
  if not isinstance(data['mc'], list) or not data['mc']:
    problems.append("mc must be a non-empty list")
  else:
    for index, row in enumerate(data['mc']):
      problems.extend("mc[%d]: %s" % (index, problem) for problem in _row_problems(row, extraweights))
  for field, kinds in (('data', DATA_KINDS), ('weights', WEIGHT_KINDS)):
    value = data[field]
    if not isinstance(value, dict) or set(value) - set(kinds) or not all(isinstance(v, str) for v in value.values()):
      problems.append("%s must map channel kinds (%s) to texts" % (field, ", ".join(kinds)))
  for field, keys in (('stitch', ('pattern', 'incl', 'name')), ('join', ('patterns', 'name'))):
    value = data[field]
    if not isinstance(value, list) or not all(isinstance(entry, dict) and sorted(entry) == sorted(keys)
                                               for entry in value):
      problems.append("%s must be a list of {%s}" % (field, ", ".join(keys)))
  return problems


def _row_problems(row, extraweights):
  if not isinstance(row, dict):
    return ["must be a mapping {%s}" % (", ".join(MC_KEYS))]
  problems = []
  unknown = sorted(set(row) - set(MC_KEYS))
  if unknown:
    problems.append("unknown key(s) %s" % (", ".join(map(str, unknown))))
  for key in ('group', 'name', 'title'):
    if not isinstance(row.get(key), str):
      problems.append("%s must be a text" % (key))
  if not isinstance(row.get('xsec'), (int, float)) or isinstance(row.get('xsec'), bool):
    problems.append("xsec must be a number")
  if 'extraweight' in row and row['extraweight'] not in extraweights:
    problems.append("extraweight %r is not a key of extraweights" % (row['extraweight'],))
  return problems
