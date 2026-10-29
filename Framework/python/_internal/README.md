# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
# Framework/_internal

The Framework's inside (CL §52). **Analysis code, scripts and the stages do not import anything here**: the
Framework's public API is `from TauFW.Framework import ...` ([Framework/README.md](../../README.md)), and the
libraries for analysis code are in `Utilities/python` ([Utilities](../../../Utilities/README.md)).
`Tests/check_import_boundaries.py` fails if a stage or a Utilities package imports `TauFW.Framework` at all.

| Here | What |
|---|---|
| `runtime/`, `recipes/`, `interfaces/` | the orchestrator, the recipes, the menu adapter: see the package layout in [Framework/README.md](../../README.md#package-layout) |
| `defaults.py`, `user_settings.py`, `version.py` | shared defaults, the user config's Framework settings, release metadata |
| `version.json`, `empty_recipe.yml`, `setup_manifest.json` | data: the release, the recipe of `taufw init`, what FastSetup installed (not tracked) |
| `menu/`, `editor/`, `installer/`, `operations/`, `notifications.py` | TauFW's own tools: the menu (`taufw`), the terminal editor, the installer behind `FastSetup.sh`, the operations that run behind the menu, the terminal bell (sections below) |

```python
from TauFW.Framework._internal.menu import ConsoleUI, MenuNavigation
from TauFW.Framework._internal.editor import edit_file
from TauFW.Framework._internal.installer import COMPONENTS
from TauFW.Framework._internal.operations import EventWriter, EventReader, LogTail, BackgroundProcess, OperationStore
```

The tools import none of the Framework's own modules (`runtime/`, `recipes/`, ...; the Framework passes in what they
need), only each other and the Utilities packages. The menu and the installer also run before `cmsenv`: FastSetup
calls `installer/setup_runner.py` and `installer/setup_tools.py` by their path, and they import each other as
top-level packages from this folder (`menu`, `installer`, `notifications`); `setup_runner.py` and
`setup_tools.py userconfig` add `<checkout>/Utilities/python` too, for UserConfig.

## Operations behind the menu

`operations` exports `EVENTS_ENV`, `EventWriter`, `EventReader`, `LogTail` (commands that run beside a screen, their
events and output followed from files), `BackgroundProcess`, and `Operation`/`OperationStore` with their states
(operations behind the menu: `_supervisor.py` keeps them going when the screen or the menu is left; it runs by its
path, so it stays next to `_operations.py`). Only `BackgroundProcess.start` and `OperationStore.start` launch
processes.

```python
store = OperationStore(".artifacts/menu/operations")
operation = store.start("tests", "Normal tests", [sys.executable, "-B", "Tests/run.py", "normal"], cwd=".",
                        data={"expected": ["plotter.unroll"]})
operation.state()                  # RUNNING, STOPPING, DONE, FAILED, STOPPED or LOST
operation.events.read(), operation.output.read()   # new events / output lines since the last read
operation.cancel()                 # stop it (from any menu, on any machine that sees the directory)
store.latest("tests"), store.running(), store.prune("tests", keep=5)
```

An operation is a command that runs behind the menu and outlives its screen and the menu itself (CL §18).
`OperationStore.start` makes `<root>/<kind>-<time>/`, writes `operation.json` (kind, title, argv, cwd, `data` for
its screen, host, user, start time) and starts `_supervisor.py` by its path, in a session of its own. The
supervisor (standard library only) starts the command in its own process group with its output in `output.log`
and `$TAUFW_EVENTS` naming `events.jsonl`; writes `heartbeat.json` every 5 s; on the file `stop` sends SIGINT, then
SIGTERM after 3 s and SIGKILL after 8 s (`escalate=False`: SIGINT only; the file `kill`: SIGKILL at once); and at
the end writes `exit.json` (exit code, 130 when stopped, 128+N after signal N). JSON files are renamed into place.

`Operation.load(directory)` reads one again; every new object reads `events`/`output` from the top. `state()`:
`exit.json` decides DONE/FAILED/STOPPED; without it RUNNING (STOPPING once `stop` exists), or LOST when no
heartbeat came for 120 s, or at once when the supervisor's process is gone on this machine. Running on after the
login session ends is not a goal: such an operation becomes LOST. `remote` and `host` tell where it runs.
`BackgroundProcess` (`_background.py`) is the simpler form without a supervisor, for a command that lives only as
long as its screen.

## Installer helpers

`installer` owns the Python operations used by `FastSetup.sh`: safe
directory renames, Python implementation/origin checks, native binding checks
and HTT ROOT-file verification. Its public helpers are `rename_directory`,
`verify_modules` and `verify_htt_files`. Imports are silent and do not load ROOT
or analysis packages until verification is requested.

FastSetup calls `installer/setup_tools.py` directly before and after the
checkout moves, so these helpers work before `cmsenv` or `scram b`. Bash retains
the shell environment, Git downloads, installation sequencing and recovery state.
See [FastSetup](../../../Docs/Guide/FastSetup.md) for details.

## Menu presentation

`TauFW.Framework._internal.menu` exports `ConsoleUI` and `MenuNavigation`. Change terminal appearance, screen
wording, option labels, keyboard handling, and menu messages in
`menu/_menu.py`. Edit the ordered help topics and explanations in
`menu/faq.py`. The pre-install FastSetup checklist launches through
`menu/setup_menu.py` and uses `ConsoleUI.setup_checklist()`; installation
sequencing remains in Bash. Space/Enter toggles components and activates Start install.
Shared ASCII branding lives in `menu/banner.py`. The Framework supplies
the actual release label through `ConsoleUI.set_version()` and plain version
status to `main_menu(version=...)`; the menu never reads a manifest or makes
an HTTP request. Standalone installer/preview screens use the `V0.0` fallback.
Entry screens show their welcome messages beneath the
banner; smaller terminals use compact branding so controls remain visible.
The full main-menu banner reveals its decay tracks once over 1.2 seconds on
entry, then stays complete. Returning from another screen replays it; background
refreshes and resizing keep its progress. Input remains available throughout.
The installer and smaller banner layouts are static.
Change screen transitions, back behavior, refresh loops,
and operation recovery in `menu/_navigation.py`. Source section banners
group the related responsibilities. `menu/_preview.py` is the UI preview
(Tests > UI preview, `ConsoleUI.preview()`): every screen with made-up data; add a
`Scenario` there for a new screen. A screen that follows an operation behind the
menu is `menu/_operation_screen.py` (`follow(ui, screen, title, process,
model)`) with a `ScreenModel` subclass for its items and words; the test screen's
model is `TestRun` in `menu/_test_run.py`, the run screen's (an advance; not
wired yet) `RunProgress` in `menu/_run_screen.py`, with `run_summary()` for the
menus' run line, run chooser and run list.

`ConsoleUI.open(parser)` lazily loads curses on an interactive Linux terminal.
It returns a UI, or `None` after explaining the failure and showing CLI help.
The menu shares one `curses.wrapper` session between its screens. A screen opened
on its own uses a wrapper of its own; terminal programs temporarily suspend the session.

Application screens return named actions: `main_menu()` returns `start`,
`continue`, `inspect`, `tests`, `grid_certificate`, `user_config`, `help`, or `exit`; recipe confirmation, status, and run
continuation return their corresponding action or `back`. Recipe/run selectors
return `(action, index)`, with `select` identifying a supplied item and `manual`
or `back` carrying `None`. Path and polling prompts return text or `None` on Esc.
Run selectors accept `(run_id, state, updated)` summaries; `state=None` marks an
unreadable run. Framework retains the records and paths behind those summaries.

Discovery, validation, record access, callback arguments, and command dispatch
stay in `Framework/python/_internal/interfaces/interactive.py`. Menu imports no Framework modules.
Workflow operations continue to use their existing CLI reporting.

Testing screens use `tests_menu()`, `test_family(title)`, and
`test_selection(title, items, review=False)`. Items contain `id`, `description`,
and `dependencies`; selection returns ordered IDs after Run or `None` on Back.
Navigation calls the supplied operations object's `test_catalog()` and
`execute_tests(family, cases)` methods. The Framework adapter owns catalog reads,
checkout paths and test subprocesses; the menu imports no test modules.

`MenuNavigation(ui, operations)` owns the user journey and accepts an operations
object supplied by the caller. The object provides `launch_dir`, `recipes()`
(sorted recipe Paths), `runs()` (sorted `(created, path, summary)` rows),
`resolve_path(value)`, `load_run(path)`, `can_advance(record)`,
`validate_poll(value)` (positive integer or `ValueError`), and
`execute(command, **values)` (CLI return code). Records expose `run_id`,
`run_dir`, and `state`. Navigation handles command errors, interruptions, and
pauses; Framework supplies command defaults and decides whether a run can advance.

`interfaces/interactive.py` `Menu(...)` remains a construction entry point and returns
a `MenuNavigation` wired to Framework operations. Its `start()`, `inspect()`,
`continue_run()`, and `run()` methods now live in `menu/`.

## Terminal editor

`editor` is a self-contained UTF-8 file editor with no Menu, Framework,
UserConfig or other TauFW dependencies. It edits on a caller-owned curses screen,
with F2 to save and Esc to return. It keeps comments, checks a candidate file
through an optional validator, detects external content changes and saves with
a temporary file followed by atomic replacement. Save failures keep the buffer.
See [editor/README.md](editor/README.md) for the API and isolation limits.

The menu loads the editor only for **Modify User Config**. Its Framework adapter
supplies `user_config_path()` (creates a missing config) and
`validate_user_config(draft_path)` (the existing YAML, header and value checks).
Editor handles neither recipe nor production logic. `ConsoleUI.edit_file()`
converts editor failures into action errors so ordinary failures return to the menu.

