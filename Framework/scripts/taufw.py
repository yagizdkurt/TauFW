#! /usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""taufw.py: run TauFW analysis pipelines from a recipe. A thin client of TauFW.Framework (no logic here).

  taufw.py                                              interactive Linux console menu
  taufw.py check   RECIPE                                every problem of a recipe (structure, ids, inputs,
                                                          the files it names) and its warnings; nothing is written
  taufw.py plan    RECIPE [--local [-m N]]                show each stage's plan and the files it reads;
                                                          nothing is written
                                                          (--local: quick local test of the production stage)
  taufw.py start   RECIPE [--run-root DIR] [--wait [--poll S]]   new run: run directory, run.json, first steps
  taufw.py advance RUN_DIR [--wait [--poll S]] [--take-lock]
                                                          continue a run: check, resubmit, merge, next stages
                                                          (controlhists, controlplots, shapes, fit, python: run locally);
                                                          refused while another advance of the run is working
                                                          (--take-lock: take over a lost one of another machine)
  taufw.py status  RUN_DIR                                saved and live state of a run (read-only)
  taufw.py init    NAME [--from RECIPE] [--root DIR]      new analysis bundle Analyses/NAME/ (with copies of the
                                                          files of RECIPE's bundle and of the module configs it
                                                          uses, next to its recipe.yml)
  taufw.py configs [update]                               the config templates of Configs/ to copy into a bundle;
                                                          update (maintainers): raise the versions of changed
                                                          templates and rewrite Configs/configs.lock
  taufw.py userconfig                                     your user config (Analyses/UserConfig.yaml, or
                                                          $TAUFW_USER_CONFIG): made if there is none, its state
  taufw.py version [--check]                              installed version; optionally check the remote manifest

RECIPE is an analysis bundle directory (Analyses/<name>, with recipe.yml) or a recipe file.

With $TAUFW_EVENTS set (the menu does that for a command it runs beside its screen), every command also writes its
messages and the Framework's events (TauFW.Framework.reporting) to that file; the output does not change. The
variable is removed from the environment first, so the commands the stages run never see it.

The runs go to start --run-root DIR, else the recipe's run_root, else runs.run_root of your user config, else
taufw_runs/ here. A production stage also takes your user config's production settings (Framework/python/
user_settings.py); `plan` names them.

check, plan and start warn in one line while there is no user config or it is not reviewed
(TauFW.Utilities.UserConfig.manage); the recipe still runs.

Exit code: 1 if the run failed or the recipe is invalid (warnings do not count), otherwise 0. See
Framework/README.md.
"""
import os
import shlex
import sys
from argparse import ArgumentParser
try:
    from TauFW.Framework import (Framework, Recipe, RecipeError, load_run, FrameworkReporter, EventReporter,
                                 RunState, check_recipe, RunDirectoryError, RunLockError)
    from TauFW.Framework.bundle import BundleError, make_bundle
    from TauFW.Framework.configs import LOCK_NAME, lock_changes, update
    from TauFW.Framework.defaults import (DEFAULT_RUN_ROOT, DEFAULT_POLL_SECONDS, ANALYSES_DIR, CONFIGS_DIR,
                                          default_file_io)
    from TauFW.Utilities.Process import EVENTS_ENV, EventWriter
    from TauFW.Utilities import UserConfig
    from TauFW.Utilities.UserConfig import manage as user_config
    from TauFW.Framework import user_settings
except ImportError as err:
    print("\033[1m\033[31mImportError for TauFW.Framework: please check if you compiled with `scram b`.\033[0m")
    raise err


# =============================================================================
# ================================= COMMANDS ==================================


def cmd_version(args):
    """Local metadata by default; explicit --check refreshes without downloading any code."""
    from TauFW.Framework.version import current_version, VersionChecker
    reporter = _reporter(args)
    if not args.check:
        try:
            reporter.message('TauFW %s' % current_version())
            return 0
        except (OSError, ValueError) as error:
            reporter.warning('Cannot read TauFW version: %s' % error)
            return 1
    result = VersionChecker().check()
    reporter.message('TauFW %s' % result['installed'])
    if result['status'] == 'disabled':
        reporter.message('Version checks disabled by TAUFW_NO_VERSION_CHECK.')
        return 0
    if result['error']:
        reporter.warning('Version check unavailable: %s' % result['error'])
        if result['available']:
            reporter.message('Last known newer version: %s' % result['latest'])
        return 1
    if result['available']:
        reporter.message('New version available: %s' % result['latest'])
    else:
        reporter.message('No newer major/minor version published (remote: %s).' % result['latest'])
    return 0


def cmd_check(args):
    """List every problem and warning of a recipe."""
    reporter = _reporter(args)
    check = check_recipe(args.recipe)
    _show_user_config(reporter)
    _show_warnings(reporter, check.warnings)
    if check.ok:
        reporter.message("Recipe %s: no problems (%d stage(s): %s)"
                         % (check.name, len(check.stages), ', '.join(stage_id for stage_id, _, _ in check.stages)))
        return 0
    reporter.warning("Recipe %s: %d problem(s)" % (check.name, len(check.issues)))
    for issue in check.issues:
        reporter.warning("  %s" % (issue))
    return 1


def cmd_plan(args):
    """Show each stage's plan, or run a quick local test of the production stage."""
    reporter = _reporter(args)
    framework = Framework.from_recipe(args.recipe, reporter=reporter)
    if args.local:
        stage_spec = framework.recipe.first('production')
        if stage_spec is None:
            reporter.warning("The recipe has no production stage to test locally.")
            return 1
        results = framework.stages[stage_spec.id].run_local(stage_spec.spec, maxevts=args.maxevts)
        return 1 if any(r.exitcode for r in results) else 0
    plan = framework.plan()
    _show_user_config(reporter)
    _show_warnings(reporter, framework.recipe.warnings)
    if plan.bundle_dir:
        reporter.message("Bundle: %s" % (plan.bundle_dir))
    reporter.message("Run root: %s" % (_run_root_line(framework.recipe)))
    production = framework.recipe.first('production')
    if production:  # only production reads it (CL §37)
        settings = getattr(framework.stages[production.id], 'settings', None)
        used = "; from your user config: %s" % (", ".join(settings.used)) if settings and settings.used else ""
        reporter.message("PicoProducer config: %s%s"
                         % (plan.pico_config or "PicoProducer/config/config.json (default)", used))
    for stage_plan in plan.stages:
        stage_spec = framework.recipe.stage(stage_plan.stage)
        reporter.header("Stage %s (%s)" % (stage_spec.id, stage_spec.stage))
        if stage_spec.description:
            reporter.message(stage_spec.description)
        reporter.message("Inputs: %s" % (_inputs_line(stage_spec, framework.stages[stage_spec.id],
                                                     stage_plan.sources)))
        if stage_plan.paths:  # the files the stage reads: bundle, template, channel name or absolute (bundle.py)
            reporter.table(["option", "file", "from"],
                           [(option, resolved, where) for option, _, resolved, where in stage_plan.paths])
        if stage_plan.plan is None:  # placeholder stage
            reporter.message(stage_plan.note)
        elif hasattr(stage_plan.plan, 'samples'):  # production: a PicoProducer JobPlan
            reporter.table(["era", "channel", "sample", "files", "chunks", "try", "conflict"],
                           [(s.era, s.channel, s.name, s.nfiles, s.nchunks, s.subtry, "yes" if s.conflict else "")
                            for s in stage_plan.plan.samples])
            reporter.message("%d sample(s), %d job(s)" % (len(stage_plan.plan.samples), stage_plan.plan.nchunks))
        elif hasattr(stage_plan.plan, 'commands'):  # controlhists, controlplots, shapes, fit, python: local
            _show_commands(reporter, stage_plan.plan)
        else:
            reporter.message(repr(stage_plan.plan))
    _show_warnings(reporter, plan.sample_warnings)
    if plan.sample_problems:  # start refuses these
        reporter.warning("Samples: %d problem(s); `taufw.py start` refuses the recipe until they are fixed"
                         % (len(plan.sample_problems)))
        for problem in plan.sample_problems:
            reporter.warning("  %s" % (problem))
        return 1
    return 0


def cmd_start(args):
    """Start a new run."""
    reporter = _reporter(args)
    framework = Framework.from_recipe(args.recipe, reporter=reporter)
    _show_user_config(reporter)
    if not args.run_root:  # --run-root chooses the place, so the recipe's run_root warnings do not apply
        _show_warnings(reporter, framework.recipe.warnings)
    reporter.message("Run root: %s" % (_run_root_line(framework.recipe, args.run_root)))
    record = framework.run(run_root=args.run_root, wait=args.wait, poll=args.poll)
    return _finish(reporter, record)


def cmd_advance(args):
    """Continue a run."""
    reporter = _reporter(args)
    record = load_run(args.run_dir)
    framework = Framework.from_record(record, reporter=reporter)
    try:
        record = framework.advance(record, wait=args.wait, poll=args.poll, take_lock=args.take_lock)
    except RunLockError as error:
        reporter.warning("Cannot advance run %s: %s" % (record.run_id, error))
        reporter.event('error', message=str(error))
        if error.lost:
            reporter.message("Take it over with: taufw.py advance %s --take-lock" % (args.run_dir))
        return 1
    return _finish(reporter, record)


def cmd_status(args):
    """Show the state of a run (nothing is saved or submitted)."""
    reporter = _reporter(args)
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
        elif isinstance(stage.live, list):  # fit: the fitted values
            reporter.header("Stage %s: fitted values" % (stage.stage))
            reporter.table(["era", "jet WP", "ele WP", "region", "poi", "value", "1 sigma"],
                           [(v['era'], v['jet_wp'], v['ele_wp'], v['region'], v['poi'], "%.4f" % (v['value']),
                             _interval(v)) for v in stage.live])
    return 1 if summary.state == RunState.FAILED else 0


def cmd_init(args):
    """Make a new analysis bundle: from a recipe (with copies of the module configs it uses), or a minimal one
    with an example Python step."""
    reporter = _reporter(args)
    target = os.path.join(args.root or ANALYSES_DIR, args.name)
    try:
        minimal = Recipe.from_dict({'name': args.name, 'pico': {'config': None},  # also checks the name
                                    'stages': [{'stage': 'python', 'id': 'example', 'inputs': None,
                                                'file': 'steps/example.py'}]})
        if args.source:
            copied = Framework.from_recipe(args.source, reporter=reporter).make_bundle(target, name=args.name)
        else:
            copied = make_bundle(minimal.to_dict(), {}, target, default_file_io())
    except (BundleError, RecipeError) as error:
        reporter.warning(str(error))
        return 1
    reporter.message("New analysis bundle: %s" % (target))
    for path in copied:
        reporter.message("  %s" % (path))
    reporter.message("Edit %s, then: taufw.py plan %s" % (os.path.join(target, 'recipe.yml'), target))
    return 0


def cmd_configs(args):
    """List the config templates of Configs/; with `update`, raise the versions of the changed templates and
    rewrite the lock (Framework/python/configs.py)."""
    reporter = _reporter(args)
    configs, changes = (update if args.action == 'update' else lock_changes)(CONFIGS_DIR)
    for problem in configs.problems:
        reporter.warning(problem)
    lowered = [change for change in changes if change.kind == 'lowered']
    if args.action == 'update':
        for change in changes:
            reporter.message(str(change))
        if configs.problems or lowered:
            reporter.warning("Nothing was written: fix the problems above first.")
            return 1
        reporter.message("Configs/%s is up to date%s." % (LOCK_NAME, "" if changes else " (nothing changed)"))
        return 0
    pending = {change.config_id: change.kind for change in changes}
    if configs.templates:
        reporter.table(["id", "version", "file", "lock", "description"],
                       [(t.header.id, t.header.version, "Configs/" + t.path.replace(os.sep, '/'),
                         pending.get(t.header.id, "ok"), t.header.description)
                        for t in sorted(configs.templates, key=lambda template: template.header.id)])
    else:
        reporter.message("No templates in %s yet." % (CONFIGS_DIR))
    if changes:
        reporter.warning("%d template(s) changed since the lock: maintainers run `taufw.py configs update`"
                         % (len(changes)))
    reporter.message("Copy a template into your analysis bundle and edit its values (never its taufw_config "
                     "header); see Configs/README.md.")
    return 1 if configs.problems or lowered else 0


def cmd_userconfig(args):
    """Make the user config if there is none (never over an existing one), and show where it is and its state."""
    reporter = _reporter(args)
    path = UserConfig.location()
    try:
        created = user_config.create(path)
    except OSError as error:  # e.g. the directory of $TAUFW_USER_CONFIG does not exist
        reporter.warning("Cannot create the user config %s: %s" % (path, error))
        return 1
    reporter.message(("New user config: %s" if created else "User config: %s") % (path))
    warnings = user_config.check()
    for warning in warnings:
        reporter.warning(warning)
    if not warnings:
        reporter.message("Reviewed: yes")
    return 0


def _reporter(args):
    """The terminal reporter; with an events file (args.events, see main), it also writes events."""
    reporter = FrameworkReporter(verbosity=args.verbose)
    return EventReporter(reporter, args.events) if args.events.path else reporter


def _show_user_config(reporter):
    """The warnings of the user config, one line each (no file, not reviewed): the recipe still runs."""
    for warning in user_config.check():
        reporter.warning(warning)


def _show_warnings(reporter, warnings):
    """A recipe's warnings (Issue): the recipe can run, but should change."""
    for warning in warnings:
        reporter.warning(str(warning))  # the reporter marks it as a warning


def _run_root_line(recipe, given=None):
    """Where the runs go, and why: --run-root, the recipe's run_root (absolute, nothing expanded), the user
    config's runs.run_root, or the default."""
    if given:
        return "%s (--run-root)" % (os.path.abspath(given))
    if recipe.run_root:
        return "%s (recipe)" % (recipe.run_root)
    from_user = user_settings.run_root_or_none()
    if from_user:
        return "%s (user config)" % (from_user)
    return "%s (default: no run_root in the recipe)" % (os.path.abspath(DEFAULT_RUN_ROOT))


def _inputs_line(stage_spec, stage, sources=None):
    """The stage's inputs as written: 'none', or 'slot <- stage id', 'slot <- <directory> (run, stage, finished)'
    (another run's stage directory; sources: what its manifest says, see StagePlan.sources), 'slot <- external
    <pattern>' (data made outside TauFW), or for null 'slot <- outside this run (what null means for the slot,
    Stage.null_inputs)'."""
    if stage_spec.inputs is None:
        return "none"
    return ", ".join("%s <- %s" % (slot, _input_text(slot, value, stage, sources or {}))
                     for slot, value in stage_spec.inputs.items())


def _input_text(slot, value, stage, sources):
    if isinstance(value, dict) and 'path' in value:
        source = sources.get(slot)
        if source is None:  # cannot be read: the stage's note says why
            return value['path']
        return "%s (run %s, stage %s (%s), finished %s)" % (value['path'], source['run_id'], source['stage_id'],
                                                            source['stage'], source['finished'])
    if isinstance(value, dict):
        return "external %s" % (value['external'])
    return value or "outside this run (%s)" % (stage.null_inputs.get(slot, '?'))


def _show_commands(reporter, plan):
    """The commands of a local stage, as they would be typed in its working directory."""
    reporter.message("Working directory: %s" % (plan.cwd))
    subdirs = [os.path.relpath(command.cwd, plan.cwd) for command in plan.commands
               if getattr(command, 'cwd', plan.cwd) != plan.cwd]
    if subdirs:  # e.g. the fit: the scripts of each era run in <stage dir>/<era>/
        reporter.message("Commands run in: %s (relative to the working directory)"
                         % (', '.join(dict.fromkeys(subdirs))))
    reporter.table(["#", "step", "command"],
                   [(index, command.label, _command_line(command))
                    for index, command in enumerate(plan.commands, 1)])
    reporter.message("%d command(s)" % (len(plan.commands)))
    for note in plan.notes:
        reporter.warning(note)


def _command_line(command):
    """A command line with its extra environment variables, with this Python shown as python3."""
    env = ["%s=%s" % (key, shlex.quote(value)) for key, value in getattr(command, 'env', ())]
    argv = [shlex.quote("python3" if i == 0 and a == sys.executable else a) for i, a in enumerate(command.argv)]
    return " ".join(env + argv)


def _interval(value):
    if value.get('low') is None or value.get('high') is None:
        return "-"
    return "[%.4f, %.4f]" % (value['low'], value['high'])


def _finish(reporter, record):
    """Tell the user where the run is and how to continue it; return the exit code."""
    reporter.message("Run directory: %s" % (record.run_dir))
    if not RunState(record.state).finished:
        reporter.message("Continue with: taufw.py advance %s" % (record.run_dir))
    return 1 if record.state == RunState.FAILED else 0


COMMANDS = {'check': cmd_check, 'plan': cmd_plan, 'start': cmd_start, 'advance': cmd_advance, 'status': cmd_status, 'init': cmd_init,
            'configs': cmd_configs, 'userconfig': cmd_userconfig, 'version': cmd_version}


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
    check = subparsers.add_parser('check', parents=[common], help="list every problem of a recipe")
    check.add_argument('recipe', help="analysis bundle directory, or recipe file (.yml or .json)")
    plan = subparsers.add_parser('plan', parents=[common], help="show each stage's plan (nothing is written)")
    plan.add_argument('recipe', help="analysis bundle directory, or recipe file (.yml or .json)")
    plan.add_argument('--local', action='store_true', help="run the production stage locally on one file per sample")
    plan.add_argument('-m', '--maxevts', type=int, default=100, metavar='N',
                      help="events per local run, default=%(default)d")
    start = subparsers.add_parser('start', parents=[common, waiter], help="start a new run")
    start.add_argument('recipe', help="analysis bundle directory, or recipe file (.yml or .json)")
    start.add_argument('--run-root', dest='run_root', default=None, metavar='DIR',
                       help="parent of the run directory, instead of the recipe's run_root "
                            "(default: run_root, else %s)" % (DEFAULT_RUN_ROOT))
    advance = subparsers.add_parser('advance', parents=[common, waiter], help="continue a run")
    advance.add_argument('run_dir', help="run directory (with run.json)")
    advance.add_argument('--take-lock', dest='take_lock', action='store_true',
                         help="take over the lock of a lost advance of this run on another machine")
    status = subparsers.add_parser('status', parents=[common], help="state of a run (read-only)")
    status.add_argument('run_dir', help="run directory (with run.json)")
    init = subparsers.add_parser('init', parents=[common], help="new analysis bundle")
    init.add_argument('name', help="name of the bundle directory and of its recipe")
    init.add_argument('--from', dest='source', default=None, metavar='RECIPE',
                      help="start from this bundle or recipe file, with copies of its bundle's files and of the "
                           "module configs it uses next to the new recipe.yml")
    init.add_argument('--root', default=None, metavar='DIR', help="parent directory, default=%s" % (ANALYSES_DIR))
    configs = subparsers.add_parser('configs', parents=[common], help="the config templates of Configs/")
    configs.add_argument('action', nargs='?', choices=('list', 'update'), default='list',
                         help="list (default): the templates; update (maintainers): raise the versions of changed "
                              "templates and rewrite Configs/configs.lock")
    subparsers.add_parser('userconfig', parents=[common],
                          help="your user config: made if there is none, its path and state")
    version = subparsers.add_parser('version', parents=[common], help="installed version; optionally check for updates")
    version.add_argument('--check', action='store_true', help="refresh the remote version manifest (no code download)")
    return parser


# =============================================================================
# =================================== MAIN ====================================


def main(argv=None):
    """Without arguments, open the interactive menu; otherwise run one command."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from TauFW.Framework.interactive import run_menu
        return run_menu(build_parser())
    args = build_parser().parse_args(argv)
    args.events = EventWriter(os.environ.pop(EVENTS_ENV, None))  # read once; the stages' commands never see it
    try:
        return COMMANDS[args.command](args)
    except (RecipeError, RunDirectoryError, RunLockError, UserConfig.UserConfigError) as error:  # without a traceback
        reporter = _reporter(args)
        reporter.warning(str(error))
        reporter.event('error', message=str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
