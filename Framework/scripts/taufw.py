#! /usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026)
"""taufw.py: run TauFW analysis pipelines from a recipe. A thin client of TauFW.Framework (no logic here).

  taufw.py                                              interactive Linux console menu
  taufw.py plan    RECIPE [--local [-m N]]                show each stage's plan; nothing is written
                                                          (--local: quick local test of the production stage)
  taufw.py start   RECIPE [--run-root DIR] [--wait [--poll S]]   new run: run directory, run.json, first steps
  taufw.py advance RUN_DIR [--wait [--poll S]]            continue a run: check, resubmit, merge, next stages
  taufw.py status  RUN_DIR                                saved and live state of a run (read-only)

Exit code: 1 if the run failed, otherwise 0. See Framework/README.md.
"""
import sys
from argparse import ArgumentParser
try:
    from TauFW.Framework import Framework, load_run, FrameworkReporter, RunState
    from TauFW.Framework.defaults import DEFAULT_RUN_ROOT, DEFAULT_POLL_SECONDS
except ImportError as err:
    print("\033[1m\033[31mImportError for TauFW.Framework: please check if you compiled with `scram b`.\033[0m")
    raise err


# =============================================================================
# ================================= COMMANDS ==================================


def cmd_plan(args):
    """Show each stage's plan, or run a quick local test of the production stage."""
    reporter = FrameworkReporter(verbosity=args.verbose)
    framework = Framework.from_recipe(args.recipe, reporter=reporter)
    if args.local:
        stage_spec = framework.recipe.stage('production')
        if stage_spec is None:
            reporter.warning("The recipe has no production stage to test locally.")
            return 1
        results = framework.stages['production'].run_local(stage_spec.spec, maxevts=args.maxevts)
        return 1 if any(r.exitcode for r in results) else 0
    plan = framework.plan()
    for stage_plan in plan.stages:
        reporter.header("Stage %s" % (stage_plan.stage))
        if stage_plan.plan is None:  # placeholder stage
            reporter.message(stage_plan.note)
        elif hasattr(stage_plan.plan, 'samples'):  # production: a PicoProducer JobPlan
            reporter.table(["era", "channel", "sample", "files", "chunks", "try", "conflict"],
                           [(s.era, s.channel, s.name, s.nfiles, s.nchunks, s.subtry, "yes" if s.conflict else "")
                            for s in stage_plan.plan.samples])
            reporter.message("%d sample(s), %d job(s)" % (len(stage_plan.plan.samples), stage_plan.plan.nchunks))
        else:
            reporter.message(repr(stage_plan.plan))
    return 0


def cmd_start(args):
    """Start a new run."""
    reporter = FrameworkReporter(verbosity=args.verbose)
    framework = Framework.from_recipe(args.recipe, reporter=reporter)
    record = framework.run(run_root=args.run_root, wait=args.wait, poll=args.poll)
    return _finish(reporter, record)


def cmd_advance(args):
    """Continue a run."""
    reporter = FrameworkReporter(verbosity=args.verbose)
    record = load_run(args.run_dir)
    framework = Framework.from_record(record, reporter=reporter)
    record = framework.advance(record, wait=args.wait, poll=args.poll)
    return _finish(reporter, record)


def cmd_status(args):
    """Show the state of a run (nothing is saved or submitted)."""
    reporter = FrameworkReporter(verbosity=args.verbose)
    record = load_run(args.run_dir)
    summary = Framework.from_record(record, reporter=reporter).status(record)
    reporter.header("Run %s: %s" % (summary.run_id, summary.state))
    reporter.table(["stage", "state", "attempt", "message"],
                   [(s.stage, s.state, s.attempt, s.message) for s in summary.stages])
    for stage in summary.stages:
        if stage.live is not None and hasattr(stage.live, 'samples'):  # production: a PicoProducer StageStatus
            reporter.header("Stage %s: jobs" % (stage.stage))
            reporter.table(["sample", "chunks", "good", "pending", "failed", "missing", "complete"],
                           [(s.name, s.nchunks, len(s.good), len(s.pending), len(s.failed), len(s.missing),
                             "yes" if s.complete else "") for s in stage.live.samples])
    return 1 if summary.state == RunState.FAILED else 0


def _finish(reporter, record):
    """Tell the user where the run is and how to continue it; return the exit code."""
    reporter.message("Run directory: %s" % (record.run_dir))
    if record.state == RunState.WAITING:
        reporter.message("Continue with: taufw.py advance %s" % (record.run_dir))
    return 1 if record.state == RunState.FAILED else 0


COMMANDS = {'plan': cmd_plan, 'start': cmd_start, 'advance': cmd_advance, 'status': cmd_status}


# =============================================================================
# ================================== PARSER ===================================


def build_parser():
    parser = ArgumentParser(prog='taufw.py', description="Run TauFW analysis pipelines from a recipe.")
    common = ArgumentParser(add_help=False)  # options of every command
    common.add_argument('-v', '--verbose', dest='verbose', type=int, nargs='?', const=1, default=0,
                        help="set verbosity")
    waiter = ArgumentParser(add_help=False)  # options of the commands that can wait for jobs
    waiter.add_argument('--wait', action='store_true', help="keep advancing while the run waits for jobs")
    waiter.add_argument('--poll', type=int, default=DEFAULT_POLL_SECONDS, metavar='S',
                        help="seconds between checks with --wait, default=%(default)d")
    subparsers = parser.add_subparsers(dest='command', metavar='COMMAND')
    subparsers.required = True
    plan = subparsers.add_parser('plan', parents=[common], help="show each stage's plan (nothing is written)")
    plan.add_argument('recipe', help="recipe file (.yml or .json)")
    plan.add_argument('--local', action='store_true', help="run the production stage locally on one file per sample")
    plan.add_argument('-m', '--maxevts', type=int, default=100, metavar='N',
                      help="events per local run, default=%(default)d")
    start = subparsers.add_parser('start', parents=[common, waiter], help="start a new run")
    start.add_argument('recipe', help="recipe file (.yml or .json)")
    start.add_argument('--run-root', dest='run_root', default=None, metavar='DIR',
                       help="parent of the run directory, default=%s" % (DEFAULT_RUN_ROOT))
    advance = subparsers.add_parser('advance', parents=[common, waiter], help="continue a run")
    advance.add_argument('run_dir', help="run directory (with run.json)")
    status = subparsers.add_parser('status', parents=[common], help="state of a run (read-only)")
    status.add_argument('run_dir', help="run directory (with run.json)")
    return parser


# =============================================================================
# =================================== MAIN ====================================


def main(argv=None):
    """Without arguments, open the interactive menu; otherwise run one command."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from TauFW.Framework.interactive import run_menu
        return run_menu(COMMANDS, build_parser())
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
