# Contract: pico tuples (PicoProducer -> Histogrammer)

Written by the **PicoProducer** (`pico.py run/submit` + `hadd`, the Framework's `production` stage), read by the
**Histogrammer** (`fillhists.py`, `TauFW.Histogrammer.controlhists`, the TES shapes, `createinputsTES.py`) through the
sample model (`Configs/Histogrammer/samples/`) and the channel setups. The two modules never import each other; this
page and the configs are all they share. Introduced in changelog §35 (plan 22, C2); the production record in §36
(C3).

The file itself carries no version and no metadata: this page writes down the format the Histogrammer has read for
years. Changing anything below means changing both sides together. Checked without ROOT by
`Tests/contracts/test_pico_tuples.py` (in `python3 Tests/run.py checks`, case `unit.contracts`).

## File

One ROOT file per sample, channel and tag, made by `hadd` of the job outputs:

```
<tupledir>/<era>/<group>/<sample>_<channel><tag>.root
```

| Part | Value |
|---|---|
| `<tupledir>` | the PicoProducer's `picodir` (`pico.py`), or `<run>/stages/<id>` of a production stage |
| `<era>/<group>` | `TUPLE_LAYOUT` `$ERA/$GROUP` (`PicoProducer/python/jobs/merge.py`) |
| `<sample>_<channel><tag>` | `merge.py` `"%s_%s%s.root"%(sample.name,channel,tag)`; the Histogrammer's pattern `$PICODIR/$SAMPLE_$CHANNEL$TAG.root` (`sample/model.py`, `fillhists.py`) |
| `<tag>` | empty for the nominal tuple; a variation's tag (below) |

Example: `2025/DY/DYto2Tau_Bin-MLL-50to120_mutau.root`, its TES variation `..._mutau_TES0p950.root`.

In a recipe the production stage reports each file in a production record (below); the reading stages get the
directory pattern from it, or from the recipe (`inputs.tuples: {external: <pattern>}`).

## Inside

| Object | Name | Read by |
|---|---|---|
| tree | `tree` (`TreeProducer`: `TTree('tree','tree')`) | `Sample` (`tree` option, default `tree`) |
| cutflow | `cutflow` (`Cutflow`: `TH1D('cutflow','cutflow',ncuts,0,ncuts)`, 25 bins) | `Sample.setnevents` (`cutflow` option), DY stitching |
| pileup | `pileup` (`Pileup_nTrueInt` of the MC) | not read by the Histogrammer (pileup profiles) |

### Cutflow bins

A channel module declares its cuts with `Cutflow.addcut(name, title, index)`; cut index `i` is ROOT bin `i+1`.
`ModuleTauPair.fillhists` fills the bins below before any selection; bins 2-15 are the channel's own selection
steps (trigger, muon, tau, pair, ...), information only.

| Bin | Cut (index) | Content | Read by |
|---|---|---|---|
| 1 | `none` (0) | events processed, unweighted | `Sample.binnevts` (default 1): `nevents` |
| 16 | `weight` (15) | sum of `genWeight` (data: event count) | not read |
| **17** | `weight_no0PU` (16) | sum of `genWeight` of the events with `Pileup_nTrueInt>0` | **`Sample.binsumw` (default 17): `sumw`, the MC normalisation `lumi x xsec / sumw`** |
| 18 | `weight_mutaufilter` (17) | sum of `genWeight` of the events passing the generator mutau filter | DY stitching (`sample/utils.py` `stitch`): mutau efficiency = bin 18 / bin 17 |
| 19-23 | `weight_mutaufilter_NUP0orp4`, `_NUP1` ... `_NUP4` (18-22) | the same, by `LHE_Njets` (0 or >4, 1, 2, 3, 4) | DY stitching: per jet bin, bin / bin 17 |

Bins 18-23 are filled only for files whose name contains `DY` (`domutau`). Since the job outputs are added by `hadd`,
every bin is the sum over the jobs.

**Any step that makes a new tuple from a pico tuple** (a skim, a reader of job outputs without `hadd`, a
post-processing step) must carry the `cutflow` histogram over unchanged and summed over all its inputs; otherwise
`nevents`, `sumw` and the stitching are wrong without any error. The add-on scripts below open the files in
`UPDATE` mode and leave the cutflow as it is.

### Branches

Every branch is written by the channel's **tree producer** (`PicoProducer/python/analysis/TreeProducer<Channel>.py`
and its base classes, `addBranch`/`setAlias`). Which channel module makes a channel's tuples is chosen in the user's
PicoProducer configuration (`channels:`), so the contract fixes the tree producer per channel:

| Channel (the setups' `channel`) | Tree producer | Channel modules using it |
|---|---|---|
| `mutau` | `TreeProducerMuTau` | `ModuleMuTau`, `ModuleMuTau_nanoV10_DeepTau2p5`, `Run3_DEV/ModuleMuTau`, `Run3_DEV/ModuleMuTau_Inclusive` |
| `etau`, `etau_inclusive` | `TreeProducerETau` | `ModuleETau`, `Run3_DEV/ModuleETau`, `Run3_DEV/ModuleETau_Inclusive` |
| `mumu` | `TreeProducerMuMu` | `ModuleMuMu`, `Run3_DEV/ModuleMuMu` |
| `ee` | `TreeProducerMuMu` | `Run3_DEV/ModuleEE` |
| `emu` | `TreeProducerEMu` | `ModuleEMu` |
| `tautau` | `TreeProducerTauTau` | `ModuleTauTau` |

What the Histogrammer reads, per config:

| Config | Branches in |
|---|---|
| channel setups (`Configs/Histogrammer/setups/`, bundle copies) | `baselineCuts`, `regions.*.definition` |
| TES/ID fit configs (`Configs/Fitter/tes_id/`, bundle copies) | the above, the observable names, `observables.*.extra.cut`, `samples.split` cuts, `samples.removeSFs`, `tagger.vsjet.discriminant` (put in at the `$VSJET` placeholder) |
| sample model (`Configs/Histogrammer/samples/`, bundle copies) | `weights` (by channel kind: `semileptonic` mutau/etau, `ditau` tautau, `other` mumu/ee/emu), `extraweights` (DY: `zptweight_nnlo`, TT: `ttptweight`) |

Branch names in these fields must be written by the channel's tree producer, or come from the analysis add-on of the
2025 campaign (below), or be listed as known debt. Not covered yet: the variables `fillhists.py` and the plotting
scripts define in Python, and the weights given on the command line.

The tree producer's branch set depends on the module options: MC-only branches (`ismc`: weights, generator
matching), `dotight` and `dosys` (below). The test takes the union (the nominal MC tuple).

## Variation tuples

Variations of the tau energy scale and the lepton/jet -> tau fake energy scales are separate productions of the same
samples with a module option and a tag:

```
pico.py ... -E tes=0.95 -t _TES0p950      ->  <sample>_<channel>_TES0p950.root
pico.py ... -E ltf=1.03 -t _LTF1p030      (also jtf=)
```

The tags the TES/ID fit reads follow from its config (`TESvariations.values`, `systematics.*.sampleAppend`);
`TauFW.Histogrammer.sample.variations` lists them (the shapes preflight, CL §23).

Any variation switches on `dotight` (`ModuleTauPair.py:51-54`): a tighter pre-selection (fewer events) and no
`trigweightUp/Down` or PDF weights (`if not module.dotight` in `TreeProducerTauPair`). `ltf=`, `jtf=` (and `tessys`)
also switch off `dosys`: no `idweightUp/Down_2`, `ltfweightUp/Down_2`, ... (`if self.module.dosys` in the channel's
tree producer); `tes=` keeps them. The fit reads a variation tuple
with the nominal MC weight of the sample model, so **that weight must use only branches written with `dotight` on and `dosys` off**
(today: `genweight`, `puweight*`, `trigweight*`, `idisoweight_1*`, `idweight_2`, `ltfweight_2`: all written
unconditionally for MC). Not checked by the test yet.

## Analysis add-on: the 2025 campaign

The 2025 and 2026 TES/ID analysis uses 2024 MC (`/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/2025`)
for the 2025 and 2026 data. Pileup and muon corrections for those data were added to the existing MC tuples after
production, by two scripts kept in `Legacy/OldAnalysis` (opened in `UPDATE` mode, missing branches added, the cutflow
untouched; hard-coded EOS and AFS paths). These branches are specific to that analysis, not part of what the
PicoProducer writes:

| Branch | Script | Files | Inputs |
|---|---|---|---|
| `puweight_2025_<xsec>`, `_v2`, `_v3` (xsec `66p0168`, `69p2`, `72p3832`, `80p0`) | `2025-2026/add_pileup_weights.py` | every MC file of `DY`, `ST`, `TT`, `VV`, `WJ` | data profiles `PicoProducer/data/pileup/Data_PileUp_2025_<xsec>.root`; MC profile `MC_PileUp_2025.root` (not in the repository) |
| `puweight_2026_69p2`, `puweight_2025_2026_69p2` | the same | the same | `Data_PileUp_2026_69p2.root`, `Data_PileUp_2025_2026_69p2.root` |
| `idisoweight_1_2025` (MediumID x TightPFIso), `trigweight_2025` (IsoMu24) | `2025/add_muon_weights.py` | every MC file, the muon at `pt_1`, `eta_1` | `PicoProducer/data/lepton/MuonPOG/Run2025/muon_Z.json.gz` |
| `idisoweight_2_2025` | the same | `*_mumu*` files, the muon at `pt_2`, `eta_2` | the same |

Open (asked to the group): the repository's copy of the pileup script writes the `_v2` names; the analysis reads
`puweight_2025_69p2_v3`, made by another version of the script. Also open: whether the TES/LTF/JTF variation files
and the 2026 tuples went through both scripts. See [docs/issues/2025-tuple-weight-branches.md](../issues/2025-tuple-weight-branches.md).

The sample models of the eras `2025`, `2026`, `2526` read these branches (`weights`); the test accepts them there,
for the channels the scripts made them for (pileup: all; muon SFs: mutau, mumu). Bringing the two scripts into the
repository as a weights step (TODO §0) would make them part of this contract.

## Known debt

Configs that read a branch their channel's tuples do not have (the test lists them in `KNOWN_DEBT`; a fixed entry
makes the test fail until it is removed there):

| Config | Channels | Branches | Why |
|---|---|---|---|
| `v15_2022_preEE.yml` ... `v15_2024.yml` (and the bundle copy `example_mutau_long/v15_2022_postEE.yml`) | mumu, ee, emu | `puweight_2025_69p2_v3`, `idisoweight_1_2025`, `trigweight_2025`, `idisoweight_2_2025` | `weights.other` of every era uses the 2025 add-on names (`samples_v15.py:281-284`, copied into the templates) |
| `v15_2025.yml`, `v15_2026.yml`, `v15_2526.yml` (and the bundle copy) | ee, emu | `idisoweight_1_2025`, `trigweight_2025`, `idisoweight_2_2025` | `weights.other`: the muon SFs of the add-on in electron channels |
| the same | etau | `idisoweight_1_2025`, `trigweight_2025` | `weights.semileptonic`: the muon SFs of the add-on for etau |
| `setup_tautau.yml` | tautau | `idMedium_1`, `idMedium_2` | the baseline of a mumu setup (muon IDs) |
| `setup_etau_inclusive.yml` | etau_inclusive | `decayModePNet_2`, `rawPNetVSe_2`, `rawPNetVSjet_2`, `rawPNetVSmu_2` | `TreeProducerETau` writes no PNet branches (`TreeProducerMuTau` does) |

Channel modules: `ModuleETau`, `ModuleTauTau` and `ModuleEMu` declare no bins 18-23, but `ModuleTauPair.fillhists`
fills them for files with `DY` in the name, where `Cutflow.fill` stops on the unknown cut (the `Run3_DEV` modules
declare them). The test lists them in `MODULES_WITHOUT_STITCH_BINS`.

## Production record

The PicoProducer API reports each merged tuple as a `TupleArtifact` (`PicoProducer/python/api/types.py`; `pico.merge()`
-> `MergeReport.artifacts`). In a TauFW recipe the production stage stores them as JSON in `run.json` and in
`stages/<id>/manifest.json`, with the directory pattern added; the stages that read tuples (`controlhists`, `shapes`,
python steps) see them as their input. The PicoProducer API owns this schema (decision K4 of plan 22); it is not
written into the ROOT file.

```json
{"path": "<run_dir>/stages/production/2025/DY/DYto2Tau_Bin-MLL-50to120_mutau.root",
 "sample": "DYto2Tau_Bin-MLL-50to120", "group": "DY", "era": "2025", "channel": "mutau", "tag": "", "dtype": "mc",
 "nevents": 1234567.0, "sumw": 9.87e11, "tree": "tree", "cutflow": "cutflow", "kind": "tuples",
 "pattern": "<run_dir>/stages/production/$ERA/$GROUP"}
```

| Field | Meaning |
|---|---|
| `kind` | always `"tuples"`: what a reader selects by. The production stage's `outputs`, the `tuples` input slot of `controlhists` and `shapes` (`Stage.inputs`), and `ctx.input(<slot>, kind='tuples')` in a python step use the same word |
| `path` | the merged tuple (the file name rule above) |
| `sample`, `group`, `era`, `channel`, `tag` | the sample (its PicoProducer name and group) and the production's era, channel and tag |
| `dtype` | `mc`, `data` or `embed` |
| `nevents` | processed events: cutflow bin 1 summed over the job outputs while their status is checked; `0` if the events were not counted (`checkevts` off) |
| `sumw` | cutflow bin 17 of the merged file, read right after `hadd` (`merge.py` `SUMW_BIN`). MC: the sum of `genWeight` of the events with `Pileup_nTrueInt>0`, the denominator of `lumi x xsec / sumw`. Data: the events with a primary vertex (not a normalisation). `null` if no merge ran (`clean` only, dry run) or the file could not be read |
| `tree`, `cutflow` | the names inside the file (`"tree"`, `"cutflow"`) |
| `pattern` | added by the Framework: the directory pattern of all tuples of the stage, `<stage dir>/$ERA/$GROUP`; the reading stages are given it as `--tuples` |

Before the tuples exist (`taufw.py plan`), the production stage gives the later stages one planned record,
`{"kind": "tuples", "pattern": "<run_dir>/stages/<id>/$ERA/$GROUP"}`.

Readers:
- The Framework's local stages (`LocalStage.tuple_artifacts`, `tuples_pattern`) read only records of kind `tuples`.
  Records without a `kind` (production runs before CL §36, read through `inputs.tuples: {path: ...}`) are refused:
  "the tuples of ... were recorded before their records had a kind (CL §36); start a new run, or name them with
  {external: <pattern>}".
- Nothing reads `sumw` yet: the Histogrammer still reads the normalisation from the file's cutflow
  (`Sample.setnevents`). It is the record of what a run produced, and the value a later hand-over of the tuples
  (inputs given, not found; a skim; reading without `hadd`) must carry over unchanged.
- The merge does not check `sumw` (a merged MC tuple with `sumw <= 0` is not refused): recording only.

Versions: before CL §36 the record had no `kind` and no `sumw`.

## Checked by

`Tests/contracts/test_pico_tuples.py` (no ROOT, both sides read as text; nothing imported from either module):

- the names `tree`, `cutflow` and the file name on both sides (tree producer, `Cutflow`, `Sample`, `TupleArtifact`,
  `merge.py`, `model.py`);
- the cutflow bins: every channel module's `addcut` indices against the table above; `Sample.binnevts`/`binsumw`; the
  bins of the DY stitching; the cuts `ModuleTauPair.fillhists` fills;
- the channel -> tree producer table against the channel modules' imports;
- every branch of the configs above (`Configs/` and `Analyses/*/`) against the tree producer, the add-on and the
  known debt; the add-on list against the branch names in the two scripts;
- the production record: `TupleArtifact.kind` = the production stage's output = the readers' slot kind and filter;
  `merge.py` `SUMW_BIN` = the normalisation bin of the table above; the API passes the merge's `sumw` on.

The Framework's unit tests (`Tests/Framework/test_stages.py` `test_pattern_problems`, `test_framework.py`) check
the readers: only kind `tuples`, records without a kind refused, the planned record. BBB `framework.production`
records the run's tuple records as JSON.

The files themselves are checked before a run: the preflights of `ControlHists` and `TESShapes` (the `controlhists`
and `shapes` stages, `plan`/`start`) read the branch list of every existing nominal tuple file of the requested
samples (ROOT, the header only; `TauFW.Histogrammer.sample.branches`) and report the files that lack a branch the
setup or the sample model reads, one problem per config, era and set of missing branches. Only with a tuple pattern,
sample files and ROOT; the MC files are checked against the cuts (with the split cuts) and their weight (without
`removeSFs` and the SFs `-r` removes), the data files against the cuts. Not read: the variation tuples.
