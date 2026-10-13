"""Persistent FastSetup UI and Bash supervisor; usable before CMSSW activation.

The worker owns installation decisions. This module imports the complete UI
before launching it, since the worker may relocate the checkout underneath us.
"""
from argparse import ArgumentParser, REMAINDER
import codecs
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

if __package__:
    from ..Menu import ConsoleUI
    from ..Menu.setup_menu import COMPONENTS
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from Menu import ConsoleUI
    from Menu.setup_menu import COMPONENTS


STAGES = ("Preflight", "CMSSW environment", "Dependencies", "Build", "Verification")
ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")
DIAGNOSTIC = re.compile(r"\b(?:warning|error|fatal)\b|Traceback \(most recent call last\)", re.I)


def clean(value):
    """Keep terminal control sequences out of curses and restored-terminal output."""
    return "".join(char for char in ANSI.sub("", value) if char.isprintable() or char == "\t")


def worker_arguments(arguments, selected):
    """Menu choices replace component flags; other arguments pass through verbatim."""
    flags = {"--run2-jme", "--skip-tauidsfs", "--skip-htt", "--skip-combine", "--non-interactive"}
    result = [arg for arg in arguments if arg not in flags] + ["--non-interactive"]
    for name in ("tauidsfs", "htt", "combine"):
        if name not in selected:
            result.append("--skip-" + name)
    if "run2-jme" in selected:
        result.append("--run2-jme")
    return result


class Worker:
    """Nonblocking output/event capture with a retained raw transcript."""

    def __init__(self, script, arguments):
        self.started = time.monotonic()
        self.finished = None
        self.stage = None
        self.completed = set()
        self.activity = "Starting installation"
        self.latest = ""
        self.diagnostics = []
        self.lines = []
        self.summary = ""
        self.retry = ""
        self.cancelled = False
        self.cancel_at = None
        self.cancel_level = 0
        self.returncode = None
        self.pending_output = ""
        self.pending_events = b""
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.selector = selectors.DefaultSelector()
        fd, self.log_path = tempfile.mkstemp(prefix="FastSetup-", suffix=".log")
        self.log = os.fdopen(fd, "wb", buffering=0)
        read_fd, write_fd = os.pipe()
        try:
            env = dict(os.environ, FASTSETUP_EVENT_FD=str(write_fd), PYTHONUNBUFFERED="1")
            self.process = subprocess.Popen(
                ["bash", str(script), *arguments], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env, pass_fds=(write_fd,), start_new_session=True)
        except BaseException:
            os.close(read_fd)
            self.log.close()
            self.selector.close()
            raise
        finally:
            os.close(write_fd)
        self.output = self.process.stdout
        for stream, kind in ((self.output, "output"), (read_fd, "events")):
            os.set_blocking(stream if isinstance(stream, int) else stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, kind)

    def diagnostic(self, value):
        value = clean(value)
        if value and value not in self.diagnostics:
            self.diagnostics.append(value)

    def event(self, kind, value):
        if kind == "stage" and value in STAGES:
            if self.stage is not None:
                self.completed.add(self.stage)
            self.stage, self.activity = value, value
        elif kind == "activity":
            self.activity = clean(value)
        elif kind in ("warning", "error"):
            self.diagnostic(value)
        elif kind in ("summary", "retry"):
            setattr(self, kind, "\n".join(clean(line) for line in value.splitlines()))

    def output_line(self, line):
        line = clean(line)
        self.lines.append(line)
        if line.strip():
            self.latest = line
        if DIAGNOSTIC.search(line):
            self.diagnostic(line)
        if self.stage == "Build":
            if "Compiling python3 modules" in line:
                self.activity = "Compiling Python modules"
            elif "All python modules compiled" in line:
                self.activity = "Finishing build"

    def feed_output(self, data, final=False):
        self.pending_output += self.decoder.decode(data, final=final)
        parts = re.split(r"\r\n|\r|\n", self.pending_output)
        self.pending_output = parts.pop()
        for line in parts:
            self.output_line(line)
        if final and self.pending_output:
            self.output_line(self.pending_output)
            self.pending_output = ""
        elif self.pending_output:
            self.latest = clean(self.pending_output[-65536:])
            if len(self.pending_output) > 65536:
                self.output_line(self.pending_output[:-65536])
                self.pending_output = self.pending_output[-65536:]

    def feed_events(self, data):
        self.pending_events += data
        while True:
            first = self.pending_events.find(b"\0")
            second = self.pending_events.find(b"\0", first + 1) if first >= 0 else -1
            if second < 0:
                break
            kind = self.pending_events[:first].decode("utf-8", "replace")
            value = self.pending_events[first + 1:second].decode("utf-8", "replace")
            self.pending_events = self.pending_events[second + 1:]
            self.event(kind, value)

    def _signal(self, number):
        try:
            os.killpg(self.process.pid, number)
        except ProcessLookupError:
            pass

    def cancel(self):
        if not self.cancelled and self.returncode is None:
            self.cancelled = True
            self.cancel_at = time.monotonic()
            self.activity = "Cancelling installation"
            self._signal(signal.SIGINT)

    def pump(self):
        if self.returncode is not None:
            return
        if self.cancel_at is not None:
            elapsed = time.monotonic() - self.cancel_at
            if elapsed >= 8 and self.cancel_level < 2:
                self._signal(signal.SIGKILL)
                self.cancel_level = 2
            elif elapsed >= 3 and self.cancel_level < 1:
                self._signal(signal.SIGTERM)
                self.cancel_level = 1
        # Bound each read pass so high-volume build output cannot starve drawing.
        for key, _ in self.selector.select(0):
            data = os.read(key.fd, 65536)
            if data:
                if key.data == "output":
                    self.log.write(data)
                    self.feed_output(data)
                else:
                    self.feed_events(data)
            else:
                self.selector.unregister(key.fileobj)
                if key.data == "events":
                    os.close(key.fd)
                else:
                    self.feed_output(b"", final=True)
        status = self.process.poll()
        if status is not None and not self.selector.get_map():
            self.returncode = 130 if self.cancelled else (status if status >= 0 else 128 - status)
            self.finished = time.monotonic()
            if self.returncode == 0 and self.stage:
                self.completed.add(self.stage)
            self.log.close()

    def close(self):
        """Stop a worker on UI failure, draining output while Bash cleans up."""
        if self.returncode is None:
            self.cancel()
            deadline = time.monotonic() + 9
            while self.returncode is None and time.monotonic() < deadline:
                self.pump()
                time.sleep(0.05)
            self._signal(signal.SIGKILL)
            self.process.wait()
        for key in list(self.selector.get_map().values()):
            if key.data == "events":
                os.close(key.fd)
        self.selector.close()
        self.output.close()
        self.log.close()

    def result(self):
        title = ("Setup cancelled" if self.cancelled else
                 "Setup complete" if self.returncode == 0 else "Setup failed")
        details = [title, "Log: " + self.log_path]
        if self.returncode != 0 and self.stage:
            details.append("Stage: " + self.stage)
        if self.diagnostics:
            details += ["", "Warnings and diagnostics:"] + self.diagnostics
        if self.returncode != 0:
            details += ["", "Last output:"] + self.lines[-20:]
        if self.summary or self.retry:
            details += ["", self.summary or self.retry]
        return "\n".join(details)


def progress(ui, screen, worker):
    """Draw at 10 Hz; scrolling and log viewing never pause the worker."""
    screen.timeout(100)
    log_view, offset = False, None
    frame = 0
    next_frame = time.monotonic()
    was_finished = False
    while True:
        try:
            time.sleep(max(0, next_frame - time.monotonic()))
            next_frame = time.monotonic() + 0.1
            worker.pump()
            if worker.returncode is not None and not was_finished:
                was_finished = True
                log_view, offset = False, None
            screen.erase()
            height, width = screen.getmaxyx()
            seconds = int((worker.finished or time.monotonic()) - worker.started)
            title = "TauFW setup | Elapsed %02d:%02d" % divmod(seconds, 60)
            start = ui._entry_header(screen, title, 13) if height >= 25 else 2
            if height < 25:
                ui._line(screen, 0, 0, title)
            if worker.returncode is not None:
                content = worker.lines if log_view else worker.result().splitlines()
            elif log_view:
                content = worker.lines
            else:
                content = []
                for stage in STAGES:
                    marker = "OK" if stage in worker.completed else ".."
                    if stage == worker.stage and stage not in worker.completed:
                        marker = "|/-\\"[frame % 4]
                    content.append("[%s] %s" % (marker, stage))
                if height - start < 16:
                    content = ["%s %s (%d/%d complete)" % (
                        "|/-\\"[frame % 4], worker.stage or "Starting",
                        len(worker.completed), len(STAGES))]
                else:
                    content.append("")
                content += [worker.activity, "Last output: " + worker.latest]
                if worker.diagnostics:
                    content += ["Warnings / diagnostics (%d)" % len(worker.diagnostics)]
                    content += worker.diagnostics
            # Wrap result/diagnostics so long activation commands remain readable.
            rows = content if log_view else []
            if not log_view:
                for line in content:
                    if line.startswith("Last output:") or worker.returncode is None and height - start < 16:
                        rows.append(line)
                    else:
                        rows.extend(textwrap.wrap(line, max(1, width - 2), replace_whitespace=False) or [""])
            visible = max(1, height - start - 2)
            maximum = max(0, len(rows) - visible)
            first = maximum if offset is None and log_view else min(offset or 0, maximum)
            for row, line in enumerate(rows[first:first + visible], start):
                ui._line(screen, row, 0, line)
            action = "Enter Close" if worker.returncode is not None else "Ctrl+C Cancel"
            footer = "L Log | " + action if width < 65 else "L Log/result | Up/Down/PgUp/PgDn Scroll | " + action
            ui._line(screen, height - 2, 0, footer)
            screen.refresh()
            frame += 1
            key = screen.getch()
            if key in (ord("l"), ord("L")):
                log_view, offset = not log_view, None
            elif key in (10, 13, ui.curses.KEY_ENTER) and worker.returncode is not None:
                return worker.returncode
            elif key == 3:
                worker.cancel()
            elif key in (ui.curses.KEY_UP, ui.curses.KEY_PPAGE):
                offset = max(0, first - (visible if key == ui.curses.KEY_PPAGE else 1))
            elif key in (ui.curses.KEY_DOWN, ui.curses.KEY_NPAGE):
                offset = min(maximum, first + (visible if key == ui.curses.KEY_NPAGE else 1))
        except KeyboardInterrupt:
            worker.cancel()


def main(argv=None):
    parser = ArgumentParser(description="Persistent interactive FastSetup screen.")
    parser.add_argument("--script", required=True)
    parser.add_argument("--selected", nargs="*", choices=[name for name, _ in COMPONENTS], default=[])
    parser.add_argument("arguments", nargs=REMAINDER)
    args = parser.parse_args(argv)
    ui = ConsoleUI.open(parser)
    if ui is None:
        return 1
    worker = None
    failure = None

    def session(screen):
        nonlocal worker
        selected = ui.setup_checklist(COMPONENTS, args.selected, screen=screen)
        if selected is None:
            return 130
        arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        worker = Worker(args.script, worker_arguments(arguments, selected))
        return progress(ui, screen, worker)

    try:
        status = ui.curses.wrapper(session)
    except KeyboardInterrupt:
        status = 130
    except Exception as error:
        failure = "Cannot continue the setup screen: %s" % clean(str(error))
        status = 1
    finally:
        if worker is not None:
            worker.close()
    if worker is not None:
        print(worker.result())
    elif status == 130:
        print("Setup cancelled; no installation changes were made.")
    if failure:
        print(failure, file=sys.stderr)
        if worker is None:
            print("Use --non-interactive to run setup without the screen.", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
