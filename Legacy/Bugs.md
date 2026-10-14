# Legacy bug register

Consolidated on **2026-10-14** from existing bug registers, legacy READMEs,
[component inventory](../docs/Refactor-2025/Legacy.md),
[analysis inventory](OldAnalysis/README.md), [refactor TODOs](../docs/Refactor-2025/TODO.md),
test documentation and the local cleanup audit. This consolidation inspected documentation only;
it did not search implementation code for bugs or verify runtime behavior.

This file owns known defects in retired workflows, archived package modules and excluded
broken demonstration/test scripts. Existing IDs and recorded fix status are preserved.
Rows without an earlier ID use `LEG-*` identifiers assigned for this register.
Archiving is not a fix; repair these paths if they are revived.

Bugs in maintained code remain in the [PicoProducer](../docs/PicoProducer/BUGS.md),
[Plotter](../docs/Plotter/BUGS.md) and [Fitter](../docs/Fitter/BUGS.md) registers and
[refactor TODOs](../docs/Refactor-2025/TODO.md). Being old, unused, latent, or outside
the main Framework workflow alone does not make a defect a legacy bug. Historical
change-log records and archive retirement reasons remain in their original documents.

## PicoProducer

Moved from the PicoProducer register. Locations below are repository-relative;
`analysis/` in the A01 history refers to the original PicoProducer package location.
Severity and BBB coverage retain the source register's definitions.

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| W03 | `Legacy/OldAnalysis/2018/dumpGen.py` (was `processors/dumpGen.py`) | Not referenced anywhere | latent | no | S2 | moved to `Legacy/OldAnalysis/2018/dumpGen.py` (not fixed) | none |
| A11 | `Legacy/OldAnalysis/2016-2017/CheckMuTrigger.py:26` | Trigger threshold attributes are assigned but unused (hard-coded 24 GeV); `trigsf` stays 1.0 | wrong | no | S2 | moved to `legacy/` (not fixed) | none |
| A13 | `import *` chains (now only in the component package archives and `Legacy/OldAnalysis/`) | `datadir` is rebound by BTagTool/PileupTool/JetVetoMapTool/TauTriggerSFs and leaks through star imports. JetTauFakeRate works around it with `replace("/pileup","")`. Session 2 replaced every star import outside `legacy/` by explicit imports of the *same* objects: all maintained modules see the base `datadir`, as before | wrong | no | S6 | | |
| C10 | `Legacy/PicoProducer/python/corrections/PreFireTool.py` | `from corrections import ...` fails, and CMSSW_BASE path building raises without CMSSW | crash | no | S2 | moved to `legacy/` (not fixed) | none |
| A01 (archived copies) | `Legacy/PicoProducer/python/analysis/ModuleMuTau_nanoV10_DeepTau2p1.py`, `analysis/TauES/ModuleMuTau.py`, `analysis/MuTauFakeRate/ModuleMuTau.py` (all under that legacy package) | `getlepvetoes(...)` is called without the required `era` argument; the first event reaching the vetoes raises `TypeError` | crash | no | S6 | not fixed | Maintained copies remain under A01 in the production register |

### Recorded origins

- **W03** `dumpGen.py` has had no references from day one: commit `d5c9d36` (2020-05-25, "add dump gen processor")
  added it as a standalone script ("Standalone to dump gen particle information"; its usage line still says
  `python dumpLHE.py`, a copy-paste leftover). The only mentions are a link in the header of `analysis/GenDumper.py`
  (`195c53d`, 2020-06-22) and a line in `processors/README.md` (`fc46a42`, 2021-07-16). It is a script run by hand,
  so it never had a caller. It moved to legacy in `0bc4d62` (2026-10-12).

- **A11** `CheckMuTrigger` has been like this since the day it was written: commit `62b74a8` (2021-07-20, "split
  triggers") created it as `analysis/ModuleMuTrigger.py`, already with the unused threshold lambdas, the hard-coded
  `if muon.pt<24: continue` and `self.out.trigsf[0] = 1.0 # TODO`. Since then it was only renamed (`eea9c66`,
  `18da2c3`, `490dd93`, 2021-07-23) and moved (`0bc4d62`, `623a040`, 2026-10). It is a one-off trigger-overlap study
  and nothing reads `trigsf`, so nobody noticed.

- **A13** The `datadir` leak has been there since the day the code was written: commit `f8ba048` (2020-06-21) created
  `PileupTool.py` with a module-level `datadir = os.path.join(datadir,"pileup")` (and `BTagTool.py` with `"btag"`),
  and `ModuleTauPair.py` star-imported `PileupTool`. `TauTriggerSFs` (`8ce519b`, 2020-07-18) and `JetVetoMapTool`
  (`26271a6`, 2024-03-25) later rebound it the same way. The `replace("/pileup","")` workaround came in `5853bb3`
  (2022-06-21, JetTauFake modules, with the comment "for some reason the pileup subfolder is selected as datadir ...
  fixme") and was copied in `50f604f` (2022-07-26). Maintained modules almost never use `datadir` directly, and the
  one author who hit it patched around it, so it was never fixed.

- **C10** `PreFireTool` has been broken since it was added in `7c97e15` (2020-06-21, "add correction tools"), with
  `from corrections import modulepath, extractTH1` (`modulepath` was never defined in this repo; probably a
  leftover of an older standalone setup) and the `CMSSW_BASE` path. `RecoilCorrectionTool` had the same bad import
  and was fixed in `64ce575` (2020-07-06); `PreFireTool` never was. Every use has always been commented out, so it
  was never imported. `0bc4d62` (2026-10-12) only moved it to `legacy/`.

The archived A01 callers originate from the same 2020 commits as the maintained
callers. `9411be0` (2023-10-19) added `era` with a default; `877e636` (2024-02-20)
made it required. See the [maintained A01 history](../docs/PicoProducer/BUGS.md#analysis-modules-and-writers).

## Fitter archives

Sources: [Fitter archive README](Fitter/README.md) and
[component inventory](../docs/Refactor-2025/Legacy.md). All entries remain unfixed.
Paths are relative to `Legacy/Fitter/`.

| ID | Location | Recorded defect | Replacement |
|---|---|---|---|
| LEG-F01 | `createJSON_TES.py` | Imports the missing `fit_tools` module | `Fitter/createroot_TES.py -f json` |
| LEG-F02 | `run_createroot_TES.py` | The `hadd` command contains literal `{era}`, `{jet_wp}` and `{ele_wp}` placeholders; `jet_wp` is also never assigned. The inventory clarifies that this command is not interpolated, so that line is a malformed command rather than a Python `NameError` | Export step of `Fitter/run_workflow_zmm*.sh` |
| LEG-F03 | `TauES/doTES.sh` | Uses the missing `Fitter/analysis/TauES` location and removed scripts | `Fitter/run_workflow_zmm*.sh` |
| LEG-F04 | `TauES_ID/saveSFs_root_JSON.py` | Calls missing `saveSFs_root.py` | `Fitter/createroot_TES.py` |
| LEG-F05 | `scripts/plotBiasTest.py`, `scripts/plotChannelCompatibility.py` | Python 2 syntax raises `SyntaxError` in Python 3 | No replacement recorded |
| LEG-F06 | `ETauFR/Fitting.sh` | Calls removed `compare.py`; the inventory also records a personal AFS path | `Fitter/ETauFR/runAll_combFit.sh` |
| LEG-F07 | `paper/postfit.sh` | Calls removed `writecards.py` | No replacement recorded |

## Plotter archives

Sources: [Plotter archive README](Plotter/README.md),
[JetToTauFR README](../Legacy/Plotter/python/corrections/JetToTauFR/README.md),
[component inventory](../docs/Refactor-2025/Legacy.md) and the local cleanup audit
(`LocalR/CodebaseCleanupAudit.md`, historical paths). All entries remain unfixed.

| ID | Location (repository-relative) | Recorded defect or limitation | Recorded workaround |
|---|---|---|---|
| LEG-L01 | `Legacy/Plotter/python/corrections/JetToTauFR/plotJetToTauFRvariables_writeJson.py` | JSON final-state/barrel key is written as `mumettau__mumettau:Barrel` instead of `mumettau_Barrel`; endcap has the same issue | Manually correct the barrel and endcap keys before reading/applying the fake rates |
| LEG-L02 | `Legacy/Plotter/python/corrections/JetToTauFR/plotJetToTauFRvariables_writeJson_FRinPtBins.py` and its consumers | pT-only fake rates require a manual eta-list change in `readAndPlotFR.py` and `Legacy/Plotter/python/methods/JetToTau_MisID.py` | Set `eta = [""]` in both consumers for pT-only results |
| LEG-L03 | `Legacy/Plotter/python/corrections/JetToTauFR/` workflow | Recorded Python 2 dependencies (`StringIO`, `raw_input`), implicit relative imports and personal AFS configuration paths; this is a workflow-level limitation, not a claim that every helper has all defects | Review dependencies and paths before reuse |
| LEG-L04 | `Legacy/Plotter/python/methods/ScaleVariations.py` | Cannot be selected by `method='ScaleVariations'`: there is no matching attribute | No workaround recorded |
| LEG-L05 | `Legacy/Plotter/python/corrections/JetToTauFR/tools/styles.py` | Two different `getSignalStyleHToTB()` definitions; the later definition hides the first | No workaround recorded |
| LEG-L06 | `Legacy/Plotter/python/corrections/JetToTauFR/tools/histograms.py` | `HistoEfficiency.getYmin()` and `getYmax()` are redefined; earlier calculations incorporating efficiency uncertainties are hidden | No workaround recorded |
| LEG-L07 | `Legacy/Plotter/python/corrections/JetToTauFR/readAndPlotFR.py` | Additional plot text is disabled with `if 0:`; another disabled block contains an OpenGL setting | Recorded as an ineffective feature; no runtime failure established |

## One-off analysis archives

Source: [analysis inventory](OldAnalysis/README.md). All entries remain unfixed;
paths are relative to `Legacy/OldAnalysis/`.

| ID | Location | Recorded defect or integration constraint |
|---|---|---|
| LEG-O01 | `2018/takeZmu.py` | Invalid indentation prevents parsing; `dm` is referenced after its defining loop was commented out |
| LEG-O02 | `2022/plot_mvis_uncorr_corr.py` | Uses `os` without importing it |
| LEG-O03 | `2016-2018/plot2D.py` | Advertised 2022 eras are rejected by its Run 2 sample configuration |
| LEG-O04 | `2016-2018/plot_compare.py` | Sample-set construction call is commented out |
| LEG-O05 | `YearIndependent/plot_GENSIM.py` | Calls `tree.MultiDraw` without importing the module that installs it |
| LEG-O06 | `2016-2018/aco.C`, `2016-2018/corrs_ntracks.C` | Required external ROOT payloads are absent from the repository and are resolved through original absolute paths; this is an integration constraint, not proof of an algorithmic defect |

The trigger-study and jet-to-tau analyzer defects are tracked above as A11 and A13.

## Excluded broken test and demonstration scripts

Moved from `Tests/LEGACY_BROKEN_CASES.md`; the following report preserves its
recorded evidence and validation limits. These defects concern test/demo scripts,
not proof that the corresponding production classes are broken.

These two cases are excluded because their existing scripts cannot complete in
the Python 3.9 test environment. The migration preserved their contents; it did
not introduce the defects described below. This report documents the problems
without fixing them.

### Overview

| Case | Classification | First failure in a suitable dependency environment |
| --- | --- | --- |
| `pico.sample` | `broken` | The `print(` call at line 88 has no closing parenthesis outside its comment. |
| `plotter.rdataframe` | `broken` | With PyROOT available, module execution reaches an undefined `kBlue` at line 17. |

The classifications describe these demonstration/test scripts. They do not
establish that the corresponding production classes are broken.

### `pico.sample`: a parenthesis hidden inside a comment

Source: [testSample.py](../Tests/PicoProducer/testSample.py).

Line 88 reads:

```python
print(">>> Call Sample.getfiles..." # load Sample.files from txt file)
```

Everything after `#` is a comment, including the apparent closing `)`. The
opening `print(` therefore remains unclosed. Python cannot parse the module, so
none of its imports, sample construction, matching checks, or file operations
execute. This is a syntax defect, not a failing `Sample.getfiles()` call.

There is a separate integration constraint beyond the syntax error. Lines
14–35 configure real 2016 CMS datasets with no supplied local storage or file
list. Line 74 calls `sample.writefiles(..., nevts=True)`, which requests file
discovery and per-file event counts. The production
[Sample storage code](../PicoProducer/python/datasets/sample.py) routes discovery
to DAS when no storage source is available (`getfiles()`, lines 224–248).
Consequently, even a syntactically repaired script would not be an isolated,
offline normal test with its current defaults. This dependency is not itself
proof of another runtime defect, and no DAS request was made for this report.

### `plotter.rdataframe`: multiple independent runtime defects

Source: [testRDataFrame.py](../Tests/Plotter/testRDataFrame.py).

This file parses as Python 3, but its module-level execution fails before
`main()` in an environment with working PyROOT. Line 11 imports only `TNamed`,
`RDataFrame`, and `RDF` from ROOT. Line 17 then evaluates:

```python
lcolors = [kBlue+1, kRed+1, kGreen+1, kMagenta+1]
```

None of those color names is defined in the Python namespace. `import ROOT`
does not make unqualified names such as `kBlue` available. The first lookup
raises `NameError`; the subsequent color names have the same issue.

Correcting the color imports alone would leave these problems:

| Location | Problem | Consequence if reached |
| --- | --- | --- |
| Lines 89, 145–150, 167 | `sampleset_RDF()` expects each input to unpack into `(stitle, fname, weight)`, but `main()` supplies filename strings. CLI `--fnames` also supplies strings. | The default paths raise `ValueError: too many values to unpack (expected 3)` before an RDataFrame is constructed. |
| Lines 103 and 122 | `res_dict` and `sname` are never defined. The loop defines `stitle`, not `sname`. | Histogram bookkeeping cannot proceed; line 103 first fails on `res_dict` if execution reaches it. |
| Lines 108–112 | `xvar` is read before its later assignment; `vfname` and `xexp` are also undefined. The variable loop instead defines `vname` and `vexp`. | Line 108 would raise `UnboundLocalError` for `xvar`; the expression-definition path has further undefined names. |
| Line 115 | `wname` is undefined. A `weight` string exists, but no corresponding `wname` is established. | The histogram booking call cannot execute as written. |
| Line 66 | `plot()` uses `TCanvas` without importing or defining it. | Calling this helper would raise `NameError`. The current `main()` does not call it. |
| Lines 143–150 | Default inputs live under `/scratch/ineuteli/analysis/UL2018`. | These external files are not portable repository fixtures; later execution would require suitable inputs and branches. |

The failures after the color lookup are established by source inspection. They
are masked by the first failure in the unchanged script and were not reproduced
through a full ROOT execution. The separate `plotter.rdataframe_sample` case is
still classified as local; this exclusion concerns `plotter.rdataframe` only.

### Why these are pre-existing, and how the runner handles them

For both files, the current SHA-256 hash after LF/CRLF normalization matches
the corresponding `canonical_sha256` in [migration.json](../Tests/migration.json).
Their contents also match the original paths in the parent of migration commit
`046367c` (`git show 046367c^:<original-path>`), using the same normalization.
This directly confirms that the listed script defects existed before relocation.

[inventory.json](../Tests/inventory.json) retains both case IDs and their reasons.
In [run.py](../Tests/run.py), `select_cases()` maps `normal` to the `local` group and
selects only that group. Explicitly requesting one of these cases through
`normal --case ...` rejects the selection with its classification and reason;
it does not run the script or report a successful test.

### Validation scope

Validation used source inspection, the migration/historical hash
comparisons, and in-memory parsing with Python 3.13.8's
`ast.parse(..., feature_version=(3, 9))`. Parsing reproduced the unclosed parenthesis
(and, before those cases were removed, the two Python 2 print failures), and confirmed that the RDataFrame
file passes syntax parsing. This grammar check is not execution under Python
3.9 or a PyROOT runtime test. No full test suite, ROOT event processing, or
remote dataset access was performed. At the time of the original report, only that Markdown report was added.

The Python 2 cases `common.loadingbar` and `common.table` were removed when
`LoadingBar` and `Table` moved to `TauFW.Utilities.CLI` (changelog §15, §17);
unit tests in `Tests/Utilities/test_cli.py` replace them.
