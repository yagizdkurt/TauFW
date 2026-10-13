# PicoProducer/python/pico

Command functions for the [`pico.py`](../../scripts/pico.py) script. They turn the command-line arguments into a
`JobRequest` and stream the pipelines of [`jobs/`](../jobs); the job logic itself lives there.
* [`run.py`](run.py): `main_run`, run a channel's worker locally (quick checks and tests)
* [`job.py`](job.py): `main_submit` (submit, resubmit) and `main_status` (status, hadd, haddclean, clean)
* [`config.py`](config.py): configuration commands (list, get, set, rm, write, channel, era)
* [`common.py`](common.py): the global configuration `CONFIG` and logger `LOG` of `pico.py`
