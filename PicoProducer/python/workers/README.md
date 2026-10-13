# PicoProducer/python/workers

The workers: scripts that run post-processing modules on nanoAOD, like those in [`analysis/`](../analysis).
Local runs (`pico.py run`) and batch jobs (`pico.py submit`) start them; the command line is built by
[`jobs/worker_command.py`](../jobs/worker_command.py). This directory was called `processors/` before Part 5 of the
cleanup; [`processors/`](../processors) now only forwards the old imports and scripts here (deprecated).
* [`skimjob.py`](skimjob.py): Skim nanoAOD file (input: nanoAOD, output: nanoAOD).
* [`picojob.py`](picojob.py): Analyze nanoAOD events (input: nanoAOD, output: custom "pico" format, e.g. a flat tree).
* [`Bookkeeper.py`](Bookkeeper.py): NanoAODTools module that keeps the total cutflow and weights of skims.
* `keep_and_drop_*.txt`: branch selections of the skim, gen and sum-of-weights jobs.
* The former `dumpGen.py` gen-level dumper now lives in [`LegacyAnalyses/2018/dumpGen.py`](../../../LegacyAnalyses/2018/dumpGen.py); use the `gen` channel ([`GenDumper`](../analysis/GenDumper.py)) instead.

For instructions, please see [the PicoProducer README](../..#skimming).
