# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The supervisor of an operation that runs behind the TauFW menu (_operations.py).

Operation.start() runs it by its path, in a session of its own, with the
operation's directory as the only argument:

    python3 -B _supervisor.py <operation directory>

It reads operation.json (argv, cwd, heartbeat, escalate, signal), starts the command
(in its own process group, output to output.log) and, until the command ends:

  - every `heartbeat` seconds writes heartbeat.json {host, pid, child, t}: a
    menu tells a running operation from a lost one by it
  - when the file `stop` appears: SIGINT to the command's group (signal
    "group", the default) or to the command alone (signal "command": it ends
    what it started itself; taufw.py first lets a job submission finish); with
    escalate, SIGTERM after TERM_AFTER s and SIGKILL after KILL_AFTER s to the
    group. SIGTERM to the supervisor itself (e.g. the login session ends)
    counts as `stop`
  - when the file `kill` appears: SIGKILL to the group at once

then writes exit.json {returncode, stopped, finished}. The exit code is the
command's, 128+N after signal N, STOP_EXIT when it was stopped and did not
succeed. JSON files are written to a temporary name and renamed: a reader never
sees half a file.

A menu only reads these files and writes `stop`: the operation keeps running
when the menu leaves its screen or quits, its exit code is kept without the
menu, and it can be stopped from any machine that sees the directory (AFS; the
supervisor looks for `stop` every TICK s). Standard library only, no TauFW
imports: it runs by its path, also where TauFW is not built.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time

# =============================================================================
# ================================= CONSTANTS =================================


OPERATION_FILE = "operation.json"
OUTPUT_FILE = "output.log"
HEARTBEAT_FILE = "heartbeat.json"
EXIT_FILE = "exit.json"
STOP_FILE = "stop"
KILL_FILE = "kill"
STOP_EXIT = 130     # exit code of a stopped command (as after Ctrl-C)
TERM_AFTER = 3.0    # seconds after a stop before SIGTERM (with escalate)
KILL_AFTER = 8.0    # seconds after a stop before SIGKILL (with escalate)
TICK = 0.2          # seconds between two looks at the command and the files
SIGKILL = getattr(signal, "SIGKILL", signal.SIGTERM)  # Windows (unit tests only) has no SIGKILL


# =============================================================================
# ================================ SUPERVISOR =================================


def supervise(directory, popen=subprocess.Popen, clock=time.time, sleep=time.sleep, terminated=()):
    """Run the operation of `directory` to its end (see the module docstring); return its exit code.
    terminated: becomes non-empty when the supervisor got SIGTERM (main() installs the handler)."""
    path = lambda name: os.path.join(directory, name)  # noqa: E731
    with open(path(OPERATION_FILE)) as stream:
        operation = json.load(stream)
    heartbeat = float(operation.get("heartbeat", 5.0))
    escalate = operation.get("escalate", True)
    alone = operation.get("signal", "group") == "command"
    try:
        with open(path(OUTPUT_FILE), "ab") as output:
            process = popen(list(operation["argv"]), cwd=operation.get("cwd"), stdin=subprocess.DEVNULL,
                            stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as error:
        with open(path(OUTPUT_FILE), "a") as output:
            output.write("Cannot start %s: %s\n" % (operation["argv"][0], error))
        write_json(path(EXIT_FILE), dict(returncode=127, stopped=False, finished=clock()))
        return 127
    host, beat, stopped, level = socket.gethostname(), None, None, 0
    while True:
        status = process.poll()
        if status is not None:
            break
        now = clock()
        if beat is None or now - beat >= heartbeat:
            write_json(path(HEARTBEAT_FILE), dict(host=host, pid=os.getpid(), child=process.pid, t=now))
            beat = now
        if level < 2 and os.path.exists(path(KILL_FILE)):
            stopped, level = stopped or now, 2
            _signal(process, SIGKILL)
        elif stopped is None and (terminated or os.path.exists(path(STOP_FILE))):
            stopped = now
            _signal(process, signal.SIGINT, group=not alone)
        elif stopped is not None and escalate:
            if now - stopped >= KILL_AFTER and level < 2:
                level = 2
                _signal(process, SIGKILL)
            elif now - stopped >= TERM_AFTER and level < 1:
                level = 1
                _signal(process, signal.SIGTERM)
        sleep(TICK)
    returncode = STOP_EXIT if stopped is not None and status != 0 else (status if status >= 0 else 128 - status)
    write_json(path(EXIT_FILE), dict(returncode=returncode, stopped=stopped is not None, finished=clock()))
    return returncode


def write_json(path, data):
    """Write `data` to a temporary file and rename it to `path`: the change is all or nothing."""
    temporary = "%s.%d.tmp" % (path, os.getpid())
    with open(temporary, "w") as stream:
        json.dump(data, stream)
    os.replace(temporary, path)


def _signal(process, number, group=True):
    """Send a signal to the command's process group (group=False, or where there are no groups: to the command
    alone)."""
    try:
        if group and hasattr(os, "killpg"):
            os.killpg(process.pid, number)
        else:
            process.send_signal(number)
    except (ProcessLookupError, OSError):
        pass  # it ended just before


def main(argv):
    """The supervisor as its own process: SIGINT and SIGHUP are ignored (stopping is asked through the `stop`
    file, and the terminal is not its own), SIGTERM counts as a stop."""
    terminated = []
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda number, frame: terminated.append(number))
    supervise(argv[1], terminated=terminated)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
