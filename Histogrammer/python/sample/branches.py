# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Branches: the pico tuple branches a channel setup and a sample model read, against the branches of the tuple files
(docs/contracts/pico-tuples.md). Used by the preflights of ControlHists and TESShapes, so that a missing branch stops
a run before it starts instead of an RDataFrame error hours into it.

    setup_branches(setup)                       ─▶ names in the cuts (ROOT-free)
    weight_branches(model, channel, row)        ─▶ names in the MC weight of one sample (ROOT-free)
    tuple_branches(path)                        ─▶ branches and aliases of a tuple file (ROOT, only the header)
    branch_problems(setup, model, era, tuples)  ─▶ problems (empty: every existing tuple file has what is read)

Read from a setup (fillhists.py channel setup or TES/ID fit config): baselineCuts, regions.*.definition, the
observable names and observables.*.extra.cut, the samples.split cuts (MC only), tagger.vsjet.discriminant (put in at
the $VSJET placeholder). From the sample model: the MC weight of the channel kind and the sample's extra weight; the
names in samples.removeSFs and the removed tau ID SFs are not needed. Not read: variables defined in Python, weights
given on the command line, the variation tuples.

Public API:
  setup_branches(setup), weight_branches(model, channel, row), tuple_branches(path), branch_problems(...)
"""
import glob
import os
import re

from TauFW.Histogrammer.sample import model as sample_model

__all__ = ['setup_branches', 'weight_branches', 'tuple_branches', 'branch_problems']


# =============================================================================
# ================================= CONSTANTS =================================


IDENTIFIER   = re.compile(r"(?<![\w.$])([A-Za-z_]\w*)(?!\w|\s*\()")  # names; not functions, members, $PLACEHOLDERS
NOT_BRANCHES = {'true', 'false', 'TMath'}


# =============================================================================
# ================================= BRANCHES ==================================


def names(expression):
  """The branch (or alias) names an expression reads."""
  return set(IDENTIFIER.findall(expression or "")) - NOT_BRANCHES


def setup_branches(setup, mc=True):
  """Names in the cuts of a channel setup or fit config; mc: with the cuts that split MC samples (genmatch)."""
  expressions = [setup.get('baselineCuts')]
  expressions += [(region or {}).get('definition') for region in (setup.get('regions') or {}).values()]
  for observable, spec in (setup.get('observables') or {}).items():
    expressions += [observable, ((spec or {}).get('extra') or {}).get('cut')]
  expressions += [((setup.get('tagger') or {}).get('vsjet') or {}).get('discriminant')]
  if mc:
    expressions += [cut for parts in ((setup.get('samples') or {}).get('split') or {}).values() for _, cut in parts]
  return set().union(*(names(expression) for expression in expressions))


def weight_branches(model, channel, row, removed=()):
  """Names in the MC weight of one sample (a row of model.mc): the channel kind's weight and the row's extra weight,
  without the removed scale factors."""
  weight = model.weights.get(sample_model._weight_kind(channel), "")
  extra = model.extraweights.get(row.get('extraweight'), "")
  return (names(weight) | names(extra)) - set(removed)


def tuple_branches(path):
  """The branches and aliases of the tree 'tree' of a tuple file (reads the header only), or None if the file cannot
  be opened or ROOT cannot be imported (left to the other checks)."""
  try:
    import ROOT
  except ImportError:
    return None
  try:
    file = ROOT.TFile.Open(path)
  except OSError:  # PyROOT 6.30 raises instead of returning a null file
    return None
  if not file or file.IsZombie():
    return None
  try:
    tree = file.Get('tree')
    if not tree:
      return None
    found = {branch.GetName() for branch in tree.GetListOfBranches()}
    aliases = tree.GetListOfAliases()
    if aliases:
      found |= {alias.GetName() for alias in aliases}
    return found
  finally:
    file.Close()


def branch_problems(setup, model, era, tuples, removed=(), read=None, config=None, maxshow=3):
  """The tuple files of a channel and era (tuple pattern with $ERA, $GROUP; the sample model's samples) that lack a
  branch the setup or the sample model reads: one problem per set of missing branches (empty: none). Files that do
  not exist or cannot be read are left to the other checks. removed: scale factors taken out of the weight."""
  read = read or tuple_branches
  channel = setup['channel']
  removed = set(removed) | set((setup.get('samples') or {}).get('removeSFs') or [])
  cuts_mc, cuts_data = setup_branches(setup) - removed, setup_branches(setup, mc=False)
  files = [(_tuple_file(tuples, era, row['group'], row['name'], channel),
            cuts_mc | weight_branches(model, channel, row, removed)) for row in model.mc]
  _, data = sample_model.sample_names(model, channel)
  if data:
    files += [(path, cuts_data) for path in sorted(glob.glob(_tuple_file(tuples, era, 'Data', data, channel)))]
  missing = {}
  for path, wanted in files:
    if not os.path.isfile(path):
      continue
    found = read(path)
    if found is None:
      continue
    lacking = tuple(sorted(wanted - found))
    if lacking:
      missing.setdefault(lacking, []).append(os.path.basename(path))
  name = config or channel
  problems = []
  for lacking, paths in missing.items():
    shown = ", ".join(paths[:maxshow]) + (", ..." if len(paths) > maxshow else "")
    problems.append("%d tuple file(s) of %s, era %s, lack branch(es) the config reads: %s (%s)"
                    % (len(paths), name, era, ", ".join(lacking), shown))
  return tuple(problems)


def _tuple_file(tuples, era, group, sample, channel):
  """$PICODIR/$SAMPLE_$CHANNEL.root with $PICODIR the tuple pattern (the keys replaced as plain text)."""
  directory = tuples.replace('$ERA', era).replace('$GROUP', group)
  return os.path.join(directory, "%s_%s.root" % (sample, channel))
