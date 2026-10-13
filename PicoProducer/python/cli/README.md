# PicoProducer/python/cli

The command line [`pico.py`](../../scripts/pico.py). The script changes into `PicoProducer/`, loads the
configuration (`common.py`), parses the arguments (`parser.py`) and calls `dispatch` (`__init__.py`).

| Module | Contents |
|---|---|
| [`parser.py`](parser.py) | `build_parser(config)`: all subcommands and options; `parse_args` expands abbreviations (`pico.py sub` = `submit`) |
| [`jobs.py`](jobs.py) | `main_run`, `main_submit`, `main_status`: build a `JobRequest` and call the public API ([`api/`](../api)) with a `ConsoleReporter`; the `--prompt` dialog |
| [`config.py`](config.py) | configuration commands: `list`, `get`, `set`, `rm`, `write`, `channel`, `era` |
| [`install.py`](install.py) | `install` (not implemented) |
| [`common.py`](common.py) | the CLI's configuration `CONFIG` (created or repaired on first use) and logger `LOG` |
