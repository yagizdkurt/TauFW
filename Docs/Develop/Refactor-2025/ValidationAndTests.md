# Refactor-2025: tests and validation

**Branch:** `Refactor-2025`
**Last updated:** 2026-10-19

Tests, results and coverage notes moved from [Refactor-2025.md](Refactor-2025.md). Section numbers match
the changelog. Test usage is documented in [Tests/README.md](../../../Tests/README.md); pending work is tracked
in [TODO.md](TODO.md).

The reference environment is `CMSSW_14_1_0_pre4` (Python 3.9, ROOT 6.30).

## Reading the checks

**How to read the checks.** Every step was checked on Windows with `python Tests/run.py checks` (the unit suites;
`check_root` needs ROOT and `check_import_boundaries` fails on the known coupling debt, so neither passes there).
The "lxplus" lines give the checks that need ROOT. "`bbb check` N/N without re-lock" means every BBB regression case
gave exactly its locked output. Import-boundary totals are written as occurrences / file-module pairs / files.

## 1. Test migration and BBB regression tests

**Change:** [CL §1](Refactor-2025.md#1-test-migration-and-bbb-regression-tests)

[Tests/inventory.json](../../../Tests/inventory.json) classifies 37 cases: 26 local (run by `normal`),
7 opt-in integration, 2 legacy and 2 broken. Missing dependencies produce SKIP.

- **BBB: exact regression tests** (`Tests/BBB/`). Added 13 cases using fixed ROOT fixtures,
  recording histogram/tree structure, values and errors. Floating-point values are compared by exact bytes,
  without tolerance. Coverage includes:
  - common: table/loading-bar text, chunking and formatting;
  - Plotter: selections, weighted 1D/2D histograms, merging/splitting, DY stitching, QCD OS/SS, unrolling;
  - PicoProducer: tree writer schema, NanoAODTools bookkeeping, scale-factor lookup;
  - Fitter: shape naming, negative-bin sanitation, adaptive rebinning.

  `python3 Tests/run.py bbb lock` runs each case twice and rejects non-repeatable baselines.
  `python3 Tests/run.py bbb check` compares against [committed baselines](../../../Tests/BBB/baselines/)
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
  ([exact differences](../Bugs.md#picoproducer-p08-p09-p10-module-options-and-run--m)).

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

**Validation:** unit tests cover output isolation and preflight. On lxplus, plots match and `bbb check` is 20/20
unchanged. VTight/Tight fit parameters and corrections match exactly on the same shapes; Framework shapes match
the baseline up to 1e-13 (multithreaded RDataFrame). Separate shapes + fit runs can differ by a grid step in fitted
POIs (TODO §6).

## 16. Framework: tuples as an input, production writes into the run, run_root

**Change:** [CL §16](Refactor-2025.md#16-framework-tuples-as-an-input-production-writes-into-the-run-run_root)

**Validation (lxplus):** external tuples give the same plots as §15; an unwritable run root stops before work starts.
An end-to-end production + plots run merges tuples into its stage directory and reads them there. BBB
`framework.production` was re-locked for the new tuple location (merged tuples byte-identical), then 20/20 passed.
PicoProducer S17 and Framework K07 were registered, not fixed.

## 17. Framework: inputs from another run's stage directory, repeated stages

**Change:** [CL §17](Refactor-2025.md#17-framework-inputs-from-another-runs-stage-directory-repeated-stages)

**Validation:** unit tests cover manifests, provenance and repeated stages. On lxplus, a fit using another run's
shapes reproduces §15's parameter/correction files exactly and matches its ROOT contents, leaving the source unchanged.
Repeated plots stages write separately; cross-run tuple plans and invalid-source rejection pass. BBB
`framework.production` was re-locked for schema/provenance only; the other 19 cases were unchanged.

## 18. Menu and UI

**Change:** [CL §18](Refactor-2025.md#18-menu-and-ui)

Without `$TAUFW_EVENTS`, terminal output and `run.log` were checked byte for byte and are unchanged.

Checked: unit tests for the supervisor (exit codes, heartbeat, stop, kill, every state), the events and the screens;
end to end, a test run behind the menu, followed from a second menu. Process groups, signals and curses on a real
terminal: on lxplus.

## 19. Configs: config templates with an id, a version and a lock

**Change:** [CL §19](Refactor-2025.md#19-configs-config-templates-with-an-id-a-version-and-a-lock)

- **Tests:** `Tests/Framework/test_configs.py` (no ROOT); two tests read the checkout's `Configs/`: the lock must be up
  to date, and every template must be readable by its module's reader (`READERS`).

## 20. Sample lists as data: the sample model

**Change:** [CL §20](Refactor-2025.md#20-sample-lists-as-data-the-sample-model)

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

- `Tests/tools/test_compare_fitresults.py` (7 tests): parameters by name, the tolerance per kind (a difference of
  exactly one grid step is equal), JSON trees, the result-file lists, nothing to compare is a failure.
- `taufw.py check` and `plan` of `tes_id_2025` (Windows, test bootstrap): the same commands as before; the bundle's
  configs equal the `Configs/` templates. `fit_summary.py` run with a fake context: the table, then the correction
  files with a missing one marked.
- `python Tests/run.py checks`: 13/15 (`check_import_boundaries` known debt 25 / 23 / 21, `check_root` needs ROOT).

## 25. Postfit scripts set the era through CMSStyle (no Plotter import)

**Change:** [CL §25](Refactor-2025.md#25-postfit-scripts-set-the-era-through-cmsstyle-no-plotter-import)

- `python Tests/check_import_boundaries.py -q`: 21 / 19 / 17, 0 new pairs, no stale allowlist entry (Fitter ->
  Plotter 5 / 4 / 3).
- BBB `drawing.canvas` (locked 2026-10-14) covers `setCMSEra` and its texts; the old `setera` path is compared by
  `Tests/tools/check_setera.py` on lxplus. The postfit scripts themselves have no BBB case (they need combine output).

## 26. The luminosity of the normalisation in the sample model and the control-histogram file

**Change:** [CL §26](Refactor-2025.md#26-the-luminosity-of-the-normalisation-in-the-sample-model-and-the-control-histogram-file)

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

## 29. Start and Continue run behind the menu

**Change:** [CL §29](Refactor-2025.md#29-start-and-continue-run-behind-the-menu)

- `Tests/Utilities/test_menu.py`: Start and Continue start runs (never `execute`), an ended advance is marked seen,
  Continue on an advancing run opens it, Advance once, the lock screen (live: back; lost elsewhere: take over with
  `take_lock`; lost here: no screen), the grid proxy check (back, renew, renew failed), the main menu run line (one
  run, the chooser), the `continue_actions` and `grid_proxy_needed` actions.
- `Tests/Framework/test_interactive.py`: the argv, `kind`, `escalate=False`, `signal="command"` and data of an
  advance; Advance once; the start of a bundle; `run_operations` (running and unseen only), `run_operation`,
  `run_advances` (a start's run dir from its `run` event), earlier advances marked seen, `run_lock` with `local`;
  `needs_grid_proxy` for recipes and runs.
- `python Tests/run.py all` on Windows: unit and harness 13/15 (known import debt, `check_root`), Framework 197 and
  Utilities 184 tests OK.

## 30. Plan and status run behind the menu, their output on a screen

**Change:** [CL §30](Refactor-2025.md#30-plan-and-status-run-behind-the-menu-their-output-on-a-screen)

- `Tests/Utilities/test_operation_screen.py` `test_a_command_screen_shows_its_output_and_leaving_stops_it`: only the
  output is drawn; Esc while it runs stops and leaves, S stops without a question, R only once it ended
  ("refresh"), the footers, "taufw.py status" on the state line.
- `Tests/Utilities/test_menu.py` `test_plan_and_status_are_shown_on_the_command_screen`: plan from the review,
  status from Inspect with two refreshes, no pause; a failing `start_command` is reported.
- `Tests/Framework/test_interactive.py`: `test_plan_and_status_run_behind_the_menu` (argv, kind, title, cwd, data;
  only plan/status; `running_operations` leaves commands out); Inspect refresh, the detailed plan before the start
  and Continue on a finished run start `status`/`plan` behind the menu, never in the menu's process.
- Windows end-to-end: `start_command("plan", "Analyses/tes_id_2025")` with a real `OperationStore` ran the
  supervisor and recorded FAILED, exit 1 and the output (no built TauFW package on Windows: `ModuleNotFoundError`
  in taufw.py, as for Start); the real output needs lxplus.
- `python Tests/run.py checks` on Windows: 13/15 (the known two: import debt in `check_import_boundaries`,
  `check_root`).

## 31. The main menu draws without voms-proxy-info and without re-reading ended operations

**Change:** [CL §31](Refactor-2025.md#31-the-main-menu-draws-without-voms-proxy-info-and-without-re-reading-ended-operations)

- `Tests/Framework/test_interactive.py` `test_grid_proxy_answer_is_kept_until_it_expires_or_the_proxy_file_changes`:
  the first draw asks `voms-proxy-info`, the next do not; valid until `PROXY_MARGIN` s before the end, then asked
  again; an invalid answer kept while the file is the same; a changed or removed proxy file asks again; `fresh`
  always asks. `test_grid_proxy_check_is_quiet_and_handles_unavailable_tools`: `--timeleft` output, a short proxy,
  no proxy, unreadable output, missing tools and a timeout.
- `Tests/Utilities/test_operations.py` `test_a_menu_draw_reads_no_file_of_an_ended_operation`: the files one draw
  reads (`_read_json`, `os.path.exists`): all three directories the first time, then only the running one and the
  `seen` mark of an unseen one, none once all ended and seen; new objects whose events read from the top; an
  `exit.json` that comes later is seen; a directory removed by another menu leaves the list and the cache.
- `Tests/Utilities/test_menu.py` `test_a_menu_line_reads_only_the_new_events_and_none_once_ended`: "Running 1/2",
  then "Running 2/2" with the same reader, "Failed: 1" once ended, then no read. `_grid_ready` asks with
  `fresh=True` (`test_a_run_that_may_submit_needs_a_valid_grid_proxy`).
- `python Tests/run.py checks` on Windows: 13/15 (the known two: import debt in `check_import_boundaries`,
  `check_root`).

## 32. One curses session for the menu, panels over the screen, the grid password in the menu

**Change:** [CL §32](Refactor-2025.md#32-one-curses-session-for-the-menu-panels-over-the-screen-the-grid-password-in-the-menu)

- `Tests/Utilities/test_menu.py`: `test_one_session_for_every_screen_and_errors_in_a_panel` (two screens and an
  error in one `curses.wrapper`, nothing printed, the "Error" panel; outside a session `unreadable_run` opens its
  own, other keys do not close it); `test_the_main_menu_is_live_while_something_runs_behind_it` (`live` follows the
  running tests, "refresh" draws again, `timeout(2000)`, the selected line stays, no refresh when not live);
  `test_the_grid_password_panel_shows_stars_and_the_result` (only `*` drawn, backspace, Esc/empty/Ctrl-C cancel,
  the result panels); `test_in_terminal_leaves_the_screen_and_comes_back`;
  `test_grid_certificate_asks_the_password_in_a_panel_and_refreshes_after_renewal` (the password to
  `renew_grid_proxy`, the terminal fallback on None, errors in a panel, Esc renews nothing); the quit warning panel.
  The tests that counted `pause` now check `operation_error`.
- `Tests/Utilities/test_test_run.py` `test_kill_now_while_it_stops_asks_first` (K only while it stops, N keeps it,
  Y kills, the panel words); the stop question panel. `Tests/Utilities/test_operation_screen.py`: the panel.
- `Tests/Framework/test_interactive.py`: `test_grid_proxy_renewal_gets_the_password_on_stdin` (argv with
  `-pwstdin`, the password as stdin, a proxy that is not valid after "Done", a wrong password, no `-pwstdin` ->
  None, a timeout, no VOMS tools; nothing printed), `test_grid_proxy_renewal_in_the_terminal_checks_result` (the old
  terminal path); `FakeUI` records the panels instead of the pauses; errors are panels, nothing is printed.
- `Tests/Utilities/test_preview.py`: every scenario draws, the three new ones too.
- `python Tests/run.py checks` on Windows: 13/15 (the known two: import debt in `check_import_boundaries`,
  `check_root`); FastSetup's `unit.setup` OK (its checklist outside a session).

## 33. Start a new run and Esc answer at once

**Change:** [CL §33](Refactor-2025.md#33-start-a-new-run-and-esc-answer-at-once)

- `Tests/Framework/test_configs.py` `test_the_scan_is_kept_while_configs_is_unchanged`: two `copy_warnings`, one
  scan; a changed template and a new template scan again (the warning follows the new version); a FileIO given by
  the caller always scans.
- `Tests/Utilities/test_menu.py` `test_terminal_open_and_initialization_failures`: `ESCDELAY` 25 unless set (100
  kept), `set_escdelay` with it.
- Profile (Windows, `cProfile` over the 4 recipe previews): before 1.76 s under the profiler, 93 % in
  `copy_warnings` -> `scan`; after: 0.18 s, then 0.08 s per list.
- `python Tests/run.py checks` on Windows: 13/15 (the known two).

## 34. Start and Continue/Inspect read their lists ahead, and open at once

**Change:** [CL §34](Refactor-2025.md#34-start-and-continueinspect-read-their-lists-ahead-and-open-at-once)

- `Tests/Utilities/test_menu.py`: `test_prefetch_runs_each_key_once_and_in_order` (without a thread: at once, a job
  that adds one, an error dropped; with the thread: a key queued once while it runs, the order, `wait`);
  `test_the_menu_reads_the_lists_ahead` (the menu's start reads every recipe and run with a real thread);
  `test_start_lists_at_once_and_fills_in_the_checks_as_they_come` ("checking...", live, the job asked once, the
  focus kept); `test_continue_lists_at_once_and_fills_in_the_runs_as_they_come` (loading rows after the read ones,
  the selected run kept while the rows move); `test_rows_still_read_say_so_and_the_list_draws_again` (the labels,
  `timeout(500)`, "refresh", no UNREADABLE for a loading run). The navigation mocks get `kept_*` that read at once.
- `Tests/Framework/test_interactive.py` `test_kept_previews_and_rows_last_until_their_files_change`: never read ->
  None; kept until the recipe file changes; an unreadable recipe (its problem) and one whose check raises (its
  error) are kept too; a run row until `run.json` is saved again; `runs()` and `run_directories()`.
- Windows timing with the real adapter and a threaded `Prefetch`: read-ahead 0.19 s, then the Start list's data
  0.004 s.
- `python Tests/run.py checks` on Windows: 13/15 (the known two; `check_import_boundaries`: 0 new pairs).

## 35. The pico tuple contract (PicoProducer -> Histogrammer)

**Change:** [CL §35](Refactor-2025.md#35-the-pico-tuple-contract-picoproducer---histogrammer)

- `Tests/contracts/test_pico_tuples.py` (9 tests): `NamesTests` (tree, cutflow, file name on both sides),
  `CutflowTests` (Histogrammer bins, stitching bins, every channel module's bins, the cuts of
  `ModuleTauPair.fillhists`), `BranchTests` (channel -> tree producer, add-on against the scripts, configs against
  the producers).
- `Tests/Histogrammer/api/test_control_hists.py` `test_branch_problems` (fake reader: a missing weight branch in
  one MC file, a missing cut alias in a data file, `-r`, no check without ROOT/samples/real pattern, an unreadable
  file); `test_tes_shapes.py` `test_branches_of_the_nominal_tuples` (removeSFs not needed, DY/TT extra weights,
  `$VSJET` -> the tagger's discriminant, split cuts only for MC).
- Mutations (by hand, not kept): `weight_no0PU` at bin 18 fails the Histogrammer and the module test; an unknown
  branch in every config, a stale `KNOWN_DEBT` row, an add-on branch removed from the list each fail.
- `python Tests/run.py checks` on Windows: 14/16 (the known two: `check_import_boundaries` known debt, `check_root`).

## 36. The production record: kind and sum of weights on the tuple artifacts

**Change:** [CL §36](Refactor-2025.md#36-the-production-record-kind-and-sum-of-weights-on-the-tuple-artifacts)

- BBB: `framework.production` re-locked with the user's approval, only that case (`kind`/`sumw` added to its two tuple
  records; `sumw` 18.5 for both tuples = their cutflow bin 17).
- PyROOT 6.30 `TFile.Open` raises `OSError` on an unreadable file, which crashed the branch preflight of CL §35
  (`unit.histogrammer.api` `test_sample_files`); `branches.tuple_branches` now returns None for it (test added).

- `Tests/contracts/test_pico_tuples.py` `ProductionRecordTests` (2 new tests, 11 in the file): `TupleArtifact.kind`
  = `tuples` = the production stage's `outputs` = the planned record = the `tuples` slot of `controlhists` and
  `shapes`, and the local stages filter with the slot's kind; `merge.py` `SUMW_BIN` = the contract's normalisation
  bin (17); the API passes `MergeResult.sumw` on.
- `Tests/Framework/test_stages.py` `test_pattern_problems`: a record without a kind is refused with the CL §36
  message; only kind `tuples` gives the pattern (another kind is ignored); the CL §16 message (no pattern) and
  "several places" still come for kind `tuples`. `test_framework.py`: the planned record has `kind: tuples`.
  `Tests/Framework/fakes.py` `Artifact` gets `sumw`, `kind` (as `TupleArtifact`). Framework: 206 tests pass.
- `cutflow_bin` and the merge read need ROOT: checked on lxplus by BBB `framework.production` (the `sumw` of its two
  merged tuples in `run.json`) and `pico.merge` (unchanged: the merge's files).
- `python Tests/run.py checks` on Windows: 14/16 (the known two: `check_import_boundaries` known debt, `check_root`).

## 37. Inputs are given, never found

**Change:** [CL §37](Refactor-2025.md#37-inputs-are-given-never-found)

- D0: `python Tests/run.py bbb list` lists `histogrammer.tes_inputs_picodir`; `python Tests/run.py checks` on
  Windows 14/16 (the known two). The case needs ROOT: locked on lxplus with the whole suite (`bbb lock --replace`,
  then `bbb diff`: every other case `same`, this one `ADDED`).
- D1: `Tests/Histogrammer/sample_model/test_tupledir.py` (new, in `unit.histogrammer.sample_model`): the env
  variable before the default file, the default path is `PicoProducer/config/config.json`, a missing or unreadable
  file and a missing/empty/non-string `picodir` are errors naming `--tuples`, PicoProducer is not imported (the test
  checkout has no `TauFW.PicoProducer`); with ROOT, the core refuses `$PICODIR` without tuples.
  `Tests/Plotter/testTupleLocation.py` (normal, ROOT): `test_default_reads_picodir_of_the_configuration` became
  `test_no_tuples_is_refused` (no `getconfig` call) and `test_script_default_reads_picodir_of_the_configuration`
  (the helper with `$TAUFW_PICO_CONFIG` gives the same files). `check_import_boundaries`: Histogrammer ->
  PicoProducer 1 / 1 / 1, totals 20 / 19 / 17, 0 new pairs. Windows `checks` 14/16 (the known two).
  The script default itself: BBB `histogrammer.tes_inputs_picodir` on lxplus, without re-lock.
- D2: `Tests/Histogrammer/api/test_control_hists.py`, `test_tes_shapes.py`: every request names its tuples (a
  `Request` helper / the `request()` default), the expected commands have `--tuples`, `env == ()` everywhere; a
  request without tuples (None, "") is a `ValueError`, with `pico_config=` a `TypeError`; the picodir preflight
  checks are gone (`test_absolute_setup`, `test_output_directory_problems`). `Tests/Fitter/api/test_tes_id.py`
  `test_no_pico_config`. `Tests/Utilities/test_process.py` `OutputDirectoryTests`: the tuple pattern only,
  `pico_config=` a `TypeError`. `Tests/Framework`: no `pico_config` in the fakes' requests; `test_pattern_problems`
  the placeholder before production is planned; `test_null_gives_no_tuples` (D3 turns it into the recipe error).
  Windows: Histogrammer API 30, Fitter API 15, Utilities 200, Framework 206 pass (`test_run_lock` heartbeat failed
  once on a slow run, then three runs clean: timing, not this change); `checks` 14/16 (the known two).
- D3: `Tests/Framework`: the stages that read tuples name `{external: <pattern>}` (`fakes.TUPLES`, a pattern whose
  fixed part is `Tests/Framework/`, so the preflight finds it) or a production stage; the fit reads a shapes stage of
  the recipe (`test_stages`, `test_interactive`, `test_framework`) or another run's (`test_validation`: a stage
  directory with a manifest made in `setUp`; `test_bundle`, `test_manifest`: a `{path: ...}` value only). New:
  `test_stages.test_null_is_a_recipe_error` (tuples of hists and shapes, the fit's shapes: the message, what null
  meant, what to write), `test_bundle.test_null_only_where_the_stage_allows_it` (the message; the `null_inputs` hook
  still works), `test_validation.test_pico_config_only_with_production`, `test_production_tag_warning` (only when the
  tuples are read), `test_python_step` (no `$TAUFW_PICO_CONFIG` in the command, `ctx.pico_config` given),
  `test_stages.test_plan_shows_commands_and_notes` (no "PicoProducer config:" line without production). The tests
  with `pico.config` now have a production stage (`test_bundle`: `ProductionStage` with a fake PicoProducer).
  `check_recipe` of the four `Analyses/` recipes: `example_mutau_short`, `example_mutau_long` OK, `tes_id_2025` only
  the EOS directory (Windows), `example_broken` its four intended errors. Framework 208 tests pass; `checks` 14/16.

## 38. One rule for the paths in a recipe

**Change:** [CL §38](Refactor-2025.md#38-one-rule-for-the-paths-in-a-recipe)

- `Tests/Framework/test_bundle.py`: `test_path_rule` (was `test_bundle_module_absolute`: `missing` for a Fitter file
  and a directory, `channel` only where the option takes one, `outside` for `../`, `/afs/...` absolute on Windows),
  `test_module_paths_are_refused` (was `test_shapes_configs_are_never_module_paths`: shapes, fit and controlhists,
  the message), new `test_paths_above_the_bundle` (absolute once loaded, not a bundle file, the same file when read
  against a run's bundle copy), `test_make_bundle_copies_the_templates_and_channel_setups` (was `..._module_configs`),
  `test_plan_resolves_against_the_bundle` (`channel`); `test_path_inputs` and `test_path_input_inside_the_bundle`
  write the files their recipes name. `test_validation.py`: `test_run_root_is_not_expanded` (was
  `..._is_expanded_with_a_warning`: `~`, `$VAR`, `$USER` inside an absolute path), the undefined-variable case of
  `test_run_root_problems` is gone, `test_files_the_recipe_names` and `test_structure_and_files_together` (the
  recipe's message first). `test_samples.test_module_path_is_refused`, `test_python_step.test_preflight_keeps_the_step_new`
  (a missing step file is a `RecipeError`). `Tests/Fitter/api/test_tes_id.py`: no `config_file`.
  `check_recipe` of the four `Analyses/` recipes: as before (`tes_id_2025` only the EOS directory on Windows,
  `example_broken` four problems, the fourth with the new wording). Framework 209 pass.

## 39. `getmcsample` takes the tuples instead of reading the PicoProducer configuration

**Change:** [CL §39](Refactor-2025.md#39-getmcsample-takes-the-tuples-instead-of-reading-the-picoproducer-configuration)

- Callers: `grep -rIil getmcsample` over every file of the repository, `mcsample` variants, the star imports of
  `TauFW.Histogrammer.sample.utils` (`Sample.py`, `SampleSet.py`: no call through them) and `git log --all -S
  getmcsample`: only the two Legacy scripts.
- `Tests/Plotter/testTupleLocation.py` (ROOT, lxplus): `test_getmcsample_tuples_instead_of_the_configuration`
  (MC file and a `tag` variation from `tuples=`, `getconfig` not called), `test_getmcsample_without_tuples`
  (`ValueError` for the default pattern, a full `fname=` works).
- `Tests/Plotter/testScriptFlow.py` (ROOT, lxplus): `MC` -> `gethist` (bin contents) -> `Plot` -> `saveas` (file
  written). Registered in `Tests/inventory.json` and `check_harness`.
- Windows: `py_compile` of the library, both Legacy scripts (they need Run 2 tuples and are not run) and both
  tests; `check_import_boundaries`: no Histogrammer -> PicoProducer row, totals 19 / 18 / 16, 0 new pairs;
  `python Tests/run.py checks` 14/16 (the known two: known debt, no ROOT). `Utilities/IOInventory.md`: the
  `sample/utils.py` row regenerated.


## 40. The user config: infrastructure (`Analyses/UserConfig.yaml`, `TauFW.Utilities.UserConfig`)

**Change:** [CL §40](Refactor-2025.md#40-the-user-config-infrastructure-analysesuserconfigyaml-taufwutilitiesuserconfig)

- `Tests/Utilities/test_userconfig.py` (8 tests, no ROOT): the public `UserConfig` has only the reading side
  (`create`, `check` only in `manage`), location (checkout / `$TAUFW_USER_CONFIG`), a missing file
  (defaults, `require` names the file, the key and the create command, the warning), `create` writes once and never
  overwrites, dotted keys / sections / copies, every broken header and a YAML syntax error name the file,
  `check()` never raises, and the package imported as a top-level `UserConfig` (FastSetup, before `cmsenv`).
- `Tests/Setup/test_fastsetup.py`: `test_user_config_is_created_once_and_named_in_the_summary` (`Created`, then
  `Kept` with the edit kept, the summary line, a warning without `Analyses/`). The helper imports `UserConfig` only
  for its `userconfig` command, so `test_shell_finds_helper_before_and_after_checkout_relocation` (a fixture with
  `Installer/` only) still passes.
- `Tests/Framework/test_framework.py`: `test_user_config_warns_in_one_line_and_the_command_creates_it` (`check`,
  `plan`, `start` warn while missing / not reviewed, exit 0; `taufw.py userconfig` creates, then keeps).
  `test_interactive.py`: `test_the_user_config_is_not_a_recipe`. The `CommandLineTests` of `test_framework.py` and
  `test_stages.py` use `checkout.reviewed_user_config`, so they do not depend on the checkout's own file.
- BBB: `pico_harness.PicoWorkspace.env()` sets `$TAUFW_USER_CONFIG` to a reviewed file of the workspace;
  `framework.production` keeps its `plan` lines (no re-lock expected).
- Windows: Tests/Utilities 207 OK, Tests/Setup 61 OK, Tests/Framework 211 OK; `check_import_boundaries`: no new pair
  (fails only on the known debt).

## 41. The user config's settings: run_root and the production settings

**Change:** [CL §41](Refactor-2025.md#41-the-user-configs-settings-run_root-and-the-production-settings)

- `Tests/Utilities/test_userconfig.py` (12 tests): the lxplus guesses (`taufw/` on EOS; `run_root` only with an AFS
  work area; nothing elsewhere), an existing `config.json` wins over them (empty values not taken over, an unreadable
  file ignored), a new file reads back every value written and the rest as unset, wrong settings named by key
  (`~` and `$` in `run_root`, text, empty, whole numbers, `True` is not a number), custom sections are not checked.
- `Tests/Framework/test_user_settings.py` (13 tests): the mapping to configuration keys and request defaults, the
  recipe wins (`queue`, `ncores`), no `ncores` anywhere leaves PicoProducer's default, a wrong setting raises where
  used, `run.json` names the settings (and has no `user_config` key without them), `run_root` precedence
  (`--run-root` > recipe > user config), the warning disappears, a wrong `run_root` stops `start` but not the
  warnings, `check_recipe` problem for a production recipe only, `plan` lines, `plan` ends in one line on a wrong
  setting.
- `Tests/Framework/checkout.py`: a neutral user config for the whole directory.
- lxplus 2026-10-27: `taufw.py userconfig` and `plan Analyses/example_mutau_short` as expected; the first
  `bbb check` failed `framework.production` (`stages[0].request.ncores: int -> NoneType`, run.json recorded the
  recipe's options); fixed by recording the effective request (`request_fields`), tested in `test_user_settings.py`
  (`ncores` 4 without settings, 8 from the user config, in the request and in run.json).
- Windows: Tests/Utilities 212 OK, Tests/Framework 224 OK, Tests/Setup 61 OK; `py_compile` of
  `PicoProducer/python/api/producer.py`; `check_import_boundaries`: no new pair.
- Not run on Windows (needs PicoProducer): `from_config(overrides=)` with a real configuration; on lxplus
  `bbb check` must pass without re-lock (no settings in the BBB workspace's user config).

## 42. The menu's run status says READING STATUS, and a stopped run is PAUSED

**Change:** [CL §42](Refactor-2025.md#42-the-menus-run-status-says-reading-status-and-a-stopped-run-is-paused)

- `Tests/Utilities/test_operation_screen.py`: the command screen's state line is `READING STATUS | 01:01 | taufw.py
  status` while it runs and `01:01 | taufw.py status` once done, never `RUNNING` or `DONE`;
  `test_a_command_screen_before_its_first_line`: `READING STATUS` / `READING PLAN` and their empty Output line
  instead of `(no output yet)`.
- `Tests/Utilities/test_menu.py`, `test_a_running_run_that_no_advance_works_on_is_paused`: `RUNNING` with an
  advance behind the menu or a live lock; `PAUSED` with a lost lock or a stopped advance; a `WAITING` run unchanged
  and its lock not read.
- Windows: Tests/Utilities 236 OK (9 skipped), Tests/Framework 227 OK.
- Open on lxplus: [TODO.md](TODO.md) section 1 (a real terminal, an advance from a second terminal).

## 43. A channel setup can leave out the QCD estimate (`qcd: false`)

**Change:** [CL §43](Refactor-2025.md#43-a-channel-setup-can-leave-out-the-qcd-estimate-qcd-false)

- No Windows test: `fillhists.py` needs ROOT. The default path (no `qcd` key) is the line it was, so the BBB
  control-plot baselines stay valid.
- Open on lxplus: [TODO.md](TODO.md) section 1 (a mumu setup with and without `qcd: false`).

## 44. Retry of a failed local stage; the bundle copy is checked at every advance

**Change:** [CL §44](Refactor-2025.md#44-retry-of-a-failed-local-stage-the-bundle-copy-is-checked-at-every-advance)

New and changed unit tests (Windows, no ROOT; `python -m unittest` in `Tests/Framework` and `Tests/Utilities`):

- `Tests/Framework/test_python_step.py` `RetryTests` (real python steps through `step_runner.py`):
  - `test_retry_runs_the_failed_step_again_and_keeps_the_finished`: the CDTest case. A step fails without
    `sf/tauid.json`; adding it to the source bundle changes nothing, and `advance` leaves the stage FAILED; with the
    file in the run's bundle copy, `retry` makes the run DONE. The finished stage did not run again (same history,
    same file time). `retries` = attempt 1, the failure message, `logs/need/attempt1`, `{sf/tauid.json: added}`. The
    archive holds the failed log, `context.json` and `stage/partial.txt`; `stages/need/` holds only the new
    manifest. One bundle warning; `bundle.changed` in run.json; manifests: `make` false, `need` and `after` true;
    a never-retried stage has no `retries` key in run.json; a second retry of the DONE run raises `RetryError`.
  - `test_every_retry_is_archived_on_its_own`: two retries without a fix give `attempt1/` and `attempt2/`, each
    with its own log and output; `bundle_changed` `{}`; no warning.
  - `test_a_bundle_change_is_warned_once_per_change`: `bundle.sha256` equals the copy at the start; edit, same,
    edit back, remove, same: 3 warnings, `changed` = `changed`, `{}` ("changed and changed back"), `removed`.
  - `test_a_run_without_bundle_hashes_is_not_checked`: run.json without `bundle.sha256`: the retry works,
    `bundle_changed` is `null`, no warning, no `changed`.
- `Tests/Framework/test_framework.py`: `test_failed_chunks_resubmit_until_max_tries` (a FAILED production stage:
  `failed_stage`, `retryable_stage` None, `retry` raises "cannot be retried yet: start a new run", nothing called or
  saved); `test_start_and_advance_map_to_the_framework` (`taufw.py retry` of a DONE run: exit 1 and one line);
  `test_parser` (`retry RUN --wait --take-lock`).
- `Tests/Framework/test_manifest.py`: the manifest has `bundle_changed: false`.
- `Tests/Framework/test_interactive.py`: `test_terminal_runs_offer_inspection_without_advancing` (FAILED: "Run failed
  at fit", Retry first); `test_retry_of_a_failed_run` (`taufw.py retry RUN --wait` behind the menu, its run screen).
- `Tests/Utilities/test_menu.py`: `test_continue_on_a_failed_run_offers_its_retry` (retry, inspect, back),
  `test_the_retry_choice_says_what_it_does` (the description with the failure and the bundle changes).
- `Tests/Utilities/test_run_screen.py`: `test_failed_card_says_whether_the_stage_can_be_retried`.

Results on Windows (2026-10-27): `Tests/Framework` 189 tests OK (test_python_step, test_framework, test_manifest,
test_bundle, test_interactive, test_stages, test_run_lock, test_interrupts, test_validation); `Tests/Utilities`
test_menu and test_run_screen 74 tests OK; the whole directories (`python -m unittest discover`): `Tests/Framework`
242 OK, `Tests/Utilities` 241 OK (9 skipped). `python Tests/run.py checks`: 14 of 16 pass; `check_root` (no ROOT on
Windows) and `check_import_boundaries` (known debt only, 0 new pairs) fail as before.

BBB: not run on Windows. `framework.production` writes no `bundle.sha256` (no bundle files) and no `retries` (no
retry), so its run.json snapshot is unchanged; to confirm on lxplus without re-lock: [TODO.md](TODO.md) section 1.

## 45. A read-only Markdown reference beside the terminal editor

**Change:** [CL §45](Refactor-2025.md#45-a-read-only-markdown-reference-beside-the-terminal-editor)

Focused Windows checks (2026-10-27, Python 3.13.8, no ROOT or real curses session):

- In `Tests/Utilities`: `python -B -m unittest test_editor test_menu` — 85 tests OK. New editor cases exercise
  independent scrolling and focus, ignored editing keys in the reference, F2 save from either pane, narrow-terminal
  show/hide, resizing with both positions preserved, horizontal scrolling, 40-column and 110-column boundaries,
  missing/invalid UTF-8 references, modal key priority, Markdown/code/table rendering, Unicode wrapping, reflow within
  a paragraph, the actual UserConfig.md and an empty file. Existing standalone-import, save and cleanup checks pass.
- In `Tests/Framework`: `python -B -m unittest test_interactive.MenuTests.test_user_config_editor_opens_the_override_and_reuses_config_validation`
  — 1 test OK; the manual comes from this checkout even with an external config override. Menu tests check forwarding
  the caller's title/reference and retaining the existing branding and exception boundary.
- Inspected the simulated 120 x 24 frames with the actual manual: YAML on the left, wrapped manual on the right,
  focus markers, separate line ranges and the pane controls. `git diff --check` passes.

The real terminal/SSH key and resize check remains in [TODO.md](TODO.md) section 1. No batch or BBB run was needed.

## 46. Continue and Retry show how long the finished stages took

**Change:** [CL §46](Refactor-2025.md#46-continue-and-retry-show-how-long-the-finished-stages-took)

New unit tests (Windows, no ROOT):

- `Tests/Framework/test_interactive.py` `test_the_run_screen_gets_the_times_of_the_earlier_advances`: a DONE shapes
  stage with two recorded commands gives `seconds` 81.5, both commands (label, seconds, status, log) and the last log;
  a FAILED fit with only history gives the time between its first and last entry (26:30:05); a WAITING stage gets no
  time.
- `Tests/Utilities/test_run_screen.py` `test_the_times_of_the_earlier_advances_are_shown`: the stage list shows
  `26:00:00`, `01:15` and nothing for a NEW stage; the Details say "Took 01:15 in an earlier advance." and list the
  commands `[ ok ]` and `[FAIL]` with their times; the log is the last command's; after the retry's `stage_state`
  NEW and `stage_step` the stage starts from zero, the finished one keeps its time.

Results on Windows (2026-10-27, `python -m unittest discover`): `Tests/Framework` 243 OK, `Tests/Utilities` 250 OK
(9 skipped). The real screen (a long run on lxplus, Continue and Retry): [TODO.md](TODO.md) section 1.

## 47. The example analyses move to Analyses/Examples/, listed under [Examples] in the menu

**Change:** [CL §47](Refactor-2025.md#47-the-example-analyses-move-to-analysesexamples-listed-under-examples-in-the-menu)

New and changed unit tests (Windows, no ROOT):

- `Tests/Framework/test_interactive.py` `test_default_recipes_are_the_analysis_bundles`: the recipe list of the
  checkout has no `Examples` row and ends with `Enter another recipe path`, `[Examples]`, `Back`;
  `test_examples_are_listed_under_examples`: `examples()` lists `broken`, `cmsdas26_ztt`, `mutau_long`,
  `mutau_short`; [Examples] shows them with only `Back`, `broken` red (the validation demo), and starting
  `cmsdas26_ztt` runs `taufw.py start Analyses/Examples/cmsdas26_ztt --wait`. The tests that left the list with
  Back by its position now count the new row.
- `Tests/Utilities/test_menu.py` `test_examples_open_from_the_recipe_list`: [Examples] and Back return to the recipe
  list; [Examples] and a start return to the main menu; `select_recipe` gets `examples=True` for the examples only.
  The picker hints, the row colors (the `[Examples]` row is accent; the examples list has no create row and its
  edit keys are on the examples) and the semantic actions (`examples`, and the examples list: `select`, `back`).
- `Tests/Framework/test_validation.py` `test_the_bundled_analyses_have_no_problems`: also `Examples/cmsdas26_ztt`;
  `test_framework.py` and `test_interactive.py` read the examples at their new paths.

Results on Windows (2026-10-27, `python -m unittest discover`): `Tests/Framework` 248 OK, `Tests/Utilities` 254 OK
(9 skipped), `Tests/contracts` OK. The menu on a real terminal: [TODO.md](TODO.md) section 1.
