# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Terminal bells for completed operations; disabled by UserConfig notifications: false.

Only an attached terminal receives BEL. Workers whose output goes to a log stay
silent; the menu follows their results independently of the screen being shown.
"""
import sys
import threading

if __name__.startswith("TauFW."):
    from TauFW.Utilities import UserConfig
else:  # standalone installer, before cmsenv
    import UserConfig


def bell(stream=None):
    """Send one BEL to a terminal, never to a log; notification failures are harmless."""
    stream = sys.stderr if stream is None else stream
    try:
        if not stream.isatty() or UserConfig.load().get("taufw_user.notifications", True) is not True:
            return False
        stream.write("\a")
        stream.flush()
        return True
    except (OSError, ValueError, UserConfig.UserConfigError):
        return False


class OperationNotifications:
    """Watch menu operations once a second, including while another screen is open.

    A separate store owns this thread's readers. Existing finished operations are
    silent on entry; each newly finished operation is considered only once.
    """

    def __init__(self, root):
        from .operations import OperationStore
        self.store = OperationStore(root)
        self.states = {}
        self.stop = threading.Event()

    def poll(self, initial=False):
        from .operations import DONE, RUNNING, STOPPING, STOPPED, EventReader
        active = (RUNNING, STOPPING)
        notify = False
        for operation in self.store.all():
            if operation.kind not in ("run", "tests"):
                continue
            state = operation.state()
            earlier = self.states.get(operation.path)
            self.states[operation.path] = state
            if (initial or state in active or (earlier is not None and earlier not in active)
                    or state == STOPPED):
                continue
            if operation.kind == "run" and state == DONE:
                events = EventReader(operation.events_path).read()
                run_state = next((event.get("state") for event in reversed(events)
                                  if event.get("kind") == "run_state"), None)
                if run_state == "WAITING":
                    continue  # an advance returned; batch jobs are still running
            notify = True
        if notify:
            bell()

    def _watch(self):
        while not self.stop.wait(1.0):
            try:
                self.poll()
            except (OSError, ValueError):
                pass  # an unavailable operation directory must not interrupt the menu

    def __enter__(self):
        try:
            self.poll(initial=True)
        except (OSError, ValueError):
            pass
        self.thread = threading.Thread(target=self._watch, name="taufw-notifications", daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *error):
        self.stop.set()
        self.thread.join(timeout=1.0)
