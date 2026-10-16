# Run times (input for a possible C++ migration)

**Status:** measurements only, no decision. Collected during the R3 checks on lxplus (October 2026, CL §17 of
[Refactor-2025.md](Refactor-2025.md), [scripts_arg_changes.md](scripts_arg_changes.md)).

This file records how long the steps of the TauES/ID measurement take, so that a decision to move parts of it to
C++ (or to change them otherwise) starts from numbers rather than impressions. Add new measurements with their
date, machine and conditions; do not overwrite old ones.

## Conditions (2026-10-15/16)

- Machine: `lxplus925`, interactive, inside `tmux`; shared with other users, so the load was not controlled.
- `CMSSW_14_1_0_pre4` (el9_amd64_gcc12), Python 3 from CMSSW, ROOT RDataFrame with 16 threads
  (`SetNumberOfThreads: Setting number of threads from 16 to 16`).
- Tuples: `/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/2025/<channel>` (mutau and mumu, with the
  TES/LTF/JTF variations). Working directories and outputs on AFS.
- One working point pair only: `VSjet VTight`, `VSele Tight`, era 2025.
  The full `run_workflow_zmm.sh` loops over 6 x 2 = 12 pairs.
- Times are wall clock. Shell runs were timed with `date` before and after; Framework runs with the times the
  Framework prints per command (`ok (N s)`, also the last line `# exit code 0 after N s` of every command log).

## Measurements

### Shell scripts

| What | Start - end (CEST) | Duration |
|---|---|---|
| `Fitter/run_inputs.sh` at `f951dc0` (`createinputsTES.py` mutau + mumu, VTight/Tight) | 2026-10-15 13:26:51 - 16:14:45 | **2 h 48 min** |
| `Fitter/run_workflow_zmm.sh` at `f951dc0`, restricted to VTight/Tight (datacards, fit, postfit, plots, corrections, summary) | 2026-10-16 12:10:07 - 12:28:04 | **18 min** |
| The same with the R3 scripts, on the baseline shapes | 2026-10-16 13:57:43 - 14:16:46 | **19 min** |

### Framework run `r3_fit_20261016-142346` (histograms + fit, VTight/Tight)

From the command logs (`# started:` and `# exit code 0 after N s`). The run started at 14:23:46 and ended at
18:16:05: **3 h 52 min** in total.

| Stage | Command | Started (CEST) | Duration | Share of the stage |
|---|---|---|---|---|
| histograms | 1/2 shapes mutau (`createinputsTES.py`) | 14:23:47 | 11576 s = **3 h 13 min** | 92 % |
| histograms | 2/2 shapes mumu (`createinputsTES.py`) | 17:36:42 | 1006 s = **17 min** | 8 % |
| histograms | **stage total** | | 12582 s = **3 h 30 min** | |
| fit | 1/13 datacards mumu | 17:53:32 | 7 s | 1 % |
| fit | 2/13 multidimfit (scan of the 12 regions) | 17:53:39 | 315 s = **5 min 15 s** | 23 % |
| fit | 3/13 postfit fitdiagnostics (incl. impacts) | 17:58:55 | 979 s = **16 min 19 s** | 72 % |
| fit | 4/13 postfit plots | 18:15:14 | 12 s | 1 % |
| fit | 5/13 combined pre/post plots | 18:15:25 | 3 s | |
| fit | 6/13 plots measurements | 18:15:28 | 3 s | |
| fit | 7/13 corrections root | 18:15:30 | 6 s | |
| fit | 8/13 corrections json | 18:15:36 | 6 s | |
| fit | 9/13 summary scan grid | 18:15:42 | 1 s | |
| fit | 10/13 summary measurements grid | 18:15:44 | 3 s | |
| fit | 11/13 summary merge json | 18:15:47 | 4 s | |
| fit | 12/13 summary nll profiles | 18:15:51 | 7 s | |
| fit | 13/13 summary tes and id | 18:15:57 | 8 s | |
| fit | **stage total** | | 1354 s = **22 min 34 s** | |

Commands 5-13 together take 41 s (3 %).

The Plotter checks (`plot.py` with 2-3 variables) took minutes and were not timed.

## What the numbers say

- **Making the shapes dominates.** In the Framework run the histograms stage is 90 % of the time (3 h 30 min of
  3 h 52 min), and the mutau shapes alone are 83 % (3 h 13 min). mumu takes 17 min. Everything after the shapes (datacards, combine fits, impacts, plots, JSON) takes 22-23 minutes.
  For the 12 pairs of the full workflow that is roughly 36-42 hours of shapes against 4-5 hours of fits, if the
  pairs are run one after another as `run_inputs.sh` does.
- Within the fit, `multidimfit` (5 min) and the postfit with impacts (16 min) are 95 % of the stage; they run
  combine and are already C++. The other 11 commands take 60 s together.
- The shapes run is an event loop over the tuples: one mutau sample alone showed 62,871,374 events in the progress
  bar (`TTto2L2Nu`, one systematic variation), and every TES/LTF/JTF variation is filled separately. A C++
  migration therefore only pays off for `createinputsTES.py` (and what it calls in the Plotter); the RDataFrame
  graph itself already runs in C++, so the gain has to come from how the graph is built and how often the tuples
  are read (number of event loops, booked histograms per loop), not from the language of the Python wrapper.
  This is a hypothesis to measure, not a result.
- The Framework histograms stage (3 h 30 min) took longer than `run_inputs.sh` (2 h 48 min) for the same
  commands. Both used the same machine but different days and times; lxplus load and EOS read speed were not
  controlled, so the 40 minutes are not attributed to the Framework. Repeat both under the same conditions before
  drawing a conclusion.

## How to measure next time

- Framework: per command, `grep -H '^# exit code' <run_dir>/logs/*/*.log`; the start time is the `# started:` line.
- Shell: `date` before and after, or `time bash <script>`.
- Record: machine, threads, load (`uptime`), where the tuples and outputs are (EOS/AFS/local disk), working points.
- For the shapes, find out where the time goes (how many event loops run, time per sample and per variation)
  before deciding what to rewrite.
