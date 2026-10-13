"""A fake PicoProducer with canned results, shaped like TauFW.PicoProducer.api records."""
from dataclasses import dataclass, asdict, field
from typing import Tuple


class _Record:
    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Sample(_Record):
    name: str
    era: str = "2018"
    channel: str = "mutau"
    nfiles: int = 2
    nchunks: int = 2
    subtry: int = 1
    conflict: bool = False


@dataclass(frozen=True)
class Plan(_Record):
    samples: Tuple[Sample, ...] = ()

    @property
    def nchunks(self):
        return sum(s.nchunks for s in self.samples)


@dataclass(frozen=True)
class Submission(_Record):
    jobids: Tuple[int, ...] = ()

    @property
    def nsubmitted(self):
        return len(self.jobids)


@dataclass(frozen=True)
class SampleStatus(_Record):
    name: str
    nchunks: int = 2
    good: Tuple[int, ...] = ()
    pending: Tuple[int, ...] = ()
    failed: Tuple[int, ...] = ()
    missing: Tuple[int, ...] = ()

    @property
    def complete(self):
        return not (self.pending or self.failed or self.missing)


@dataclass(frozen=True)
class Status(_Record):
    samples: Tuple[SampleStatus, ...] = ()

    @property
    def complete(self):
        return bool(self.samples) and all(s.complete for s in self.samples)

    @property
    def npending(self):
        return sum(len(s.pending) for s in self.samples)

    @property
    def nfailed(self):
        return sum(len(s.failed) + len(s.missing) for s in self.samples)


@dataclass(frozen=True)
class Artifact(_Record):
    path: str
    sample: str


@dataclass(frozen=True)
class MergeReport(_Record):
    artifacts: Tuple[Artifact, ...] = ()
    refused: Tuple[str, ...] = ()
    invalid: Tuple[Tuple[str, str], ...] = ()


def pending(*names):
    return Status(tuple(SampleStatus(n, good=(0,), pending=(1,)) for n in names))


def failed(*names):
    return Status(tuple(SampleStatus(n, good=(0,), failed=(1,)) for n in names))


def complete(*names):
    return Status(tuple(SampleStatus(n, good=(0, 1)) for n in names))


@dataclass
class FakePicoProducer:
    """statuses: returned by status() in turn (the last one repeats). Every call is recorded in calls."""
    samples: Tuple[str, ...] = ("DY", "TT")
    statuses: list = field(default_factory=list)
    merge_report: MergeReport = None
    calls: list = field(default_factory=list)
    jobid: int = 1000

    @staticmethod
    def request(**fields):
        return dict(fields)

    def plan(self, request):
        self.calls.append(("plan", request))
        return Plan(tuple(Sample(n) for n in self.samples))

    def submit(self, request):
        self.calls.append(("submit", request))
        return Submission(self._jobids())

    def resubmit(self, request):
        self.calls.append(("resubmit", request))
        return Submission(self._jobids())

    def status(self, request):
        self.calls.append(("status", request))
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def merge(self, request, clean=False, force=False):
        self.calls.append(("merge", request, clean, force))
        if self.merge_report is not None:
            return self.merge_report
        return MergeReport(tuple(Artifact("/pico/%s_mutau.root" % n, n) for n in self.samples))

    def run_local(self, request):
        self.calls.append(("run_local", request))
        return ()

    def _jobids(self):
        ids = []
        for _ in self.samples:
            self.jobid += 1
            ids.append(self.jobid)
        return tuple(ids)

    def names(self):
        return [c[0] for c in self.calls]
