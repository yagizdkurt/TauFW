"""Contract: pico tuples (Docs/Develop/contracts/pico-tuples.md), without ROOT. Both sides are read as text: the PicoProducer's
tree producers, channel modules and merge step, the Histogrammer's Sample and stitching code, and the configs that
name branches (Configs/ and the bundle copies in Analyses/). Nothing is imported from either module.

What is checked:
- names: tree 'tree', cutflow 'cutflow', file <sample>_<channel><tag>.root on both sides;
- cutflow bins: the bins the PicoProducer's channel modules fill equal the bins the Histogrammer reads
  (nevents 1, sumw 17, DY stitching 17-23);
- branches: every branch a config reads (cuts, regions, observables, splits, removed SFs, MC weights, extra
  weights) is written by the channel's tree producer, or added by the analysis add-on of the 2025 campaign
  (ANALYSIS_ADDON, eras ADDON_ERAS only), or listed in KNOWN_DEBT.
KNOWN_DEBT and MODULES_WITHOUT_STITCH_BINS must match exactly: a fixed entry fails until it is removed here."""
import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
ANALYSIS = REPO / "PicoProducer" / "python" / "analysis"
SAMPLE = REPO / "Histogrammer" / "python" / "sample"
LEGACY = REPO / "Legacy" / "OldAnalysis"

TREE, CUTFLOW = "tree", "cutflow"

# The cutflow bins of the contract: cut name of the PicoProducer's channel modules -> ROOT bin (cut index + 1)
CUTFLOW_BINS = {
    'none':                        1,  # events processed, unweighted (Sample.binnevts)
    'weight':                      16, # sum of genWeight
    'weight_no0PU':                17, # sum of genWeight with nTrueInt>0: the normalisation (Sample.binsumw)
    'weight_mutaufilter':          18, # DY stitching: sum of genWeight passing the gen mutau filter
    'weight_mutaufilter_NUP0orp4': 19, # ... and LHE_Njets 0 or >4
    'weight_mutaufilter_NUP1':     20,
    'weight_mutaufilter_NUP2':     21,
    'weight_mutaufilter_NUP3':     22,
    'weight_mutaufilter_NUP4':     23,
}
STITCH_CUTS = [name for name in CUTFLOW_BINS if name.startswith('weight_mutaufilter')]

# Config channel -> tree producer (PicoProducer/python/analysis/<name>.py); the channel module that writes it is
# chosen in the user's PicoProducer config, so the contract fixes the producer per channel
CHANNEL_PRODUCERS = {
    'mutau':          'TreeProducerMuTau',
    'etau':           'TreeProducerETau',
    'etau_inclusive': 'TreeProducerETau',
    'mumu':           'TreeProducerMuMu',
    'ee':             'TreeProducerMuMu',
    'emu':            'TreeProducerEMu',
    'tautau':         'TreeProducerTauTau',
}
# The channels a sample model's MC weight kind is used for (Histogrammer sample/model.py _weight_kind)
WEIGHT_KIND_CHANNELS = {
    'semileptonic': ('mutau', 'etau'),
    'ditau':        ('tautau',),
    'other':        ('mumu', 'ee', 'emu'),
}

# Analysis add-on of the 2025 campaign: branches added after production to the MC tuples of
# /eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/2025 (2024 MC used for the 2025 and 2026 data) by
# the scripts in Legacy/OldAnalysis. branch -> (script, channels whose files have it; None: every channel)
PILEUP = "2025-2026/add_pileup_weights.py"
MUON = "2025/add_muon_weights.py"
ANALYSIS_ADDON = dict(
    [("puweight_2025_%s%s" % (xsec, version), (PILEUP, None))
     for xsec in ('66p0168', '69p2', '72p3832', '80p0') for version in ('', '_v2', '_v3')] +  # '' and _v3: older runs
    [("puweight_2026_69p2", (PILEUP, None)), ("puweight_2025_2026_69p2", (PILEUP, None)),
     ("idisoweight_1_2025", (MUON, ('mutau', 'mumu'))), ("trigweight_2025", (MUON, ('mutau', 'mumu'))),
     ("idisoweight_2_2025", (MUON, ('mumu',)))])
ADDON_ERAS = ('2025', '2026', '2526')  # the sample model eras that read the campaign's tuples

# Branches the configs read that their channel's tuples do not have, documented in Docs/Develop/contracts/pico-tuples.md
# ("Known debt"): (config file names, the same in Configs/ and in bundle copies), channels, branches. Remove a row
# when the config is fixed.
OLD_ERAS = ('v15_2022_preEE.yml', 'v15_2022_postEE.yml', 'v15_2023C.yml', 'v15_2023D.yml', 'v15_2024.yml')
CAMPAIGN_ERAS = ('v15_2025.yml', 'v15_2026.yml', 'v15_2526.yml')
KNOWN_DEBT = [
    # weights.other of every era uses the names of the 2025 add-on (samples_v15.py:281-284)
    (OLD_ERAS, ('mumu', 'ee', 'emu'),
     {'puweight_2025_69p2_v3', 'idisoweight_1_2025', 'trigweight_2025', 'idisoweight_2_2025'}),
    # weights.other and weights.semileptonic of the campaign eras: the muon SFs of the add-on in electron channels
    (CAMPAIGN_ERAS, ('ee', 'emu'), {'idisoweight_1_2025', 'trigweight_2025', 'idisoweight_2_2025'}),
    (CAMPAIGN_ERAS, ('etau',), {'idisoweight_1_2025', 'trigweight_2025'}),
    # the baseline of a mumu setup (muon IDs): no such branches in tautau
    (('setup_tautau.yml',), ('tautau',), {'idMedium_1', 'idMedium_2'}),
    # PNet regions: TreeProducerETau writes no PNet branches (TreeProducerMuTau does)
    (('setup_etau_inclusive.yml',), ('etau_inclusive',),
     {'decayModePNet_2', 'rawPNetVSe_2', 'rawPNetVSjet_2', 'rawPNetVSmu_2'}),
]
# Channel modules without the DY stitching bins 18-23: ModuleTauPair.fillhists fills them for DY files (domutau),
# where Cutflow.fill would stop on the unknown cut
MODULES_WITHOUT_STITCH_BINS = {'ModuleEMu.py', 'ModuleETau.py', 'ModuleTauTau.py'}

IDENTIFIER = re.compile(r"(?<![\w.$])([A-Za-z_]\w*)(?!\w|\s*\()")  # names; not functions, members, $PLACEHOLDERS
NOT_BRANCHES = {'true', 'false', 'TMath'}


def text(path):
    return path.read_text(encoding="utf-8")


def read(path):
    with open(str(path), encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def names(expression):
    """The branch (or alias) names an expression reads."""
    return set(IDENTIFIER.findall(expression)) - NOT_BRANCHES


def producer_branches(name):
    """Branches and aliases a tree producer and its base classes write (every addBranch/setAlias, conditions
    ignored: the MC/nominal superset)."""
    source = text(ANALYSIS / (name + ".py"))
    found = set(re.findall(r"self\.(?:addBranch|setAlias)\(\s*['\"](\w+)['\"]", source))
    base = re.search(r"class %s\((\w+)\)" % name, source).group(1)
    return found | (producer_branches(base) if base.startswith('TreeProducer') and base != 'TreeProducer' else set())


def channel_modules():
    """The channel modules (subclasses of ModuleTauPair): path -> source."""
    paths = sorted(ANALYSIS.glob("Module*.py")) + sorted((ANALYSIS / "Run3_DEV").glob("Module*.py"))
    return {path: text(path) for path in paths if re.search(r"class \w+\(ModuleTauPair\)", text(path))}


def addcuts(source):
    """Cut name -> ROOT bin of a module's cutflow (Cutflow.addcut: the next free index unless given; bin = index+1)."""
    bins, index = {}, 0
    for name, given in re.findall(r"^\s*self\.out\.cutflow\.addcut\(\s*'(\w+)'\s*,\s*\"[^\"]*\"\s*(?:,\s*(\d+))?",
                                  source, re.M):
        if given:
            bins[name] = int(given)+1
        else:
            bins[name] = index+1
            index += 1
    return bins


def configs():
    """The configs that name pico tuple branches: (path, kind, data) with kind setup, fit or samples."""
    kinds = (('histogrammer.setup_', 'setup'), ('fitter.tes_id', 'fit'), ('histogrammer.samples_', 'samples'))
    found = []
    for path in sorted(REPO.glob("Configs/**/*.yml")) + sorted(REPO.glob("Analyses/*/*.yml")):
        data = read(path)
        ident = (data or {}).get('taufw_config', {}).get('id', '') if isinstance(data, dict) else ''
        for prefix, kind in kinds:
            if ident.startswith(prefix):
                found.append((path, kind, data))
    return found


def config_reads(kind, data):
    """channel -> branch names a config reads."""
    if kind == 'samples':
        extra = set().union(*(names(w) for w in data['extraweights'].values()))
        reads = {}
        for weight_kind, weight in data['weights'].items():
            for channel in WEIGHT_KIND_CHANNELS[weight_kind]:
                reads[channel] = names(weight) | extra
        return reads
    expressions = [data.get('baselineCuts') or ""]
    expressions += [region.get('definition') or "" for region in (data.get('regions') or {}).values()]
    for observable, spec in (data.get('observables') or {}).items():
        expressions += [observable, ((spec or {}).get('extra') or {}).get('cut') or ""]
    samples = data.get('samples') or {}
    expressions += [cut for parts in (samples.get('split') or {}).values() for _, cut in parts]
    expressions += samples.get('removeSFs') or []
    expressions += [((data.get('tagger') or {}).get('vsjet') or {}).get('discriminant') or ""]
    return {data['channel']: set().union(*(names(e) for e in expressions))}


class NamesTests(unittest.TestCase):
    def test_tree_and_cutflow_names(self):
        self.assertIn("self.tree      = TTree('%s','%s')" % (TREE, TREE), text(ANALYSIS / "TreeProducer.py"))
        self.assertIn("TH1D('%s','%s'" % (CUTFLOW, CUTFLOW), text(ANALYSIS / "Cutflow.py"))
        sample = text(SAMPLE / "Sample.py")
        self.assertIn("kwargs.get('tree',         None         ) or '%s'" % TREE, sample)
        self.assertIn("kwargs.get('cutflow',      '%s'    )" % CUTFLOW, sample)
        types = text(REPO / "PicoProducer" / "python" / "api" / "types.py")
        self.assertIn('tree:    str = "%s"' % TREE, types)
        self.assertIn('cutflow: str = "%s"' % CUTFLOW, types)

    def test_file_name(self):  # <sample>_<channel><tag>.root
        self.assertIn('outfile  = "%s_%s%s.root"%(sample.name,channel,tag)',
                      text(REPO / "PicoProducer" / "python" / "jobs" / "merge.py"))
        self.assertIn('kwargs.get(\'fname\', "$PICODIR/$SAMPLE_$CHANNEL$TAG.root" )', text(SAMPLE / "model.py"))


class CutflowTests(unittest.TestCase):
    def test_histogrammer_bins(self):
        sample = text(SAMPLE / "Sample.py")
        self.assertEqual(re.search(r"kwargs\.get\('binnevts',\s*None\s*\) or (\d+)", sample).group(1),
                         str(CUTFLOW_BINS['none']))
        self.assertEqual(re.search(r"kwargs\.get\('binsumw',\s*None\s*\) or (\d+)", sample).group(1),
                         str(CUTFLOW_BINS['weight_no0PU']))

    def test_stitching_bins(self):  # sample/utils.py stitch(): efficiencies of the mutau filter per LHE_Njets
        source = text(SAMPLE / "utils.py")
        for which in ('incl', 'mutau'):
            pairs = re.findall(r"cutflow_%s\.GetBinContent\((\d+)\) / cutflow_%s\.GetBinContent\((\d+)\)"
                               % (which, which), source)
            self.assertEqual(pairs, [(str(CUTFLOW_BINS[name]), str(CUTFLOW_BINS['weight_no0PU']))
                                     for name in STITCH_CUTS], which)

    def test_modules_fill_the_contract_bins(self):
        without = set()
        for path, source in channel_modules().items():
            bins = addcuts(source)
            self.assertEqual(min(bins, key=bins.get), 'none', path.name)
            for name in ('none', 'weight', 'weight_no0PU'):
                self.assertEqual(bins.get(name), CUTFLOW_BINS[name], "%s: %s" % (path.name, name))
            stitch = {name: bins[name] for name in STITCH_CUTS if name in bins}
            if stitch:
                self.assertEqual(stitch, {name: CUTFLOW_BINS[name] for name in STITCH_CUTS}, path.name)
            elif path.parent == ANALYSIS:
                without.add(path.name)
            else:
                without.add("%s/%s" % (path.parent.name, path.name))
        self.assertEqual(without, MODULES_WITHOUT_STITCH_BINS)

    def test_base_module_fills_these_cuts(self):
        source = text(ANALYSIS / "ModuleTauPair.py")
        body = source[source.index("def fillhists("):]
        body = body[:body.index("\n  def ", 1)]
        self.assertEqual(set(re.findall(r"cutflow\.fill\('(\w+)'", body)), set(CUTFLOW_BINS))


class ProductionRecordTests(unittest.TestCase):  # CL §36: the TupleArtifact of the production stage
    def test_kind_on_both_sides(self):
        types = text(REPO / "PicoProducer" / "python" / "api" / "types.py")
        record = types[types.index("class TupleArtifact("):types.index("class MergeReport(")]
        self.assertIn('kind:    str = "tuples"', record)
        stages = REPO / "Framework" / "python" / "stages"
        self.assertIn("outputs = ('tuples',)", text(stages / "production.py"))
        self.assertIn("return ({'kind': self.outputs[0], 'pattern': pattern},)", text(stages / "production.py"))
        for reader in ("controlhists.py", "shapes.py"):
            self.assertIn("inputs = {'tuples': 'tuples'}", text(stages / reader))
        self.assertIn("context.input_artifacts(slot, kind=self.inputs[slot])", text(stages / "local.py"))

    def test_sumw_is_the_normalisation_bin(self):
        merge = text(REPO / "PicoProducer" / "python" / "jobs" / "merge.py")
        self.assertEqual(re.search(r"^SUMW_BIN\s*=\s*(\d+)", merge, re.M).group(1),
                         str(CUTFLOW_BINS['weight_no0PU']))
        self.assertIn("nevents=result.status.nprocevents,sumw=result.sumw",
                      text(REPO / "PicoProducer" / "python" / "api" / "producer.py"))


class BranchTests(unittest.TestCase):
    def test_channel_modules_use_the_contract_producer(self):
        for path, source in channel_modules().items():
            channel = re.sub(r"_(Inclusive|nanoV10_DeepTau2p5)$", "", path.stem[len("Module"):]).lower()
            self.assertEqual(re.findall(r"import (TreeProducer\w+)", source), [CHANNEL_PRODUCERS[channel]], path.name)

    def test_addon_matches_the_scripts(self):  # every branch the scripts write is in the add-on list
        pileup = text(LEGACY / PILEUP)
        written = set(re.findall(r"'(puweight_\w+)'\),", pileup))
        written |= set(re.findall(r'NEW_BRANCH_\w+\s*=\s*"(\w+)"', text(LEGACY / MUON)))
        self.assertTrue(written)
        self.assertEqual(written - set(ANALYSIS_ADDON), set())

    def test_configs_read_written_branches(self):
        missing = {}
        for path, kind, data in configs():
            era = str(data.get('era', '')) if kind == 'samples' else None
            for channel, reads in config_reads(kind, data).items():
                written = producer_branches(CHANNEL_PRODUCERS[channel])
                for name in sorted(reads - written):
                    script, channels = ANALYSIS_ADDON.get(name, (None, None))
                    addon = script and (era is None or era in ADDON_ERAS) and (channels is None or channel in channels)
                    if not addon:
                        missing.setdefault((path.name, channel), set()).add(name)
        debt = {(config, channel): branches for files, channels, branches in KNOWN_DEBT
                for config in files for channel in channels}
        self.assertEqual(missing, debt)


if __name__ == "__main__":
    unittest.main()
