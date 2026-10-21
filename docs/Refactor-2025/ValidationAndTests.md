# Refactor-2025: tests and validation

**Branch:** `Refactor-2025`
**Last updated:** 2026-10-19

Tests, results and coverage notes moved from [Refactor-2025.md](Refactor-2025.md). Section numbers match
the changelog. Test usage is documented in [Tests/README.md](../../Tests/README.md); pending work is tracked
in [TODO.md](TODO.md).

The reference environment is `CMSSW_14_1_0_pre4` (Python 3.9, ROOT 6.30).

## Reading the checks

**How to read the checks.** Every step was checked on Windows with `python Tests/run.py checks` (the unit suites;
`check_root` needs ROOT and `check_import_boundaries` fails on the known coupling debt, so neither passes there).
The "lxplus" lines give the checks that need ROOT. "`bbb check` N/N without re-lock" means every BBB regression case
gave exactly its locked output. Import-boundary totals are written as occurrences / file-module pairs / files.

## 1. Test migration and BBB regression tests

**Change:** [CL §1](Refactor-2025.md#1-test-migration-and-bbb-regression-tests)

[Tests/inventory.json](../../Tests/inventory.json) classifies 37 cases: 26 local (run by `normal`),
7 opt-in integration, 2 legacy and 2 broken. Missing dependencies produce SKIP.

- **BBB: exact regression tests** (`Tests/BBB/`). Added 13 cases using fixed ROOT fixtures,
  recording histogram/tree structure, values and errors. Floating-point values are compared by exact bytes,
  without tolerance. Coverage includes:
  - common: table/loading-bar text, chunking and formatting;
  - Plotter: selections, weighted 1D/2D histograms, merging/splitting, DY stitching, QCD OS/SS, unrolling;
  - PicoProducer: tree writer schema, NanoAODTools bookkeeping, scale-factor lookup;
  - Fitter: shape naming, negative-bin sanitation, adaptive rebinning.

  `python3 Tests/run.py bbb lock` runs each case twice and rejects non-repeatable baselines.
  `python3 Tests/run.py bbb check` compares against [committed baselines](../../Tests/BBB/baselines/)
  and reports the exact changed field. Baselines were locked on Linux in `CMSSW_14_1_0_pre4`
  and re-locked (`ef80e40`) with CMSSW-provided packages.

BBB verifies that the covered outputs remain unchanged. Intentional output changes require an explicit
`bbb lock --replace`, reviewed in Git.

## 2. FastSetup script

**Change:** [CL §2](Refactor-2025.md#2-fastsetup-script)

No section-specific test or validation result was recorded in the changelog.

## 3. Removal of legacy Python 2 scripts

**Change:** [CL §3](Refactor-2025.md#3-removal-of-legacy-python-2-scripts)

The removals were checked against imports and shell-script calls.

## 4. Utilities package for future development

**Change:** [CL §4](Refactor-2025.md#4-utilities-package-for-future-development)

Offline tests mock remote and ROOT operations.

## 5. PicoProducer cleanup: command-level BBB tests and bug register

**Change:** [CL §5](Refactor-2025.md#5-picoproducer-cleanup-command-level-bbb-tests-and-bug-register)

- Added five command-level BBB cases: `pico.config`, `pico.run`, `pico.jobs`, `pico.merge`, `pico.workers`.
  They run `pico.py` and workers in fresh processes with fixed configuration/catalogs, synthetic NanoAOD
  and a fake scheduler. Snapshots cover config edits/recovery, chunking and option merging, status/resubmission,
  merge/cleanup gates, worker outputs and remaining files.

Existing PicoProducer baselines covered tree writing, bookkeeping and scale factors, leaving command workflows
unprotected. Testing public commands and normalizing internal script paths keeps coverage useful when modules move.
Some baselines deliberately record registered bugs; fixes require explicit, reviewable baseline changes.
Still open: a `ModuleTauPair` channel case before the analysis/corrections cleanup (TODO §5).

## 6. PicoProducer cleanup: settings, datasets, storage, batch and jobs packages

**Change:** [CL §6](Refactor-2025.md#6-picoproducer-cleanup-settings-datasets-storage-batch-and-jobs-packages)

**Not tested:** S01's SGE array submission has not been tested on an SGE site.

**Only P17 changes a BBB baseline** (`pico.config`, `fresh.values.eras`).

**Case-only module-name correction (`ae0d9bf`):**

After the correction, lxplus BBB showed only the intended P17 difference; the other 17 cases passed.
Re-lock `c2d8296` changed only `pico.config.json` and `manifest.json`.

## 7. PicoProducer cleanup: job pipelines

**Change:** [CL §7](Refactor-2025.md#7-picoproducer-cleanup-job-pipelines)

**Validation:** worker options and 280 submit/resubmit/status/merge/local-run scenarios (verbosity 0–3) matched the
old code (`3c401cd`) in output, files and external calls; the only difference was the exception type of P02's
existing prompt crash.

**No BBB change:** crash fixes P01–P03 and P07.

**No BBB change:** behavior fixes P04–P06, P11 and P19–P23.

- **Module options, BBB re-locked:** P08 (precedence channel < sample < user `-E`), P09 (resubmission does not grow
  the options), P10 (no default `-m -1` for local runs). `pico.run` and `pico.jobs` were re-locked on lxplus; they
  differ only in option order, the removed `-m -1` and the verbose labels `chopts`/`useropts`
  ([exact differences](../PicoProducer/BUGS.md#p08-p09-p10-module-options-and-run--m)).

## 8. PicoProducer cleanup: public API, command line, workers

**Change:** [CL §8](Refactor-2025.md#8-picoproducer-cleanup-public-api-command-line-workers)

BBB drives the CLI → API path.

**Validation:** 296 job scenarios and 30 CLI command lines matched the old output, files, calls and exit codes.

P12's `--opt` → `--opts` is the only further difference in `pico.run`/`pico.jobs` (re-locked in §7).

## 9. Framework: the TauFW orchestrator

**Change:** [CL §9](Refactor-2025.md#9-framework-the-taufw-orchestrator)

**Validation:** offline tests cover orchestration, persistence and CLI behavior; new lxplus BBB case
`framework.production` covers planning, resubmission, merged tuples and cleanup.

## 10. Framework: plots, histograms and fit stages

**Change:** [CL §10](Refactor-2025.md#10-framework-plots-histograms-and-fit-stages)

F07 (rebinned output location): confirmed on lxplus 2026-10-17.

**Validation:** offline tests cover command parity, failures and stale outputs. BBB `framework.production` was
re-locked; the other 18 cases were unchanged. Local script stages are outside BBB coverage.

**Still open:** a full VTight/Tight `taufw.py start` run of `Analyses/tes_id_2025` compared with the shell drivers
in a clean copy (TODO §1). The fit part on the same shapes was compared in §15.

## 11. Framework: analysis bundles and Python steps

**Change:** [CL §11](Refactor-2025.md#11-framework-analysis-bundles-and-python-steps)

**Validation:** offline tests cover bundle isolation and Python steps; BBB `framework.production` intentionally
changes for bundle/config metadata. PicoProducer cases stay unchanged.

## 12. Import-boundary test and coupling inventory

**Change:** [CL §12](Refactor-2025.md#12-import-boundary-test-and-coupling-inventory)

Registered with the test runner; the repository check fails on known debt as intended (today's totals: §22).
Production code and baselines are unchanged.

## 13. Framework: explicit stage ids, inputs and recipe validation

**Change:** [CL §13](Refactor-2025.md#13-framework-explicit-stage-ids-inputs-and-recipe-validation)

**Validation:** unit tests cover recipe errors and input isolation. BBB `framework.production` intentionally changes
for explicit ids/inputs in plans and the recorded recipe.

## 14. Framework: run directory with logs/ and stages/, stage manifests

**Change:** [CL §14](Refactor-2025.md#14-framework-run-directory-with-logs-and-stages-stage-manifests)

**Validation:** unit tests cover directory separation, manifests and rejected old records; BBB `framework.production`
changes for the record schema.

## 15. Framework: Plotter and Fitter outputs in the run directory

**Change:** [CL §15](Refactor-2025.md#15-framework-plotter-and-fitter-outputs-in-the-run-directory)

**Status:** checked on lxplus 2026-10-15

**Validation:** unit tests cover output isolation and preflight. On lxplus, plots match and `bbb check` is 20/20
unchanged. VTight/Tight fit parameters and corrections match exactly on the same shapes; Framework shapes match
the baseline up to 1e-13 (multithreaded RDataFrame). Separate shapes + fit runs can differ by a grid step in fitted
POIs (TODO §6).

## 16. Framework: tuples as an input, production writes into the run, run_root

**Change:** [CL §16](Refactor-2025.md#16-framework-tuples-as-an-input-production-writes-into-the-run-run_root)

**Status:** done; the end-to-end production check passed on lxplus

**Validation (lxplus):** external tuples give the same plots as §15; an unwritable run root stops before work starts.
An end-to-end production + plots run merges tuples into its stage directory and reads them there. BBB
`framework.production` was re-locked for the new tuple location (merged tuples byte-identical), then 20/20 passed.
PicoProducer S17 and Framework K07 were registered, not fixed.

## 17. Framework: inputs from another run's stage directory, repeated stages

**Change:** [CL §17](Refactor-2025.md#17-framework-inputs-from-another-runs-stage-directory-repeated-stages)

**Status:** checked on lxplus

**Validation:** unit tests cover manifests, provenance and repeated stages. On lxplus, a fit using another run's
shapes reproduces §15's parameter/correction files exactly and matches its ROOT contents, leaving the source unchanged.
Repeated plots stages write separately; cross-run tuple plans and invalid-source rejection pass. BBB
`framework.production` was re-locked for schema/provenance only; the other 19 cases were unchanged.

## 18. Menu and UI

**Change:** [CL §18](Refactor-2025.md#18-menu-and-ui)

**Pending:** lxplus checks: TODO §1.

Without `$TAUFW_EVENTS`, terminal output and `run.log` were checked byte for byte and are unchanged.

Checked: unit tests for the supervisor (exit codes, heartbeat, stop, kill, every state), the events and the screens;
end to end, a test run behind the menu, followed from a second menu. Process groups, signals and curses on a real
terminal: TODO §1.

## 19. Configs: config templates with an id, a version and a lock

**Change:** [CL §19](Refactor-2025.md#19-configs-config-templates-with-an-id-a-version-and-a-lock)

**Status:** done; nothing to check on lxplus (no ROOT, no BBB case)

- **Tests:** `Tests/Framework/test_configs.py` (no ROOT); two tests read the checkout's `Configs/`: the lock must be up
  to date, and every template must be readable by its module's reader (`READERS`).

## 20. Sample lists as data: the sample model

**Change:** [CL §20](Refactor-2025.md#20-sample-lists-as-data-the-sample-model)

**Status:** verified on lxplus 2026-10-17 (details in TODO §1)

- **Recorder and BBB case:** `Tests/Plotter/sample_model/recorder.py` records every call of a sample-set function
  (8 eras × 6 channels × 7 caller options = 336 cases). BBB case `plotter.sample_model` was locked on lxplus with the
  old code, then switched to the model with no difference.

Each exported sample template was read back and compared with the recorded calls.

A unit test checks all 336 cases against the old function.

lxplus: `bbb check` 21/21 and `Tests/run.py checks` after the switch; a plots + histograms run of `tes_id_2025` with
`samples:` against the same stages without it gave 57 byte-identical PNGs and equal shapes (up to multithreaded
RDataFrame noise; `data_obs` bit-identical); `plan` of `example_mutau_long` lists 25 samples.

## 21. Plotter becomes Histogrammer; a clean Plotter is extracted

**Change:** [CL §21](Refactor-2025.md#21-plotter-becomes-histogrammer-a-clean-plotter-is-extracted)

**Status:** done; S0–S4 checked on lxplus.

**Coupling:** 30 / 28 / 26 after the rename, including 13 compatibility aliases; 0 new pairs. The rename itself
removed no cross-stage import. Outside the aliases, Plotter imports only Utilities; Histogrammer and Plotter
never import each other.

### Lock and tools (S0)

Locked new BBB case `plotter.stack` with the old code, covering samples, QCD, stack histograms, drawing attributes
and canvases. Added `Tests/tools/move_check.py` to check code moves. A one-off ROOT round-trip experiment confirmed
that drawing from a file and plain drawing attributes preserves canvases and PNGs (12/12 SAME).

### Test migration (S1)

The unit tests moved to `Tests/Histogrammer/`. BBB case names stay `plotter.*`.

### Histogram file and drawing (S3)

BBB `plotter.stack` now covers fill → write → read → draw against the S0 lock. Unit tests cover the file format
and both modules' handling of it.

### Review fixes

Tests cover the histogram-file/metadata errors and duplicate variable names described in CL §21,
and clear rejection of run records naming retired stages.

**Validation (lxplus):** BBB 22/22 without re-lock after S1–S4 and the review fixes; known import-boundary debt
remains. On real 2025 tuples, renamed filling and file-based drawing reproduce the old PNGs (31 mutau, 19 mumu;
`m_ll` excluded because of existing L17). The two Framework stages reproduce the old one-step plots.
Files with/without drawing agree within multithreaded-fill noise (~1e-13); the stage rename preserves the
`tes_id_2025` plan's commands and inputs. Registered issues: L17, K08, flaky background tests and IOInventory (TODO §7).

## 22. TES shapes leave the Fitter for the Histogrammer

**Change:** [CL §22](Refactor-2025.md#22-tes-shapes-leave-the-fitter-for-the-histogrammer)

**Status:** done; H0–H4 checked on lxplus.

**Coupling:** 30 / 28 / 26 before, 25 / 23 / 21 after H1; 0 new pairs. Fitter → Histogrammer drops from 6 to 1
(`Fitter/MuTauFR/createinputs.py`, D11). Fitter's Python API no longer names Histogrammer paths; stages share
files and channel configs.

### Lock and contract (H0)

Locked new BBB case `histogrammer.tes_inputs` with the old script, covering TES/LTF tuple inputs, shape and rebinned
files, and PNG names. Wrote the file/config contract shared by filling and fitting.

**Coverage limits:** working-point substitution is not tested (no `idDeepTau*` branches); LTF variation files are
read but their shapes are empty in the fixture. H4 covers LTF content on real data; extending BBB remains in TODO §7.

### Moved cases (H1)

- BBB writer/rebin cases import `TauFW.Histogrammer.shapes`; the end-to-end case runs the moved script.

### Channel configs (H2)

Contract tests check the keys required by both readers; template resolution and migration errors have unit coverage.

**Validation (lxplus):** BBB 23/23 without re-lock after H1, H2 and H3; running the old code against the lock
also matches. `checks` is 14/15 because of known import-boundary debt. The `tes_id_2025` plan is unchanged by H2/H3;
unit tests cover compatibility stubs, templates and API/config errors.

### Real-data comparison (H4)

On lxplus (2026-10-18/19), compared one pre-H1 run (`0c611f4`) with two current-code runs using the same 2025
tuples, configs and samples. `Tests/tools/compare_shapefiles.py` compares file names, ROOT keys and histogram content.

- Old/new: the same 43 files, keys in all 4 ROOT files, and 775 histograms within relative tolerance 1e-12.
- Largest old/new relative difference: 5e-13; between two current-code runs: 1.07e-12. The observed migration
  difference is below the run-to-run noise of multithreaded filling.
- All 96 LTF histograms have content and are compared here, covering the gap in the BBB fixture.
- `check` / `plan` of `tes_id_2025` and `example_mutau_long` report no problems, only run-root warnings.

## 23. Variation tuples in the shapes preflight

**Change:** [CL §23](Refactor-2025.md#23-variation-tuples-in-the-shapes-preflight)

**Status:** done; checked on lxplus 2026-10-19.

- `Tests/tools/check_variation_files.py` (lxplus, ROOT): builds the real `SampleSet` as the script does, makes every
  shifted set with `Sample.setnevents` switched off (no variation file opened) and compares the file names with the
  preflight's: SAME or the files only one side names.
- Tests: `Tests/Histogrammer/sample_model/test_variations.py` (the 144 files, mumu none, every `Configs/Fitter/tes_id`
  template with every sample template, the TES tag format, weight-only and empty `sampleAppend`, the substring
  match without joins, split with its own title, rename, the 2022 stitching), `ShapesVariationTests` in
  `Tests/Histogrammer/api/test_tes_shapes.py` (all there, one missing, counts by tag, the cases not checked).

**Validation (lxplus, 2026-10-19):**

- `check_variation_files.py` against the real `SampleSet`: SAME 144 (mutau), SAME 0 (mumu).
- `tes_id_2025`: `check` and `plan` show no variation problem.
- A shapes-only copy of `tes_id_2025` on a symlink mirror of the tuples without `TT/TTtoLNu2Q_mutau_LTF1p030.root`:
  `plan` warns "1 of 144 variation tuple file(s) ... (_LTF1p030: 1): <that file>"; `start` leaves the stage NEW
  ("Stage shapes is not ready: ...") and runs no command. `taufw.py check` validates the recipe only (no stage
  preflight), so it does not show the missing file.
- `checks` 14/15 (known import-boundary debt, 25 / 23 / 21, 0 new pairs).

## 24. Review of the tes_id_2025 bundle: fit-result comparison, result files in the summary

**Change:** [CL §24](Refactor-2025.md#24-review-of-the-tes_id_2025-bundle-fit-result-comparison-result-files-in-the-summary)

**Status:** Windows checks done; the lxplus run is TODO §1 "Framework, TES/ID bundle".

- `Tests/tools/test_compare_fitresults.py` (7 tests): parameters by name, the tolerance per kind (a difference of
  exactly one grid step is equal), JSON trees, the result-file lists, nothing to compare is a failure.
- `taufw.py check` and `plan` of `tes_id_2025` (Windows, test bootstrap): the same commands as before; the bundle's
  configs equal the `Configs/` templates. `fit_summary.py` run with a fake context: the table, then the correction
  files with a missing one marked.
- `python Tests/run.py checks`: 13/15 (`check_import_boundaries` known debt 25 / 23 / 21, `check_root` needs ROOT).

## 25. Postfit scripts set the era through CMSStyle (no Plotter import)

**Change:** [CL §25](Refactor-2025.md#25-postfit-scripts-set-the-era-through-cmsstyle-no-plotter-import)

**Status:** done; checked on lxplus 2026-10-19 (TODO §1, CL §25-§27 item).

- `python Tests/check_import_boundaries.py -q`: 21 / 19 / 17, 0 new pairs, no stale allowlist entry (Fitter ->
  Plotter 5 / 4 / 3).
- BBB `drawing.canvas` (locked 2026-10-14) covers `setCMSEra` and its texts; the old `setera` path is compared by
  `Tests/tools/check_setera.py` on lxplus. The postfit scripts themselves have no BBB case (they need combine output).

## 26. The luminosity of the normalisation in the sample model and the control-histogram file

**Change:** [CL §26](Refactor-2025.md#26-the-luminosity-of-the-normalisation-in-the-sample-model-and-the-control-histogram-file)

**Status:** done; checked on lxplus 2026-10-19 (TODO §1, CL §25-§27 item).

- `Tests/Histogrammer/sample_model/test_sample_model.py`: the call-equality grid (old `samples_v15.py` against the
  model) passes once the model's `lumi=` is checked to equal the table lookup and removed
  (`without_model_lumi`); `test_template_lumi_is_the_table_value` (every template, and the recorded `setera` call);
  format problems: `lumi` missing, not positive, `schema: 1` (message), `schema: 3`.
- `Tests/Histogrammer/controlhists`, `Tests/Plotter/draw`: version 2 metadata written and read, `lumi: null`,
  version 1 refused with the message, `lumi`/`cme` missing refused; the constants of both sides agree.
- `Tests/Framework/test_samples.py`: the broken-copy case uses another unknown key (`lumi` is known now).
- `export.py` into a scratch directory: the eight templates the same apart from the header version.
- `python Tests/run.py checks`: 13/15 (`check_import_boundaries` known debt, `check_root` needs ROOT).

## 27. The fit plots show the luminosity of the normalisation; explicit lumi on the samples

**Change:** [CL §27](Refactor-2025.md#27-the-fit-plots-show-the-luminosity-of-the-normalisation-explicit-lumi-on-the-samples)

**Status:** done; checked on lxplus 2026-10-19 (TODO §1, CL §25-§27 item).

- `Tests/Histogrammer/api/test_tes_shapes.py` `test_artifacts_carry_the_normalisation`: lumi/cme of the sample file,
  `None` without one or with an unreadable one.
- `Tests/Framework/test_stages.py` `FitLabelTests`: labels from the artifacts, none for artifacts without lumi,
  another era ignored, different values an error.
- `Tests/Fitter/api/test_tes_id.py` `LabelTests`: `--lumi 110.18 --cme 13.6` on exactly the four scripts, nothing
  without a label or for another era, no `--cme` when it is unknown.
- `Tests/Histogrammer/controlhists` `test_normalisation_lumi`; the sample-model equality grid checks and removes the
  `lumi` of the core call too.
- The command strings the `makecombinedfit` scripts build were checked by hand (`... -i out/ --lumi 110.18 --cme
  13.6`); the scripts themselves need ROOT/combine: lxplus.
- `python Tests/run.py checks`: 13/15 (known import debt 21 / 19 / 17, `check_root`).

**Validation (lxplus, 2026-10-19), CL §25-§27 together:** a `hists` + `plots` copy of `tes_id_2025` with the code
before (`74d8e68`) and after (`4afa0bd`): every PNG byte-identical, the new files are version 2 with `lumi 110.18`,
`cme 13.6`. `check_setera.py` SAME (28 cases). BBB: `plotter.sample_model` re-locked (approved, plan 22 K2; `lock`
re-captures the whole suite: 22 same, 1 changed): 658 `lumi` fields added, each equal to the old
`CMSStyle.lumi_dict` value of its era (2022_postEE 27.0072, 2022_preEE 8.077, 2023C 17.06, 2023D 9.525, 2024
109.08, 2025 110.18, 2026 25.3, 2526 135.48), the baseline otherwise identical. `histogrammer.tes_inputs` needed
`lumi` in its own mini model (`3268066`) and then passed without re-lock. `bbb check` 23/23; `checks` 14/15.

## 28. One advance per run, a safe stop, the command log in the progress events

**Change:** [CL §28](Refactor-2025.md#28-one-advance-per-run-a-safe-stop-the-command-log-in-the-progress-events)

**Status:** unit tests on Windows; lxplus check open (TODO §1 "Run lock and safe stop on lxplus").

- `Tests/Framework/test_run_lock.py`: held and removed; a second lock refused; a live lock of another machine never
  taken (also with take); a lost one only with take; a lock of this machine whose process is gone taken at once; a
  half-written lock goes by the file time; the heartbeat renews `t`; `check()` after a takeover. `Framework.advance`
  holds and releases it (also after a stage error), is refused without changing `run.json`, says when it took a lock
  over. `taufw.py advance`: one warning line, the `--take-lock` hint only for a lost lock, `--take-lock` continues.
- `Tests/Framework/test_interrupts.py`: one Ctrl-C waits for the block, a second stops at once, the handler is
  restored; a submission cut by Ctrl-C is still recorded (SUBMITTED, lock gone); a merge stops at once (MERGING).
- `Tests/Utilities/test_operations.py` `test_signal_command_stops_the_command_alone`; `test_process.py` and
  `Tests/Framework/test_stages.py` `test_progress_events`: the log path in the callback and in the events.
- `python Tests/run.py all` on Windows: unit and harness 13/15 (known import debt, `check_root`), Framework 195 and
  Utilities 180 tests OK; normal and BBB need lxplus.
