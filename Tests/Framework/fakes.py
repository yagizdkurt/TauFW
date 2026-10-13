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


# =============================================================================
# ===================== FAKE MODULE APIS OF THE LOCAL STAGES ==================


@dataclass(frozen=True)
class Command:
    label: str
    argv: Tuple[str, ...] = ()
    cwd: str = "/fake"


@dataclass(frozen=True)
class Result(_Record):
    label: str
    returncode: int = 0
    missing: Tuple[str, ...] = ()
    log: str = ""
    seconds: float = 1.0

    @property
    def ok(self):
        return self.returncode == 0 and not self.missing


@dataclass(frozen=True)
class CommandPlan:
    cwd: str
    commands: Tuple[Command, ...]
    artifacts: Tuple[dict, ...] = ()
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RunReport:
    results: Tuple[Result, ...]
    total: int
    artifacts: Tuple[dict, ...] = ()

    @property
    def ok(self):
        return len(self.results) == self.total and all(r.ok for r in self.results)

    @property
    def failed(self):
        return next((r for r in self.results if not r.ok), None)


@dataclass
class _FakeLocalAPI:
    """problems: returned by every preflight; fail: label of the command that fails (exit code 2, log written).
    Every call is recorded in calls; logdirs records where each run wrote its logs."""
    problems: Tuple[str, ...] = ()
    fail: str = None
    calls: list = field(default_factory=list)
    logdirs: list = field(default_factory=list)
    basedir: str = "/repo"  # the module directory that config_file() resolves against

    def _run(self, plan, logdir, progress):
        import os
        self.logdirs.append(logdir)
        os.makedirs(logdir, exist_ok=True)
        results = []
        for index, command in enumerate(plan.commands, 1):
            progress(index, len(plan.commands), command, None)
            log = os.path.join(logdir, "%02d.log" % (index))
            with open(log, "w") as stream:
                stream.write("".join("line %d\n" % (n) for n in range(30)))
            result = Result(command.label, returncode=2 if command.label == self.fail else 0, log=log)
            results.append(result)
            progress(index, len(plan.commands), command, result)
            if not result.ok:
                break
        report = RunReport(tuple(results), len(plan.commands))
        return RunReport(report.results, report.total, plan.artifacts if report.ok else ())

    def names(self):
        return [c[0] for c in self.calls]

    def config_file(self, config):
        import os
        return os.path.join(self.basedir, config)

    def call(self, name):
        """The arguments (after the name) of the last call of `name`."""
        return [c[1:] for c in self.calls if c[0] == name][-1]


class FakePlotter(_FakeLocalAPI):
    @staticmethod
    def request(**fields):
        return dict(fields)

    def plan(self, request):
        self.calls.append(("plan", request))
        commands = tuple(Command("plots %s %s" % (c, e), ("python3", "plot.py", "-y", e, "-c", c))
                         for c in request["configs"] for e in request["eras"])
        artifacts = tuple({"kind": "plots", "era": e, "config": c} for c in request["configs"] for e in request["eras"])
        return CommandPlan("/repo/Plotter", commands, artifacts)

    def preflight(self, request):
        self.calls.append(("preflight", request))
        return self.problems

    def make(self, request, logdir, progress):
        self.calls.append(("make", request))
        return self._run(self.plan(request), logdir, progress)


class FakeFitter(_FakeLocalAPI):
    @staticmethod
    def shapes_request(**fields):
        return dict(fields)

    @staticmethod
    def fit_request(**fields):
        return dict(fields)

    def plan_shapes(self, request):
        self.calls.append(("plan_shapes", request))
        commands, artifacts = [], []
        for era in request["eras"]:
            for jet in request["jet_wps"]:
                for ele in request["ele_wps"]:
                    for config in request["configs"]:
                        commands.append(Command("shapes %s %s %s %s" % (era, jet, ele, config)))
                        artifacts.append({"kind": "shapes", "path": "/fit/%s_%s_%s.root" % (era, jet, ele),
                                          "era": era, "jet_wp": jet, "ele_wp": ele, "config": config})
        return CommandPlan("/repo/Fitter", tuple(commands), tuple(artifacts))

    def preflight_shapes(self, request):
        self.calls.append(("preflight_shapes", request))
        return self.problems

    def make_shapes(self, request, logdir, progress):
        self.calls.append(("make_shapes", request))
        return self._run(self.plan_shapes(request), logdir, progress)

    def plan_fit(self, request):
        self.calls.append(("plan_fit", request))
        commands = tuple(Command("fit %s %s %s" % point) for point in request["points"])
        artifacts = tuple({"kind": "fit", "era": era, "jet_wp": jet, "ele_wp": ele,
                           "values": [{"region": "DM0", "poi": "tes", "value": 0.98, "low": 0.97, "high": 0.99}]}
                          for era, jet, ele in request["points"])
        return CommandPlan("/repo/Fitter", commands, artifacts)

    def preflight_fit(self, request, check_shapes=True):
        self.calls.append(("preflight_fit", request, check_shapes))
        return self.problems

    def fit(self, request, logdir, progress):
        self.calls.append(("fit", request))
        return self._run(self.plan_fit(request), logdir, progress)
