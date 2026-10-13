"""Production jobs: plan, submit and check the batch jobs that turn NanoAOD into pico tuples.

Flow (pico.py submit / resubmit):
  JobRequest -> iter_plans() -> SamplePlan per sample -> submit_plan() -> record_submission()
                  uses: resolve_worker / job_command (worker command lines), sample_layout / assign_chunks
                  (pure planning), chunkify_by_evts (event splitting), check_sample (on resubmission)
Flow (pico.py status / hadd / haddclean / clean), per sample from getcfgsamples():
  check_sample() -> ChunkStatus            status only
  merge_sample() -> MergeResult            check_sample, merge_gate, storage.hadd, cleanup_commands

Public API:
  JobRequest                                 settings of one job operation
  iter_plans, submit_plan, record_submission submission pipeline; SamplePlan is one sample's plan
  Reporter, ConsoleReporter                  silent / terminal reporting
  sample_layout, assign_chunks, cfg_globs    pure planning; SampleLayout is a sample's names and directories
  resolve_worker, job_command, run_command   worker (picojob.py/skimjob.py) of a channel and its command line
  WorkerSpec, WorkerOptions                  records used by the command builders
  check_sample, format_summary, ChunkStatus  status of a sample's job chunks
  merge_sample, merge_target, merge_gate,    merge (hadd) and clean up a sample's job output;
  cleanup_commands, MergeTarget, MergeResult MergeTarget holds its paths, MergeResult the outcome
  evtsplitexp, chunkify_by_evts              event-based chunking of input files
  JOBCFG_KEYS, make_jobcfg, write_jobcfg     job config JSON (key order, writing)
  getcfgsamples                              samples (with job state) from job config JSON files
"""
from TauFW.PicoProducer.jobs.request import JobRequest
from TauFW.PicoProducer.jobs.reporting import Reporter, ConsoleReporter
from TauFW.PicoProducer.jobs.worker_command import resolve_worker, job_command, run_command, WorkerSpec, WorkerOptions
from TauFW.PicoProducer.jobs.chunking import evtsplitexp, chunkify_by_evts
from TauFW.PicoProducer.jobs.jobconfig import JOBCFG_KEYS, make_jobcfg, write_jobcfg, getcfgsamples
from TauFW.PicoProducer.jobs.planner import sample_layout, assign_chunks, cfg_globs, SampleLayout
from TauFW.PicoProducer.jobs.status import check_sample, format_summary, ChunkStatus
from TauFW.PicoProducer.jobs.merge import merge_sample, merge_target, merge_gate, cleanup_commands, MergeTarget, MergeResult
from TauFW.PicoProducer.jobs.pipeline import iter_plans, submit_plan, record_submission, SamplePlan

__all__ = ['JobRequest', 'Reporter', 'ConsoleReporter',
           'resolve_worker', 'job_command', 'run_command', 'WorkerSpec', 'WorkerOptions',
           'evtsplitexp', 'chunkify_by_evts', 'JOBCFG_KEYS', 'make_jobcfg', 'write_jobcfg', 'getcfgsamples',
           'sample_layout', 'assign_chunks', 'cfg_globs', 'SampleLayout', 'check_sample', 'format_summary', 'ChunkStatus',
           'merge_sample', 'merge_target', 'merge_gate', 'cleanup_commands', 'MergeTarget', 'MergeResult',
           'iter_plans', 'submit_plan', 'record_submission', 'SamplePlan']
