"""Public API of PicoProducer: produce pico tuples from NanoAOD on a batch system.

    from TauFW.PicoProducer.api import PicoProducer, JobRequest
    pico    = PicoProducer.from_config()                 # config/config.json; silent
    request = JobRequest(eras=['2022_postEE'],channels=['mutau'],samples=['DY*'])
    plan    = pico.plan(request)                         # JobPlan: nothing written
    pico.submit(request)                                 # Submission
    status  = pico.status(request)                       # StageStatus; status.complete when all can be merged
    pico.resubmit(request)                               # failed and missing chunks
    report  = pico.merge(request,clean=True)             # MergeReport: report.artifacts (TupleArtifact)

See Docs/Manual/PicoProducer/API.md for the records, side effects and limitations.

Public API:
  PicoProducer                                  the facade (api/producer.py)
  JobRequest                                    what to produce (jobs/request.py)
  JobPlan, PlannedSample, Submission, SubmittedSample, StageStatus, SampleStatus,
  MergeReport, TupleArtifact, LocalResult       results (api/types.py)
  Reporter, ConsoleReporter                     silent / terminal messages (jobs/reporting.py)
"""
from TauFW.PicoProducer.api.types import (JobRequest, JobPlan, PlannedSample, Submission, SubmittedSample,
                                          StageStatus, SampleStatus, MergeReport, TupleArtifact, LocalResult,
                                          request_to_dict, request_from_dict)
from TauFW.PicoProducer.jobs.reporting import Reporter, ConsoleReporter
from TauFW.PicoProducer.api.producer import PicoProducer

__all__ = ['PicoProducer', 'JobRequest', 'JobPlan', 'PlannedSample', 'Submission', 'SubmittedSample',
           'StageStatus', 'SampleStatus', 'MergeReport', 'TupleArtifact', 'LocalResult',
           'request_to_dict', 'request_from_dict', 'Reporter', 'ConsoleReporter']
