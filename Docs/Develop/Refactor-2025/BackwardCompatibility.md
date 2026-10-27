# Backward compatibility audit

**Audit date:** 2026-10-21

**Branch / audited code:** `Refactor-2025`, `1103958233b95ae798c645f65aef5b41f8915542`

**Pre-refactor reference:** `0b174cf8122899bfbe5e5f03378d27e2d5c932fa` (`949ce56^`, before Test Migration 1)

**Scope:** existing commands, Python functions and methods, imports, configuration, stored outputs, job continuation, and scientific results.

## 1. Verdict

**This branch is not a drop-in replacement for the pre-refactor checkout.** Much of the numerical implementation is preserved, but several old commands and imports already fail, some defaults and operational decisions deliberately changed, and several compatibility layers are scheduled for removal.

The practical answers are:

| Question | Answer |
|---|---|
| Does everything work exactly as before? | **No.** There are explicit command/import breaks, corrected bugs, different resubmission semantics, and incompatible intermediate file formats. |
| Can ordinary `pico.py` users keep their commands? | Mostly yes. The command vocabulary remains, but option precedence, chunking, validation and cleanup can behave differently. |
| Can users keep running `Plotter/plot.py`? | **No.** It prints a replacement command and exits **2**, without processing anything. Use `Histogrammer/fillhists.py`. |
| Can users keep running the old Fitter shape scripts? | **No.** Five old paths are diagnostic stubs, also exiting **2** without processing. |
| Are old Plotter Python imports supported? | Only a specific set of aliases. Drawing imports such as `TauFW.Plotter.plot.Plot` have already disappeared. |
| Can queued jobs survive the worker rename? | The retained `processors/` script forwarders support old job lists. This does not guarantee compatibility with every external task file or old software environment. |
| Can every old Framework run be resumed? | **No.** Only run-record schema 3 is accepted; recipes/records using retired stage types also fail. |
| Are physics outputs preserved? | There is strong, scoped evidence for covered histograms, plots and one TES/ID workflow. There is no repository-wide proof for every analyzer, correction, campaign and fit mode. |
| Will anybody need to change something? | **Yes:** private scripts, drawing users, direct shape-script callers, custom batch adapters, users of old recipe formats and archived workflows are the main groups. |

The right release description is **“preserved algorithms with explicit migration requirements and intentional behavior changes”**. “Fully backward compatible” would be inaccurate.

## 2. Evidence and limits of this audit

### 2.1 Reference and method

The reference matches the historical dependency audit in [old-evidence.md](dependencies/old-evidence.md). It precedes test relocation as well as the subsequent package moves. Changes introduced before that commit are not attributed to this refactor. Later changes within the branch are included even when an earlier audit or changelog section predates them.

The review used:

1. Both Git trees, rename information and current source, rather than documentation alone.
2. An inventory of **every historical Python file**, including tests, auxiliary/data scripts and archives, and its function/method definitions.
3. AST comparisons of matched definitions, followed by inspection of affected public APIs, call sites, command builders, parsers, module globals, shell drivers and readers/writers.
4. A source/build/config disposition inventory, including shell scripts, native code and data/configuration files.
5. Existing regression evidence, explicitly distinguished from focused tests executed for this report.

The reproducible inventory generator is [audit_compatibility.py](dependencies/audit_compatibility.py):

```bash
python3 Docs/Develop/Refactor-2025/dependencies/audit_compatibility.py
```

It reads committed Git contents, imports no TauFW code and writes documentation CSVs only. Its historical file scope comes from [old-source-files.csv](dependencies/old-source-files.csv). The report describes the audited commit; regenerating after code changes produces a new snapshot that must be reviewed with the report.

### 2.2 Complete static inventory

| Inventory | Count | Evidence |
|---|---:|---|
| Historical Python files | 405 | [compatibility-files.csv](dependencies/compatibility-files.csv) |
| Current Python files | 588 | Git tree read by the generator |
| Historical Python files parsed by AST | 362 | File inventory |
| Historical Python files requiring lexical recovery | 43 | File inventory, including the syntax error/recovery reason |
| Historical function/method definitions inventoried | 2,765 | [compatibility-functions.csv](dependencies/compatibility-functions.csv) |
| Matched definitions with identical AST | 2,404 | Function inventory: `same AST` |
| Matched definitions with changed AST | 137 | Function inventory: `changed AST` |
| Matched definitions with lexical evidence only | 53 | Function inventory: `lexical only` |
| Definitions without a matched current definition | 155 | Function inventory: `no matched definition` |
| Ambiguous definition matches | 16 | Function inventory: `ambiguous` |
| Historical source/build/config files | 552 | [compatibility-sources.csv](dependencies/compatibility-sources.csv) |
| Sources with an identical blob at a mapped destination | 231 | Source inventory: `same blob` |
| Sources with changed blobs at mapped destinations | 285 | Source inventory: `changed blob` |
| Sources without a mapped destination | 36 | Source inventory: `no mapped file` |

**These are inventory counts, not pass rates.** In particular:

- AST equality ignores comments/formatting but includes function bodies, signatures, decorators and docstrings. It says nothing about changed imported dependencies, module globals, call order, paths or external payloads.
- A changed AST can be only a renamed helper, a docstring or an import; it does not necessarily mean a changed result.
- A missing definition match is not automatically a deleted capability. Some old functions were split across pipelines or replaced by methods with different interfaces. The matrices below explain the important replacements.
- Lexical recovery records class/function scope from declarations and indentation; it is not a Python 2 interpreter. Those files have no AST equivalence claim.
- The 16 ambiguities include property getter/setter pairs and repeated definitions. Examples are `Variable.xmin/xmax`, `SampleSet.mcsamples`, two `SampleSet.replace` definitions and duplicate `ensureDirectory` definitions. Later definitions still shadow earlier ones; this audit does not silently select one.
- Defined functions are inventoried, including private and nested definitions. Lambdas, implicit re-exports, monkey-patched attributes, dynamic imports and C++ functions inside strings are not separate rows. Their relevant migration effects are reviewed below.
- Native code is covered at file level: **18 `.C`, two `.cxx`, one `.cc`, one `.h`**. Fifteen map to identical blobs; the other seven differ by archive comment banners, with no non-comment line changes found. That preserves implementation text, not the old macro paths or runtime environment.

This is an extensive source audit with focused execution, not a claim that all 2,765 definitions were individually exercised on real data.

## 3. Who is affected

| User / integration | Disruption | Concrete effect | Required response |
|---|---|---|---|
| Standard `pico.py` CLI, existing JSON configuration | Usually low; sometimes physics-relevant | Commands remain, but fixes alter options, splitting and cleanup | Read §6 before continuing production |
| Private sample catalogs importing `storage.Sample` | Low today | Explicit sample-class re-export remains | Prefer `TauFW.PicoProducer.datasets`; check inferred data types |
| Jobs queued with `python/processors/...` | Low while forwarders remain | Worker runs with an extra stderr warning | Let old jobs finish or regenerate lists before deleting forwarders |
| Private scripts importing moved `common` helpers | Immediate break | Old modules/functions are absent | Apply §5 mappings and keyword changes |
| Scripts importing drawing from `TauFW.Plotter.plot` | Immediate break | Drawing modules have no compatibility aliases | Import `TauFW.Utilities.Drawing` |
| Users running `Plotter/plot.py` or old Fitter shape entry points | Immediate break | Exit 2; no plots/shapes produced | Change executable path, config path and preserve intended working directory |
| Custom batch systems or templates | Immediate break unless updated | File-based automatic adapter discovery was replaced by a registry | Register the adapter and update template paths |
| Old analysis bundles / run directories from earlier branch revisions | High | Retired stages, old schemas and moved configs are rejected | Update recipes; start a new compatible run where required |
| Users redrawing version-1 control-histogram files | High if only histograms were retained | New reader refuses the file | Refill with the current writer; no converter is supplied |
| Legacy studies, tutorials and personal macro paths | Variable, potentially high | Imports, files, CWD assumptions or Python 2 environment no longer match | Use archive inventories and restore a suitable environment deliberately |
| TES/ID option-3 workflow with current drivers/configs | Managed migration | Paths and isolation change; scoped old/new comparisons exist | Use current drivers or the current bundle and compare the intended outputs |

The absence of an in-repository caller is not evidence that a private analysis does not use an interface. This matters especially for removed re-exports, custom batch adapters, monkey patches and legacy command paths.

## 4. Commands that change

### 4.1 Executables and working directories

`ARGS` below means the user's existing arguments **after updating any moved config, macro or data path**. Diagnostic stubs preserve the literal arguments in their suggestions; they do not rewrite a deleted configuration argument.

| Before | Current replacement | What the old command does now |
|---|---|---|
| From `Plotter/`: `python3 plot.py ARGS` | From the same CWD: `python3 ../Histogrammer/fillhists.py ARGS` | Prints guidance to stderr; exits 2; runs nothing |
| `python3 Histogrammer/plot.py ARGS` | `python3 Histogrammer/fillhists.py ARGS` from the same CWD | Same diagnostic behavior |
| From `Fitter/`: `python3 TauES/createinputsTES.py ARGS` | `python3 ../Histogrammer/shapes/TauES/createinputsTES.py ARGS` | Prints guidance; exits 2; runs nothing |
| From `Fitter/ETauFR/`: `python3 createinputs.py ARGS` | `python3 ../../Histogrammer/shapes/ETauFR/createinputs.py ARGS` | Same |
| From `Fitter/HighPT/`: `python3 createinputs.py ARGS` | `python3 ../../Histogrammer/shapes/HighPT/createinputs.py ARGS` | Same |
| From `Fitter/paper/`: `python3 createinputs.py ARGS` | `python3 ../../Histogrammer/shapes/paper/createinputs.py ARGS` | Same |
| From `Fitter/tutorial/`: `python3 createinputs.py ARGS` | `python3 ../../Histogrammer/shapes/tutorial/createinputs.py ARGS` | Same |
| `python3 Plotter/plot_postfit.py`, `plot_postfit_shift.py`, `plot_v10.py` | Scripts now under `Histogrammer/` | Old files are absent; no command forwarders |
| `Plotter/tutorial/plot.py` | `Histogrammer/tutorial/plot.py` | Directory moved; review tutorial config paths too |
| From `PicoProducer/`: `python3 python/processors/picojob.py ARGS` | `python3 python/workers/picojob.py ARGS` | **Forwards and runs**, with a stderr deprecation line |
| From `PicoProducer/`: `python3 python/processors/skimjob.py ARGS` | `python3 python/workers/skimjob.py ARGS` | **Forwards and runs**, with a stderr deprecation line |
| Hard-coded `python/processors/keep_and_drop_*.txt` | `python/workers/keep_and_drop_*.txt` | Old text-file paths are absent; script forwarding does not cover them |
| `python3 Plotter/test/<test>.py` / `PicoProducer/test/<test>.py` | Relocated `Tests/...` script or the registered `Tests/run.py` case | Old test directories are not retained as aliases |

**The Plotter/Fitter diagnostic stubs and PicoProducer worker forwarders have different contracts.** Merely finding an old script on disk is not proof that it still performs the old action. An automation that ignores exit status can proceed after a diagnostic stub and accidentally consume stale outputs.

For the main TES shape command, a current standalone example is:

```bash
cd Fitter
python3 ../Histogrammer/shapes/TauES/createinputsTES.py \
  -y 2025 -c ../Configs/Fitter/tes_id/config_coarse_TT.yml -j VTight -e Tight
```

Keeping `Fitter/` as CWD preserves the standalone `input_pt_less_region/...` output location. Moving the CWD to `Histogrammer/` changes relative output locations even if the executable and physics arguments are correct. `run_inputs*.sh` has been updated to call the moved script.

### 4.2 Config arguments and program options

| Usage | Migration / behavior |
|---|---|
| From `Fitter/`: `-c TauES_ID/config/config_coarse_TT.yml` | Use `-c ../Configs/Fitter/tes_id/config_coarse_TT.yml`; likewise `_PNet` and `_UParT` |
| From `Fitter/`: `-cmm TauES/config/FitSetup_mumu.yml` | Use `-cmm ../Configs/Fitter/tes_id/FitSetup_mumu.yml` |
| Explicit `Plotter/config/setup_<channel>.yml` | File is now `Configs/Histogrammer/setups/setup_<channel>.yml`; update the path relative to the actual CWD |
| `sys.path` / direct script path into `Plotter/config/samples*.py` | Tables now live in `Histogrammer/config/`; prefer explicit sample model files for new analyses |
| `makecombinedfitTES_SF.py --input_file FILE` | **Remove this argument.** It was unused and is now rejected. Shapes are supplied through `-i` |
| Standalone `makecombinedfitTES_SF_postfit.py` without `--impacts` | Impacts no longer run implicitly. Add `--impacts` to request them; `--impacts-parallel N` is now honored |
| `pico.py install cmmsw` | Misspelling is rejected; the spelling is `cmssw`. **Installation is still a stub**, not a working installer |
| Worker `--opt` | Generated commands now use the defined spelling `--opts`; the earlier abbreviation depended on argparse prefix matching |
| `Histogrammer/fillhists.py --hists` | Adds a histogram file and still draws by default |
| `Histogrammer/fillhists.py --hists --no-draw` | Writes histograms only; `-F`, `-p`, `-T` are ignored with a warning |
| `Histogrammer/fillhists.py --no-draw` without `--hists` | Usage error; there would be no output |
| `Plotter/draw.py FILE...` | New drawing-only command; it expects control-histogram files, not pico tuples |

The following additions are optional on the standalone paths; ordinary supported defaults are retained unless a separate fix below applies:

| Script / function | Added options |
|---|---|
| `fillhists.py`, `Histogrammer/shapes/TauES/createinputsTES.py` | `--tuples PATTERN`, `--samples FILE [FILE ...]` |
| Generic Histogrammer `sample.utils.getsampleset` | `tuples=PATTERN` |
| `Histogrammer/config/samples_v15.py:getsampleset` | `samples=[FILE, ...]` |
| `makecombinedfitTES_SF.py` | `--output_dir DIR`, `--plot_dir DIR` |
| `harvestDatacards_TES_idSF_MCStat.py` | `--output_dir DIR` |
| `plot2DScan_MultiDimFit.py` | `--outdir DIR` |
| `make_tid_2025.py` | `--sf-dir DIR` |
| Fit/scan/postfit label scripts and their two `makecombinedfit` drivers | `--lumi L`, `--cme E`; see [script option inventory](scripts_arg_changes.md#cms-label-of-the-fit-plots-changelog-27) |

With `--tuples`, the tuple directory pattern replaces PicoProducer configuration lookup on that path. In a shell, quote placeholders, for example `--tuples '/absolute/pico/$ERA/$GROUP'`. File names retain the sample/channel/variation conventions. `fname=` and the fit YAML's `samples.filename` are **not** replacements for this option: the old ignored-keyword defect L02 remains.

For explicit filling and later redrawing:

```bash
cd Histogrammer
python3 fillhists.py -y 2025 -c mutau -V m_vis -S baseline --hists --no-draw
python3 ../Plotter/draw.py hists/2025/mutau.root -o drawn/2025 -p
```

These commands use existing default tuple/sample configuration unless explicit options are provided. `draw.py` draws the entries stored in the file; it is not another invocation of the old tuple-reading `plot.py`.

## 5. Python API and import migration

### 5.1 PicoProducer

| Old import / interface | Current location / replacement | Compatibility |
|---|---|---|
| `TauFW.PicoProducer.storage.Sample.{Sample,MC,Data}` | `TauFW.PicoProducer.datasets` | Old module explicitly re-exports the same classes |
| `storage.Sample.Embdedded` | `datasets.Embedded` | Misspelling remains an alias **only in the old shim** |
| `TauFW.PicoProducer.tools.config` | `TauFW.PicoProducer.settings` | Old module removed; change imports |
| `storage.das` | `datasets.das` | Old module removed |
| `storage.utils.getstorage`, `isvalid`, `itervalid`, `iterevts` | `TauFW.PicoProducer.storage` | Old utility module removed; use explicit exports |
| `storage.utils.getsamples` | `TauFW.PicoProducer.datasets.getsamples` | Old import removed |
| `storage.utils.guess_sedir`, `guess_tmpdirs` | `settings.defaults` | Moved implementation; old import removed |
| `batch.utils.getbatch` | `TauFW.PicoProducer.batch.getbatch` | Old utility module removed |
| `batch.utils.chunkify_by_evts` | `TauFW.PicoProducer.jobs.chunkify_by_evts` | Old import removed; optional `progress` factory added |
| `batch.utils.getcfgsamples` | `TauFW.PicoProducer.jobs.getcfgsamples` | Old import removed |
| `batch.BatchSystem`, `batch.HTCondor`, site-specific adapter modules, `batch.SLURM` | `batch.base`, `batch.htcondor`, `batch.slurm`; factory through `batch.getbatch` | Class-bearing module paths changed; do not confuse configured system names with Python module names |
| `storage.StorageSystem`, `storage.EOS`, `T2_DESY`, `T2_PSI`, `T3_PSI`, `GridKA_NRG` modules | `storage.base`, `eos`, `t2_desy`, `t2_psi`, `t3_psi`, `gridka_nrg` | Old file/module names removed; class names generally retained |
| `TauFW.PicoProducer.pico.{common,config,job,run}` | `cli` for CLI dispatch; `api.PicoProducer` / `jobs` for programmatic use | No general re-export of the old modules |
| `processors.Bookkeeper` | `workers.Bookkeeper` | Same module/class through an alias, with `FutureWarning` |
| `processors.moddir` | `workers.moddir` | Re-export points to **workers**, where branch-selection files live |

The new `PicoProducer` API exposes `plan`, `iter_plan`, `submit`, `resubmit`, `status`, `merge`, `clean`, `run_local`, request/result records and explicit reporting. It replaces the old globally configured control-plane functions; it is **not** a signature-compatible rename of `preparejobs`, `checkchunks` or `getmodule`. See [public API](../../Manual/PicoProducer/API.md) and [jobs exports](../../../PicoProducer/python/jobs/__init__.py).

API reporting is silent by default; callers wanting familiar terminal messages must supply a reporter. File-touching API calls temporarily change process CWD to PicoProducer and restore it. They are not thread-safe. Callers that relied on importing `pico.common` to change CWD must make their own path policy explicit.

### 5.2 Histogrammer aliases: the precise supported set

The old Plotter package has **13 alias modules today**. Twelve correspond to names present in the pre-refactor reference; `sample.model` was introduced later in this branch.

| Old namespace | Current owner |
|---|---|
| `TauFW.Plotter.sample.HistSet`, `MergedSample`, `ResultDict`, `Sample`, `SampleSet`, `utils`, `model` | `TauFW.Histogrammer.sample.<same module>` |
| `TauFW.Plotter.plot.Context`, `Selection`, `Variable`, `string` | `TauFW.Histogrammer.spec.<same module>` |
| `TauFW.Plotter.plot.MultiDraw` | `TauFW.Histogrammer.sample.MultiDraw` |
| `TauFW.Plotter.methods.QCD_OSSS` | `TauFW.Histogrammer.methods.QCD_OSSS` |

These replace their entries in `sys.modules` with the target module. That preserves **module identity and shared mutable state**, including the era/luminosity globals used by `setera` and `Sample`. It avoids a second disconnected copy of that state. Source and alias-mechanism tests confirm the implementation; real ROOT imports remain environment-dependent.

This support does **not** extend to arbitrary `TauFW.Plotter.*` names. In particular:

- `TauFW.Plotter.plot.Plot`, `Plot2D`, `Stack`, `Ratio`, `CMSStyle`, `utils` and `TauFW.Plotter.sample.SampleStyle` have no aliases. They moved to Drawing.
- `TauFW.Plotter.api` now means the **new drawing-only API**. Importing `ControlPlots` / `PlotsRequest` from that name does not preserve the intermediate tuple-reading API contract.
- `SampleSet.gethists(method=...)` now loads methods under `Histogrammer.methods`. A privately installed method under `Plotter.methods` needs migration even though `QCD_OSSS` itself is aliased.
- Module names in `__module__`, tracebacks and newly serialized class references naturally follow current owners. Pickle/object identity compatibility beyond the explicit aliases has not been established.
- `TauFW.Plotter.plot.datacard` was already a broken import in `Fitter/MuTauFR/createinputs.py`; no alias was added to repair it.

### 5.3 Drawing, expressions and shape helpers

| Old | Current |
|---|---|
| `TauFW.Plotter.plot.{Plot,Plot2D,Stack,Ratio,CMSStyle}` modules | `TauFW.Utilities.Drawing.<same module>` |
| `TauFW.Plotter.plot.utils` histogram/graph helpers | `TauFW.Utilities.Drawing.hist_tools` |
| `TauFW.Plotter.sample.SampleStyle` | `TauFW.Utilities.Drawing.SampleStyle` |
| Drawing `LOG` formerly obtained from Plotter utilities | `TauFW.Utilities.Drawing.LOG` |
| Label helpers in `plot.string`: `makelatex`, `maketitle`, `makehistname`, `estimatelen`, etc. | `TauFW.Utilities.Drawing.labels`; also still re-exported through Histogrammer's `spec.string` |
| `getselstr`, `joinweights`, `joincuts`, `replacepattern`, `cleanbool` | `TauFW.Utilities.Expressions`; also re-exported through `spec.string` |
| `TauFW.Fitter.plot.datacard` | `TauFW.Histogrammer.shapes.inputs` |
| `TauFW.Fitter.plot.rebinning` | `TauFW.Histogrammer.shapes.rebinning` |

The Drawing `LOG` is a single shared instance used by drawing code and Histogrammer. It is not a promise that every remaining `TauFW.common.tools.log.Logger` object is that instance.

`Drawing.Plot` no longer re-exports Histogrammer's `Variable` / `Var`. Code such as `from TauFW.Plotter.plot.Plot import Plot, Var` needs **two** explicit imports:

```python
from TauFW.Utilities.Drawing.Plot import Plot
from TauFW.Histogrammer.spec.Variable import Var
```

`Plot` and `Plot2D` accept objects satisfying the required variable attributes rather than importing a concrete Histogrammer class. Histograms and supported Variable objects retain the intended drawing behavior; an arbitrary object with only a partial set of attributes is not guaranteed to work.

The Fitter shape helpers moved without a Fitter-side alias. Code importing `createinputs`, `plotinputs`, related writer helpers, `find_binedges` or `regular_binning` must follow the new modules. Old macro paths such as `Plotter/python/macros/Unroll.cxx`, `mapDecayModes.C`, and `Plotter/python/plot/MultiDraw.cxx` also need updating; Python import aliases cannot make those filesystem paths exist.

### 5.4 Numeric, table, loading-bar and process helpers

| Old interface | Replacement | Important difference |
|---|---|---|
| `common.tools.math.frange(start,end,step,scale)` | `Utilities.Math.float_range(start,end,step,scale)` | Same ordinary values; old module/name removed |
| `partition(mylist,nparts=None,nmax=None)` | `partition(items,parts=None,max_size=None)` | Rename keyword arguments; missing partition parameters raise `ValueError` instead of `IOError` |
| `partition_by_max(mylist,nmax)` | `partition_by_sum(values,maximum)` | **Does not sort/mutate the caller's list** |
| `columnize(oldlist,ncol=2)` | `columnize(items,columns=2)` | Rename keywords; ordering preserved |
| `reldiff(x,y)` | `relative_difference(x,y)` | Existing numeric rule preserved, including special handling of zero |
| `scalevec(a,b,r,log=False)` | `scale_vector(start,end,ratio,log=False)` | Rename keywords; invalid logarithmic inputs raise `ValueError`, replacing assertions |
| `magnitude(x)` | `Utilities.Math.magnitude(x)` | Existing rule preserved |
| `sqrt`, `log10`, `ceil`, `floor` imported through the old math helpers | Import directly from standard `math` | Implicit export compatibility is not retained |
| `round2digit`, `ceil2digit` | No direct replacement supplied | Removed; a private caller needs its own reviewed replacement |
| `common.math_helper` | Standard `math` for its former math exports | Old module removed |
| `Plotter.plot.MultiThread.MultiProcessor` | `Utilities.Process.ParallelProcessor` | `max=` becomes `max_parallel=`; use current handles rather than old helper-class internals |
| Intermediate `common.tools.parallel.MultiProcessor` | `Utilities.Process.ParallelProcessor` | Same migration; that intermediate module is also gone |
| `Thread`, `SimpleProcess`, `ReturnProcess`, old process target helpers | No supported import-compatible public replacements | Thread demos removed; process helpers became private implementation details |
| `common.tools.LoadingBar.LoadingBar(...)` | `CLI().loading_bar(steps, ...)` | `pre=` becomes `prefix=`; `count(message="",steps=1)` is the supported update operation |
| `LoadingBar.update`, `LoadingBar.message()` | `bar.count(message=..., steps=...)` as appropriate | Old methods removed; `.message` is now stored text, not that old callable |
| `common.tools.Table.Table(...)` / `LOG.table(...)` | `CLI(...).table(...)` | Construction/verbosity/prefix options move to the CLI/factory |
| `printheader(...,post=...)` | `print_header(...,suffix=...)` | Method and keyword rename |
| `printrow(...)`, `printtable()` | `print_row(...)`, `print_rows()` | Method rename |
| Table `header(...,post=...)`, `row(...)`, `str(table)` | `header(...,suffix=...)`, `row(...)`, `str(table)` | Names mostly retained, but `post` changes; current `save` arguments are explicit |
| `Logger.tableheader`, `Logger.row` | No retained logger methods | Removed |

Imports in this table omit the common `TauFW.` prefix. Normal queued-result iteration, serial process mode and retained formatting bytes are covered by existing tests/baselines. That does not preserve old internal class names, attributes, monkey patches or exception-catching code.

For example:

```python
from TauFW.Utilities.CLI import CLI
from TauFW.Utilities.Process import ParallelProcessor
from TauFW.Utilities.Math import partition

table = CLI(verbosity=1, prefix=">>> ").table("%s %d", minimum_verbosity=0, underline=True)
table.print_header("Sample", "Events", suffix=" total")
table.print_row("DY", 10)
chunks = partition([1, 2, 3], parts=2)
processor = ParallelProcessor(max_parallel=4)
```

Remaining `common.tools.{string,utils,file,root,log,RDataFrame}` modules still exist. The planned future Utilities migration must not be described as already implemented.

## 6. PicoProducer behavior changes

The CLI parser still exposes `list/get/set/rm/write/channel/era`, `run/submit/resubmit/status/hadd/haddclean/clean` and the existing abbreviations. Existing configuration keys and configured batch-system names are generally retained. **Keeping the CLI spelling does not imply identical execution.**

### 6.1 Options, resubmission and job splitting

Source: [worker_command.py](../../../PicoProducer/python/jobs/worker_command.py), [planner.py](../../../PicoProducer/python/jobs/planner.py), [chunking.py](../../../PicoProducer/python/jobs/chunking.py), [PicoProducer bug register](../Bugs.md#picoproducer), and the earlier [jobs/workers audit](JobsWorkersAudit.md).

| Change | Before | Current behavior | User consequence |
|---|---|---|---|
| Module option precedence, P08 | Channel options could override user `-E` | **Channel < sample < user**; later value wins | Conflicting options can change the analyzer settings and therefore physics output |
| Resubmit options, P09 | Channel/user options were merged again, duplicating entries | Previous merged list is reused, with new user options appended if absent | Editing channel options between tries no longer automatically changes resubmitted jobs |
| Positive sample `maxevts`, P06 | Inverted condition selected the wrong source | User > positive sample limit > configuration | Job count and grouping can change |
| `resubmit --split`, consequence of P06 | Could fall back to file-count splitting | Can use positive `config.maxevtsperjob` and split by events | More/different jobs even though `--split` itself is unchanged |
| Already split `file.root:first:max` inputs | Ranges were retained but omitted from the returned event total | Their available event range contributes, clipped at end-of-file | Total-event bookkeeping changes; represented ranges are not silently dropped from totals |
| Local run's default `-m -1`, P10 | Always appended | Only positive limits are emitted | Printed/generated command text changes; unlimited behavior remains intended |
| Generated worker option spelling, P12 | `--opt` abbreviation | `--opts` | Log/job-list comparisons and wrappers parsing command strings need updating |

The resubmission distinction deserves an explicit example:

1. First submission stores `tes=1.0` in the job configuration.
2. The channel definition is edited to `tes=1.02`.
3. A normal resubmit retains the previous `tes=1.0`; it does not rebuild the entire merged list from the current channel.
4. To explicitly override that try, pass `-E tes=1.02`; for a consistent changed production, use a new tag/submission.

Old job configurations can retain the old precedence order and duplicates. Resubmission does not normalize every historical options list. Do not assume that an old production and a fresh production with superficially identical CLI arguments now resolve conflicts identically.

### 6.2 Status, merge, cleanup and failures

| Change | Current effect |
|---|---|
| P04: `--checkqueue 1` | Actually queries the queue once and recognizes pending jobs |
| P05: empty sample selection | Submission reports that no samples matched |
| P11: local worker failure | Nonzero worker status is collected and warned about. The thin `pico.py` launcher does not turn the returned result records into a nonzero process exit; warnings are not a new shell failure contract |
| P19: merge followed by cleanup | Cleanup requires a readable, validated merged tuple and the relevant event-count agreement; invalid output keeps job inputs |
| Forced incomplete merges | `haddclean -f` / `hadd -r -f` can merge while retaining inputs when validation fails; `-f` does not waive the post-merge validation |
| P20: `submit --prompt` | Existing-config prompt no longer crashes; `y`/`f` submit, `n` skips |
| P21: expected-event checks | Analysis-channel status now forwards the check and can print mismatch warnings |
| P22: status side effects | Checking status does not create missing output directories; a warning can appear instead |
| P23: multiple tags in one job directory | Cleanup of one tag preserves unrelated tags' job configurations/lists/logs |
| P01/P03/P07 | Exception formatting, compressed JSON writing and the ineffective assignment are corrected |

These are intended corrections. They can still affect automation expecting a directory to appear, every forced merge to delete its inputs, old prompt responses, or byte-identical logs.

### 6.3 Configuration and samples

- `getconfig(verb=0, refresh=False, write=False)` now defaults to a **read-only** load. Missing keys can be repaired in memory without persisting them. Scripts that intentionally initialized the on-disk configuration by calling `getconfig()` must explicitly request writing on the normal config path.
- The CLI still loads with `write=True`. With `TAUFW_PICO_CONFIG`, the selected file is read-only even for that path, and a missing selected file is an error.
- Configuration is cached. Changing the environment/config file in a long-lived process does not override an already returned cached object unless the caller refreshes/reconstructs appropriately.
- Fresh-install era defaults now name existing catalogs, including split Run 2 eras and Run 3 entries (P17). Existing user `config.json` era mappings are preserved; updating the checkout does not rewrite every personal catalog mapping.
- The default test channel was removed when its module moved to `Tests.PicoProducer.analysis.TestModule`. A private config still naming `TestModule` through the old analysis namespace needs updating.
- Generic `Sample(...)` no longer forcibly labels everything MC. Data/embedded DAS paths can be inferred as data/embed, with a warning (S10). Repository catalogs using explicit `MC`/`Data` do not acquire this ambiguity, but private catalogs can see a substantive type change.
- `Sample.loadfiles` now replaces an inconsistent explicit event total with the sum of per-file counts (S11). Downstream bookkeeping depending on the old incorrect total changes.
- `getsamples(..., moddict=None)` replaces the shared mutable default dictionary. Explicit caches still work. Dynamic module state and Python's own import cache remain relevant.
- The known `Sample.loadjson` private-storage/DAS-format warning (S17) is still present; the reorganization did not fix it.

### 6.4 Batch/storage adapters and worker continuity

Configured names such as `HTCondor`, `HTCondor_NAF`, `SLURM_UCL` and `SGE` still select adapters. Python filenames changed to lower-case modules and templates moved into `batch/templates/`. **Adding a private `batch/<Name>.py` alone no longer works:** `getbatch` uses `batch.factory.SYSTEMS`. Site extensions must register a class and supply the expected templates. The base class now enforces its abstract interface under Python 3.

Storage fixes also change observable operations: EOS removal uses the removal command instead of overwriting the listing command; GridKA removal actually removes, and multi-input merges separate source paths; PSI construction and unmounted `cd()` no longer fail on the registered defects. SGE was rewritten as an actual `qsub`/`qstat` adapter; it has no real-site validation in the recorded evidence. NAF guessing remains deliberately unresolved: select `pico.py set batch HTCondor_NAF` explicitly where needed.

Old worker script forwarders run the new worker through `runpy` in the same process, preserve the arguments/worker exit status and adjust `argv[0]` and the script search path. They add a warning. Imports emit `FutureWarning`, so `-W error::FutureWarning` intentionally turns that compatibility path into a failure. The Run 2 JME import in `skimjob.py` is now conditional on JEC options; ordinary Run 3 skims need not install the standalone JME repository for that import.

Worker/analyzer equivalence is conditional on the **resolved command, inputs and payloads** being the same. The precedence/configuration fixes above can change that command without changing the worker's event-processing implementation.

## 7. Histogrammer, drawing and numerical compatibility

### 7.1 What the source comparison supports

The historical `Sample`, `MergedSample`, `SampleSet`, `HistSet`, `ResultDict`, `Variable`, `Selection`, `Context`, `MultiDraw` and QCD implementations largely remain at their new owners. Important families such as sample normalization, tree/histogram access, merging/splitting, RDataFrame construction, histogram retrieval and styling retain their bodies except for the specific differences identified in this audit. The function CSV permits inspection by old module and symbol instead of relying on a package-level assertion.

The changed-definition review found these additional distinctions:

| Function family | Source-level difference / consequence |
|---|---|
| `Selection.join` | Uses each selection's `.selection`, replacing the nonexistent `.cut` access. This fixes an old failure; exception behavior is not identical |
| `Variable.getnametitle` | Normalizes an empty/false tag to `""`, including `None`, before formatting; this changes edge-case failure/name behavior |
| `Sample.__init__`, `SampleSet.printtable` | Internal state imports point to Histogrammer; the old alias and new name share that state |
| `Sample.appendfilename` | Calls renamed `relative_difference`; the existing repeated sum-of-weights comparison is retained |
| Generic `getsampleset` / `getmcsample` | Updated config imports; the explicit `tuples` override exists on `getsampleset`. `getmcsample` takes an explicit `tuples=` since CL §39 (no PicoProducer configuration; `$PICODIR` without `tuples=` raises, `pico=` is gone); the two Legacy analyses keep their own copies, without the `pico=` defect |
| `HistSet`/`HistDict.display`, histogram/graph diagnostic tables | Use `CLI.table` and renamed print methods; covered formatting is intended to stay the same |
| `Stack.draw(ratio=...)` | Nonzero integer ratio values now imply one lower panel unless explicitly overridden, fixing bad `ratio=2/3` behavior |
| `gethistratio` | Accepts a graph denominator by building a histogram representation; formerly failing graph-denominator calls can succeed |
| `Plot` / `Plot2D` variable handling | Uses attribute-based checks rather than importing the old concrete Variable class |

“Moved unchanged” in the rename commits describes those individual moves. It does not erase fixes made elsewhere between the full pre-refactor reference and HEAD.

Drawing still has legacy ROOT/style import side effects, module-level CMS and sample-style state, and preserved quirks. The old table's ANSI underline/debug/warning behavior and loading-bar backspace bytes are intentionally retained. These are compatibility decisions, not newly cleaned interfaces.

### 7.2 Sample tables versus sample model files

Without `samples` / `--samples`, `Histogrammer/config/samples_v15.py` still executes its Python tables. With sample files, it dispatches to the model selected by exact era. There must be one matching file; no match or two matches is an error. The templates cover the table's supported Run 3 eras; this is not an automatic conversion of every historical custom `samples.py`, `samples_v12.py` or HighPT configuration.

The new path preserves table order, cross sections, weights, joins, stitching and splitting for the covered combinations. It intentionally omits the table path's 2022_preEE muon-dataset debug print. Unsupported combinations need not throw the exact same exception: for example, `2526` tautau/emu lacks model data entries and produces a model error instead of the old `%d` formatting failure.

**Normalization has two sources during transition:**

- The model path uses explicit `lumi` and `cme`; luminosity is passed to `setera` and each constructed sample.
- The old table path still relies on `CMSStyle.lumi_dict` when no luminosity is given.

At this snapshot the templates are tested against those table values. For 2025 that is **110.18 /fb**, not a new measurement supplied by this audit. The explicit model values preserve the current reference normalization. Editing a copied model's luminosity, cross sections or weights is a physics change even if every command stays the same. Updating a template without updating the legacy table default can also separate the two paths; the equality test exists to detect that.

Control-histogram metadata now records the normalization luminosity/energy; redrawing uses those facts. Shape artifacts carry them to fit plotting. This makes old/new label comparison dependent on the same normalization inputs, not just the era string.

### 7.3 Known problems that compatibility does not resolve

Source and [Histogrammer BUGS](../Bugs.md#histogrammer) still identify:

| Area | Existing limitation |
|---|---|
| File pattern | `fname=` versus `file=` means a custom `samples.filename` can be ignored (L02) |
| Histogram/label helpers | `sumhists` with multiple histograms fails; multi-argument `estimatelen` fails (L03/L04) |
| Expressions | Numeric zero weight formatting can fail; multiple replacements apply incorrectly; partially parenthesized OR cuts can change logical grouping (L05–L07) |
| Sample splitting / eras | `split=['DM']` uses an undefined name; unsupported electron/2526 channel branches remain problematic (L14–L16) |
| Default mumu variables | `fillhists.py` includes `m_ll` with no alias in the affected 2025 tuples (L17); selecting supported variables avoids claiming the full default list was validated |
| Standalone TES shape reruns | ROOT files opened with `UPDATE` retain obsolete histograms from previous configurations (L20) |
| Shape diagnostics/rebinning | Conditional control plots, limited channel cases, first-observable-only rebinning, sparse-region failure, wrong error accumulation and repeated tags remain (L18–L24) |

Several of these defects are intentionally preserved in regression expectations. A passing snapshot can establish “same old behavior,” including the same defect. It cannot establish scientific correctness for arbitrary inputs or cuts.

## 8. Fitter compatibility and scientific results

### 8.1 Current standalone versus Framework execution

The updated `run_inputs*.sh` and `run_workflow_zmm*.sh` call the new shape/config paths. Their continued presence supports those drivers, not every original script they once invoked. The Framework wraps the **uncorrelated DeepTau option-3 TES/ID workflow**; that is not validation or support for every corrTES/full-correlation/PNet/UParT fit mode.

Standalone scripts keep their historical default output derivations where no explicit output option is supplied. The Framework uses explicit output directories and absolute script/config paths, runs per era inside its own fit stage directory, and reads upstream shapes in place. These paths deliberately differ from standalone `Fitter/input_pt_less_region`, `output_pt_less_region`, `tau_sf`, `Measurements`, etc.

| Intentional difference | Consequence |
|---|---|
| F01/F02: workflow passes requested year to JSON merging and ID generation | A 2025 merge no longer accidentally selects 2024 corrections; non-default years are forwarded |
| F03: shape shell drivers capture mutau/mumu failure status correctly | A failed shape step is reported/skipped instead of being silently accepted |
| F04: remove required but unused `--input_file` | Old command lines explicitly supplying it fail until updated |
| F05: missing one-sigma intervals | Parameter file is still written, omitting unavailable `_1sigma_low/high` lines; parsers must tolerate absent lines |
| F06: impacts are opt-in | Direct postfit invocations can produce fewer files/run faster unless `--impacts` is supplied; current workflow driver supplies it |
| F07: correct rebinned-input path | Diagnostic plots can appear where the old code failed to find the file |
| F14–F18/F21: explicit path/output controls | Out-of-module execution works on the wrapped path; historical `str.replace` derivations remain when overrides are absent |
| Fit artifact collection | Describes this run's intended DeepTau correction files instead of collecting unrelated taggers' results from a shared directory |
| New label options | Plots can show the shape model's actual normalization; unknown-era labels no longer invent the old fixed 109 /fb fallback |

The source changes in four drawing paths (`postfit.py`, `postfit_TES.py`, ETauFR postfit and tutorial postfit) replace Histogrammer/Plotter `setera` with `CMSStyle.setCMSEra`. Existing label comparisons support equal text for the covered cases. **The old normalization-global side effect is intentionally gone:** a private caller that drew a postfit plot and then expected an unrelated Sample to inherit its era/luminosity must explicitly initialize sample normalization itself.

### 8.2 Earlier branch APIs that are also breaking

The pre-refactor reference had no Framework or these stage APIs. They are listed separately because users may already have adopted an intermediate `Refactor-2025` revision:

| Intermediate interface | Current interface | Compatibility |
|---|---|---|
| Old tuple-reading `ControlPlots` / `PlotsRequest` | `TauFW.Histogrammer.api.ControlHists` / `HistsRequest` | Renamed; drawing options moved to Plotter's separate request; no alias |
| `TauFW.Fitter.api.ShapesRequest` | `TauFW.Histogrammer.api.ShapesRequest` | Old export removed; `outdir` now required |
| `TauESID.plan_shapes`, `make_shapes`, `preflight_shapes`, `shapes_request` | Same-named operations on `TauFW.Histogrammer.api.TESShapes` | Fitter methods removed; change owner/constructor |
| Shapes request using Fitter-relative config paths | Explicit template, bundle or absolute paths on Framework path; API-relative paths resolve from Histogrammer | A raw path rename alone can select the wrong base directory |
| Old shared command/result record locations | `TauFW.Utilities.Process` | Existing documented API re-exports were retained where specified; prefer the shared owner |

### 8.3 How much numerical equivalence is established

The recorded comparisons are more specific than “the fit still works”:

- The R3 comparison used `f951dc0` as the unchanged-script reference, 2025 VTight/Tight inputs, and compared standalone defaults with the isolated Framework path. Parameter files and correction JSONs matched when the fit consumed the **same shapes**.
- Independently filled shapes differ around floating-point reduction precision. The recorded Framework/shell comparison found relative differences around `1e-13`; fitted POIs can move by one TES grid step (`0.00125`) and nuisance parameters along flat directions can move substantially.
- The later H4 old/new shape comparison used pre-H1 `0c611f4`: 43 files, the same keys in four ROOT files, and 775 histograms agreeing within `1e-12`. Largest old/new relative difference was `5e-13`; two current runs reached `1.07e-12`. All 96 LTF histograms had content and were compared there.
- CL §25–§27 recorded byte-identical control-plot PNGs before/after normalization-label propagation, a 28-case `setera`/`setCMSEra` text comparison, and a 23/23 BBB check on lxplus.

These are **historical validations recorded in this repository**, not runs repeated for this audit. They establish scoped equivalence of the migration steps and input choices they used. They do not prove bitwise equality of independently refilled production fits or full end-to-end equivalence to the pre-refactor tree, which also contained bugs deliberately fixed later. See [validation record](ValidationAndTests.md) and [R3 comparison](scripts_arg_changes.md#verification-on-lxplus).

### 8.4 Remaining scientific/reliability gaps

- Fitter options 4–6 retain registered defects F08/F09/F10/F26. Option 3 does not cover them.
- Several fit scripts still call nested commands with ignored `os.system` return codes. A top-level zero exit can coexist with a failed nested command. Framework expected-output checks improve detection but are not a proof of convergence or valid uncertainties.
- F19/F24 can create default/dummy scale factors when fit inputs are missing; F20 can exit successfully without producing output. This is an existing correctness risk, not something a module rename fixes.
- Shared-CWD standalone execution retains wildcard moves, era/config collisions and path replacement hazards (F11–F13/F18/F23). Framework isolation avoids some, not all, underlying defects.
- Analyzer/correction bugs in the PicoProducer register remain open, including required `era` arguments, missing branches/tools and campaign limitations. Worker forwarding does not validate those analyzers.
- The maintained 2025/2026 production pipeline does not provide a complete integrated step for the weight branches read by the analysis. There **are** archived writers: [add_muon_weights.py](../../../Legacy/OldAnalysis/2025/add_muon_weights.py) adds the 2025 trigger/ID/isolation branches, and [add_pileup_weights.py](../../../Legacy/OldAnalysis/2025-2026/add_pileup_weights.py) adds campaign pileup weights. The latter names 2025 `_v2` branches, while `samples_v15.py` reads `puweight_2025_69p2_v3`. Their hard-coded campaign/payload paths and in-place postprocessing are not a reproducible current pipeline stage. The TODO's statement that no code in the repository writes these branches is therefore too broad, and its linked `Docs/Develop/issues/2025-tuple-weight-branches.md` is absent at this snapshot. Reproducing the actual tuple preparation still needs reconciliation of writer versions and payloads.
- The TES BBB fixture has empty LTF shape content and does not test working-point substitution with the real ID branches. Real-data H4 comparison partly covers that gap; it does not make the fixture cover every later change.

## 9. Recipes, saved runs and file formats

### 9.1 Explicit migration boundaries

| Stored/configured object | Current requirement | Old data behavior | Migration |
|---|---|---|---|
| Framework `run.json` | **Schema 3** | Schemas 1 and 2 are rejected; no converter | Finish with matching old software or start a current run |
| External stage directory manifest | **Manifest format 2** | Other formats rejected | Recreate through a supported current run; do not just change the version number |
| Recipe stages | Every stage needs `stage`, unique `id`, explicit `inputs` | Old implicit input/ID format is invalid | Rewrite the recipe |
| `stage: histograms` | `stage: shapes` | Validation error with replacement guidance | Rename type and update input references where IDs change |
| `stage: plots` | `controlhists` then `controlplots` | Validation error; saved runs using it cannot simply continue | Split the stage and distribute fill/draw options |
| Old TES/ID config paths | `Configs/Fitter/tes_id/...` or bundle copies | Recipe validation error; standalone paths may be missing | Change references/copy the template |
| Sample model | **Schema 2**, explicit positive `lumi` | Header schema 1 is refused | Review/add the era's luminosity and update schema, or copy current template and reapply intentional edits |
| Control-histogram content | `taufw.control_histograms`, **version 2** | Version 1 refused | Refill histograms with the current writer |
| Generic HistFile container | **Format 1** | Other container formats refused | Use the matching writer/reader |
| TES fit-input ROOT files | Existing unversioned TES shape contract | No new generic format/version migration was introduced for the move | Match config, keys, names and actual normalization; no blanket promise for unrelated files |
| Template IDs in old bundle copies | `histogrammer.samples_*`, `histogrammer.setup_*` | `plotter.*` IDs still recognized for warnings through `RENAMED_IDS` | Update header IDs after checking the copied content/schema |

The version numbers refer to different layers. A HistFile container at format 1 may hold control-histogram **content version 2**. A template's **content version** is also different from its **schema**. Updating an ID or content version does not upgrade an incompatible sample schema or histogram file.

Source of truth: [run_record.py](../../../Framework/python/runtime/run_record.py), [manifest.py](../../../Framework/python/runtime/manifest.py), [stage registry](../../../Framework/python/stages/__init__.py), [sample reader](../../../Histogrammer/python/sample/model.py), [control-histogram contract](../contracts/control-histograms.md), [TES contract](../contracts/tes-shapes.md). Older examples/docstrings sometimes still say schema 1/2 or control version 1; current constants and reader checks take precedence.

### 9.2 A current two-stage control-plot recipe fragment

```yaml
stages:
  - stage: controlhists
    id: hists
    inputs: {tuples: {external: /eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP}}
    eras: [2025]
    configs: [Configs/Histogrammer/setups/setup_mutau.yml]
    samples: [Configs/Histogrammer/samples/v15_2025.yml]
    variables: [m_vis, pt_2]
    selections: [baseline]
  - stage: controlplots
    id: plots
    inputs: {hists: hists}
    pdf: true
```

This is a stage fragment, not a complete recipe. In a production pipeline name the production stage ID instead of the external pattern. Since CL §37 no input slot may be null (`tuples: null`, the old `$PICODIR` fallback, and the fit's `shapes: null` are recipe errors); the `controlplots.hists` slot must refer to control-histogram artifacts. The stage ID `plots` is valid: it is the old **type** `stage: plots` that is retired.

For fit shapes, rename the type to `shapes`; a fit can consume `inputs: {shapes: <shape-stage-id>}`. Do not blindly rename arbitrary user IDs if other input references rely on them.

### 9.3 Operational differences of the Framework path

- Results now live under `<run>/stages/<id>/`; command logs under `<run>/logs/<id>/`. Fit output is further separated by era. Old tooling scanning `Fitter/tau_sf` or `<run>/<id>` will not find these results.
- A started run copies bundle files to `<run>/bundle/`. Editing the source analysis directory afterwards does not edit that run. PicoProducer's own sample catalogs are not automatically bundled with it.
- Preflight can refuse nonempty output directories and relative/unresolved tuple patterns on isolated paths. Reusing a standalone directory with old files is not equivalent to starting a fresh stage.
- With explicit sample models and tuple patterns, TES preflight can check missing variation tuples before filling. A missing variation now leaves the stage NEW before any command runs instead of failing hours later. The recorded real example checks 144 mutau variation files and zero mumu files; that count is configuration-specific.
- `taufw.py check` validates recipe/files; it does **not** execute stage environment/tuple preflight. Use `plan` to see those problems. Some stage docstrings still mention `check` for preflight; that is not the implemented CLI distinction.
- `advance` never moves a FAILED stage. Repairing source files and issuing `advance` is not a general stage-rerun facility. Since CL §44, `taufw.py retry <run>` (menu: Continue > Retry) runs a FAILED local stage again after its cause was fixed in the run's `bundle/` copy or environment; the failed attempt moves to `logs/<id>/attempt<N>/` and run.json records the retry and any bundle change. A FAILED production stage is still final: a new run can reuse eligible completed stages through their manifests.
- `controlplots` draws the files of its input, without a separate era/channel filter. Redrawing with an arbitrary new tag and raw external histogram-file recipe inputs are not general supported features today; see [open work](TODO.md).

Old schema-3 runs with retired stage types still fail even though the JSON schema number matches. Conversely, manually changing `schema: 2` to `3` cannot supply the required paths, inputs and provenance. Retain old results; do not try to make them compatible by editing just a number.

## 10. Archived and removed workflows

### 10.1 Archive relocation is a compatibility break

Archives were consolidated under `Legacy/`. Their implementation may be preserved while their original module/command path is gone:

| Historical location / family | Current location / treatment |
|---|---|
| `Fitter/Legacy/` | `Legacy/Fitter/` |
| `Plotter/Legacy/` | `Legacy/Plotter/` |
| `LegacyAnalyses/` | `Legacy/OldAnalysis/`, grouped by year or documented uncertainty |
| PicoProducer `python/legacy/`, retired analysis/correction modules | `Legacy/PicoProducer/python/` or the independent-study archive |
| Retired Fitter model modules such as `TagAndProbeModel` | `Legacy/Fitter/python/...` |
| Jet-to-tau fake-rate suite, `JetToTau_MisID`, `ScaleVariations`, retired macros/corrections | `Legacy/Plotter/python/...` |
| `PicoProducer/scripts/pico2.py` | Archived shell content at `Legacy/PicoProducer/python/scripts/pico2.sh`; it was not a Python API |

Explicit archive imports use `Legacy.<Component>.python.*`, with the checkout root on `PYTHONPATH`. The old `TauFW.*.legacy` namespaces are retired. Maintained TauFW packages still need their normal installation/CMSSW setup.

Archived methods are not automatically discovered by the active Histogrammer `method=` loader. A Python monkey-patch module may need explicit import and dependency repair. Unchanged code can still contain a personal AFS path, a Python 2 dependency or a CWD-relative sibling import. Moving it does not make its workflow runnable in the reference Python 3 environment.

Detailed reasons/replacements are in [Legacy inventory](Legacy.md), [root archive README](../../../Legacy/README.md), [archive bugs](../Bugs.md#legacy) and the component READMEs. The archive is reference material, not a general old-API compatibility layer.

### 10.2 Old standalone paths with no mapped current implementation

The complete source inventory identifies 36 unmapped historical files. Of those, 32 are the following Fitter/PicoProducer Python script paths. Some capabilities have broader alternatives, but **no import/command-compatible replacement at these paths** is supplied.

| Area | Removed old scripts |
|---|---|
| `Fitter/ETauFR/` | `compare.py`, `writedatacard2.py` |
| `Fitter/MuTauFR/` | `compare.py`, `plotpostfit.py`, `writedatacard_2016.py`, `writedatacard_2017.py`, `writedatacard_2018.py`, `writedatacard_UL2016_postVFP.py`, `writedatacard_UL2016_preVFP.py`, `writedatacard_UL2017.py`, `writedatacard_UL2018_withJEC.py` |
| `Fitter/TauES/` | `checkShapes_TES.py`, `createinputsTESPlots.py`, `makeTESfit.py`, `plotParabola_TES.py`, `plotPostFitScan_TES.py` |
| `Fitter/TauID/` | `createinputs.py`, `createinputs_simple.py`, `plotfit.py`, `plotfit_dm.py` |
| `Fitter/paper/` | `plotpostfit.py`, `writecards.py` |
| `Fitter/scripts/` | `histedit.py` |
| `PicoProducer/` | `getTESvariations.py`, `runShapevar.py`, `runTESvar.py`, `sample_monitor.py` |
| `PicoProducer/utils/` | `compareNano.py`, `comparePico.py`, `convertGENSIM_mutau.py`, `pickEvents.py`, `printNanoAOD.py` |

The other four are `common/python/math_helper.py`, `common/test/testLoadingBar.py`, `common/test/testTable.py` and `PicoProducer/nanoV10branch.txt`. Helper replacements are described in §5; these two old common demonstrations were not relocated as command-compatible test files.

This list is broader than the changelog's initial Python 2 deletion step, because the audit spans the entire branch. Deleted source is recoverable from Git history. Existing references such as the TauID README's `plotfit*.py` instructions and TODO mentions of `PicoProducer/utils/compare{Nano,Pico}.py` are stale at the audited commit; do not infer that those commands still exist.

Python 2 migration remains incomplete in retained code too. Examples include ETauFR datacard writing, Zpt configuration/helpers and some PicoProducer utilities. The Tau_Trigger_SF workflow also has unresolved `TauFW.TriggerSF.Common` imports. Their existing problems are not newly repaired by this refactor.

## 11. What will break later at the migration point

No fixed deletion date or release tag is specified by the current TODO. These are **planned**, not changes already made. Track [TODO §8](TODO.md#8-legacy-code-and-architecture) and the [worker compatibility removal condition](../../../PicoProducer/python/processors/README.md#removal).

| Temporary support today | Planned removal / change | Consumers to migrate first |
|---|---|---|
| 13 Plotter alias modules | Delete aliases and their boundary exemptions/tests | Private imports, retained Fitter consumers, `Tests/Plotter`, Legacy scripts |
| Diagnostic `Plotter/plot.py`, `Histogrammer/plot.py` and five old Fitter shape stubs | Delete old files | External wrappers and documentation still using the old paths |
| `samples_v15.py` Python tables | Remove fallback | Supply schema-2 sample model files explicitly |
| Table-derived default luminosity on sample normalization path | One normalization source; unqualified `setera` behavior to become stricter | Users relying on global defaults; keep table/template changes synchronized until then |
| `RENAMED_IDS` for `plotter.samples_*` / `plotter.setup_*` | Delete old ID mapping | Old bundle headers, independently of schema migration |
| `fillhists.py` fills and draws by default | Drawing to leave it; histogram-only behavior becomes default | Users expecting PNG/PDF without a separate draw command |
| `RETIRED` / `MOVED_CONFIGS` migration messages | Delete temporary guidance; possible later stage naming decisions | Old recipes already fail today; messages are not execution compatibility |
| `PLOTTER_ROOT` / `PLOTTER_DATA_DIR` path constants | Remove/review names | External path consumers; `Plotter/data` already does not exist |
| `processors/` worker aliases/forwarders | Delete after old lists finish or are regenerated | Queued tasks, manual task lists, `Bookkeeper` imports and warning-sensitive scripts |

The sample-class shim `storage/Sample.py` also remains a compatibility surface today. Its removal should be announced explicitly if later planned; the current code does not supply a universal deprecation schedule for every shim.

Removing aliases while retaining Legacy callers will break those callers. That may be an accepted archive-policy decision, but it must be explicit. A clean import-boundary report alone is not evidence that external users or archived analyses migrated.

## 12. Validation performed and evidence still needed

### 12.1 Checks executed for this report

Environment: **Windows, Python 3.13.8**. No CMSSW/ROOT/combine production execution was performed. No batch jobs, full test sweep or BBB baseline lock/re-lock was run. Existing baselines and production code were not changed.

| Check | Result | What it establishes |
|---|---|---|
| Inventory generator against the two Git trees | Completed: 405 old Python files, 2,765 definitions, 552 historical source/config/build files | Static coverage and reproducible old/new mapping, not runtime equivalence |
| `python -m unittest discover -s Tests/Histogrammer/compat -q` | 9 tests: **7 passed, 2 skipped** | Alias files/mechanism and five old shape-command stubs; real ROOT module checks skipped |
| `python -m unittest discover -s Tests/PicoProducer/compat -q` | **10 passed** | Worker forwarding with fake workers: arguments, warnings, identity and exit behavior |
| `python -m unittest discover -s Tests/Histogrammer/sample_model -p test_sample_model.py -q` | **8 passed** | Recorder-based table/model calls, lumi consistency, era selection and format errors; not real ROOT normalization |
| `python -m unittest discover -s Tests/Plotter/draw -p test_controlplots.py -q` | **5 passed** | Plot naming/text and control-histogram content validation with test doubles |
| Four selected Framework tests, command below | **4 passed** | Old schemas and retired stages refused; moved config guidance and old template-ID warning mapping |

The Framework selection was run from `Tests/Framework/`:

```bash
python3 -m unittest -q \
  test_framework.RunRecordTests.test_unknown_schema \
  test_framework.RecoveryTests.test_run_with_a_retired_stage_is_refused_with_the_message \
  test_validation.CheckRecipeTests.test_templates_and_moved_configs \
  test_configs.CopyWarningTests.test_copy_with_the_id_from_before_a_rename
```

**Total focused unit results: 34 passed, 2 skipped.** These tests validate migration mechanisms and rejection behavior. In several cases, the expected result is that an old interface is refused, not that the old analysis runs.

### 12.2 How to interpret existing regression evidence

The committed BBB manifest contains **23 cases**, including `pico.*`, old-named `plotter.*`, shape helpers, `histogrammer.tes_inputs`, drawing/common utilities and Framework production. It is not a complete catalog of public APIs or a complete combine fit test.

Several baselines were intentionally replaced during the branch, for corrected defaults/options and later explicit luminosity fields. A current BBB pass means agreement with the **current approved expectation**, not automatic byte equality with the initial pre-refactor checkout. Review the recorded re-lock reasons in [ValidationAndTests.md](ValidationAndTests.md), including P08/P09/P10/P12/P17 and CL §26–§27.

The last recorded lxplus CL §25–§27 result was BBB **23/23**, with the general checks **14/15** because import-boundary debt remains. This report does not rerun or extend that result to untested later environments. The postfit/fit scripts themselves are not a full BBB fit suite. Normal-test success may mean only a successful script exit; the chunking and histogram-correctness cases add independent numerical assertions.

### 12.3 Focused checks before adopting/removing compatibility

These are proposed follow-ups, **not checks claimed as performed here**:

1. In the documented reference `CMSSW_14_1_0_pre4` stack (Python 3.9, ROOT 6.30), rebuild the TauFW Python namespace after the moves and run the real alias imports. Match the stack used by existing BBB locks.
2. Run the relevant current BBB cases with `check`, never re-lock just to hide a migration difference. The full BBB check is appropriate for a release validation, but was not needed to create this documentation artifact.
3. Exercise one small actual `pico.py run` and one dry submission with the analysis's real option conflicts; compare the **resolved worker command**, not just the typed CLI.
4. For an existing production, inspect the persisted options list and regenerate/resubmit old worker task lists before removing `processors/`. Validate the chosen batch adapter on its actual site, especially SGE.
5. For TES/ID acceptance, compare shapes and fit results separately. Fit old/new commands on the **same shape files** to isolate command changes, and compare independent shape fills with the documented numerical tolerance. Use the existing [shape comparison](../../../Tests/tools/compare_shapefiles.py) and [fit comparison](../../../Tests/tools/compare_fitresults.py) tools with analysis-appropriate thresholds.
6. Check private imports, macro paths, bundle headers, file schemas, output-discovery scripts and old queued jobs before deleting aliases. Repository searches cannot see private clones/catalogs.

Current recipe-only checks can be run without starting the analysis:

```bash
python3 taufw.py check Analyses/tes_id_2025
python3 taufw.py plan Analyses/tes_id_2025
```

`plan` needs the appropriate installed environment to give meaningful stage preflight. A successful `check` is not evidence that remote tuples, variation files, correction payloads or combine are available.

## 13. Recommended migration sequence

1. **Record the old result context:** commit, software stack, input tuples/payloads, config copies, resolved worker options and output paths. Preserve existing results and job configs.
2. **Update paths and imports:** use Histogrammer for sample/spec/shapes, Drawing for graphics, `settings/datasets/jobs` for production, and current config/template paths. Rebuild installed CMSSW Python links after moving packages.
3. **Review behavior changes:** especially conflicting `-E` values, resubmit channel edits, positive event limits, forced cleanup and impacts. Do not mix a changed analysis setting into an equivalence comparison accidentally.
4. **Migrate branch-era data/configuration explicitly:** sample schema 2, control content version 2, current recipes/manifest/run formats. Retain old run directories; start a new run where no conversion exists.
5. **Check the analysis at the right level:** command/path checks first, then a small actual worker/histogram run, then physics comparisons needed for that workflow. Treat known legacy failures separately from a new regression.
6. **Remove transition layers only after consumers are accounted for.** Announce the change from fill-and-draw default to two-step plotting separately from the already breaking executable rename.

The highest-priority user communication is a short migration notice containing the executable/config/import tables, the resubmit option example, and the file-format/run-continuation limits. Those are the changes most likely to interrupt a working analysis or silently change how a command is interpreted.

## 14. Evidence index

| Evidence | Purpose |
|---|---|
| [Function inventory](dependencies/compatibility-functions.csv) | Every recovered historical Python function/method definition, old/new signatures/locations and static comparison |
| [Python file inventory](dependencies/compatibility-files.csv) | Every old Python file, parser status and candidate current owners |
| [Source/config/build inventory](dependencies/compatibility-sources.csv) | Every file in the historical source scope, mapped destinations and exact blob comparison |
| [Inventory generator](dependencies/audit_compatibility.py) | Reproduce the three CSVs from Git |
| [Changelog](Refactor-2025.md) / [validation record](ValidationAndTests.md) | Intent, intermediate references, approved output changes and earlier execution evidence |
| [Script options](scripts_arg_changes.md) / [jobs/workers audit](JobsWorkersAudit.md) | Detailed path/default and resubmission consequences |
| [PicoProducer bugs](../Bugs.md#picoproducer), [Histogrammer bugs](../Bugs.md#histogrammer), [Fitter bugs](../Bugs.md#fitter) | Fixed versus retained defects and expected output impact |
| [Tests guide](../../../Tests/README.md) / [test relocation manifest](../../../Tests/migration.json) | Test semantics, runtime requirements and original test locations |
| [Legacy inventory](Legacy.md) / [Legacy bugs](../Bugs.md#legacy) | Retired workflows, dependencies and alternatives |
| [Open work](TODO.md) | Remaining validation and migration-point removals; not evidence that those changes already happened |
