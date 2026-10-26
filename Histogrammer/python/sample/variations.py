# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Variation tuples: which samples createinputsTES.py reads from a shifted tuple file, without ROOT.

A TES point and a shape systematic with `sampleAppend` make a shifted copy of the sample set
(SampleSet.shift -> Sample.appendfilename): every sample of a matched process reads
<sample>_<channel><filetag>.root next to its nominal tuple, e.g. DYto2Tau_Bin-MLL-50to120_mutau_TES0p950.root.
The file is opened only when the shifted set is made, after the nominal histograms (hours into a run), so a missing
one fails late (Docs/Develop/contracts/tes-shapes.md, "Variation tuples"). This module names the files beforehand, for the
preflight of TauFW.Histogrammer.api.TESShapes.

    variations(setup, model, era) ─▶ (Variation(tag, label, samples), ...)   in the order the script shifts

It replays what createinputsTES.py does to the sample set, on names only:
  1. model.getsampleset() with split=[] and the config's samples.join: the model's stitching, the DY join, the
     model's joins, then VV, TT, ST, Top as samples.join asks (the order of model.py);
  2. the config's samples.split and samples.rename (SampleSet.split/rename: the first top-level sample that matches);
  3. per TES value (TESvariations.processes) and per shape systematic with sampleAppend (its processes): a top-level
     sample whose own labels or one of whose split parts match the processes is shifted, and with it every MC sample
     in it (a merged sample shifts all its samples, a split part is a copy of the whole sample).
Matching is the sample code's own (TauFW.Utilities.Drawing.labels.match: glob, substring, any term), on the labels
known without ROOT: the name of every sample and the title of a sample model row. The titles that the sample code
takes from SampleStyle (merged samples, split parts with two fields) are not known here; a process found only through
such a title is missed (no false alarm, the run fails late as before). Tests/tools/check_variation_files.py compares
this with the real SampleSet on lxplus. Data are never shifted (filter=False shares the data sample).

Public API:
  variations(setup, model, era) -> tuple of Variation
  Variation(tag, label, samples)    samples: ((group, name), ...) of the model rows, in model order
"""
from dataclasses import dataclass
from typing import Tuple

from TauFW.Utilities.Drawing.labels import match

__all__ = ['variations', 'Variation']


# =============================================================================
# ================================= RECORDS ===================================


@dataclass(frozen=True)
class Variation:
  """One shifted sample set: the file tag (e.g. '_TES0p950', '_LTF1p030'), a label for messages ('TES 0.950',
  'LTF Up') and the model rows whose tuple file gets the tag."""
  tag:     str
  label:   str
  samples: Tuple[Tuple[str, str], ...]


# =============================================================================
# =============================== VARIATIONS ==================================


def variations(setup, model, era):
  """The shifted sample sets of one channel config (createinputsTES.py's YAML, a dict) for the sample model of an era
  (TauFW.Histogrammer.sample.model.SampleModel), in the script's order: the TES values, then the shape systematics.
  A systematic without sampleAppend (or with an empty one) reads the nominal files and is left out."""
  samples = setup.get('samples') or {}
  units = _sampleset(model, era, samples.get('join') or [])
  for name, parts in (samples.get('split') or {}).items():  # SampleSet.split
    unit = _find(units, name)
    if unit is not None:
      unit.splits = [_Unit(part[0], part[1] if len(part) >= 3 else None, unit.rows) for part in parts]
  for old, new in (samples.get('rename') or {}).items():  # SampleSet.rename
    unit = _find(units, old)
    if unit is not None:
      unit.name = new
  shifts = []
  tes = setup.get('TESvariations')
  if tes:
    for value in tes['values']:
      shifts.append((("_TES%.3f" % value).replace(".", "p"), "TES %.3f" % value, tes['processes']))
  for key, syst in (setup.get('systematics') or {}).items():
    if syst.get('effect') != 'shape' or 'sampleAppend' not in syst:
      continue
    for index, variation in enumerate(syst['variations']):
      shifts.append((syst['sampleAppend'][index], "%s %s" % (key, variation), syst['processes']))
  result = []
  for tag, label, processes in shifts:
    if not tag:
      continue
    rows = [row for unit in units if _shifted(unit, processes) for row in unit.rows]
    order = {(row['group'], row['name']): index for index, row in enumerate(model.mc)}
    names = sorted(dict.fromkeys((row['group'], row['name']) for row in rows), key=order.get)
    result.append(Variation(tag, label, tuple(names)))
  return tuple(result)


# =============================================================================
# =============================== SAMPLE SET ==================================


class _Unit:
  """A top-level sample of the replayed sample set: its name, title (None: from SampleStyle, unknown), the model rows
  in it and its split parts (units with the same rows)."""

  def __init__(self, name, title, rows):
    self.name, self.title, self.rows, self.splits = name, title, list(rows), []

  def match(self, terms):
    """Sample.match(*terms) (a new list: match() rewrites the terms it is given into regular expressions)."""
    return match(list(terms), [self.name] + ([self.title] if self.title else []), incl=True)

  def __repr__(self):
    return "<_Unit(%r, %d rows)>" % (self.name, len(self.rows))


def _sampleset(model, era, join):
  """The top-level samples after model.getsampleset(channel, era, model, join=join, split=[]): stitch, then the joins
  in model.py's order."""
  units = [_Unit(row['name'], row['title'], [row]) for row in model.mc]
  for stitch in model.stitch:
    units = _stitch(units, era, stitch['pattern'], stitch['incl'], stitch['name'])
  units = _join(units, ['DY'], 'DY')
  for extra in model.join:
    units = _join(units, extra['patterns'], extra['name'])
  if 'VV' in join:
    units = _join(units, ['VV', 'WZ', 'WW', 'ZZ'], 'VV')
  if 'TT' in join and era != 'year':
    units = _join(units, ['TT'], 'TT')
  if 'ST' in join:
    units = _join(units, ['ST'], 'ST')
  if 'Top' in join:
    units = _join(units, ['TT', 'ST'], 'Top')
  return units


def _join(units, terms, name):
  """sample/utils.py join() on a list: the matching samples become one merged sample, placed where the list code puts
  it (the index of the last one removed, as the code does)."""
  merge = [unit for unit in units if unit.match(terms)]
  if len(merge) <= 1:
    return units
  merged = _Unit(name, None, [row for unit in merge for row in unit.rows])
  units = list(units)
  index = len(units)
  for unit in merge:
    index = units.index(unit)
    units.remove(unit)
  units.insert(index, merged)
  return units


def _stitch(units, era, pattern, incl, name):
  """sample/utils.py stitch(): a join if at least two samples match and the inclusive sample is among them (by name
  for the 2022-2024 eras, else by pattern; a DYJets*MuTau sample does not count)."""
  found = [unit for unit in units if unit.match([pattern])]
  if len(found) < 2:
    return units
  if "2022" in era or "2023" in era or "2024" in era:
    inclusive = [unit for unit in found if unit.name == incl]
  else:
    inclusive = [unit for unit in found if unit.match([incl])]
  if not [unit for unit in inclusive if not unit.match(["DYJets*MuTau"])]:
    return units
  return _join(units, [pattern], name)


def _find(units, term):
  """findsample(..., unique=True): the first top-level sample that matches (None if none)."""
  return next((unit for unit in units if unit.match([term])), None)


def _shifted(unit, processes):
  """SampleSet.shift(processes, ..., split=True): the sample or one of its split parts matches."""
  return unit.match(processes) or any(part.match(processes) for part in unit.splits)
