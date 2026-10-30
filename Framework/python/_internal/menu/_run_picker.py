# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Adaptive run list and read-only preview. The supplied callback never waits for files or a command."""
import time

from ._loading import draw_loading
from ._operation_screen import printable


MIN_WIDTH, MIN_HEIGHT = 120, 18
ACTION_HELP = {
    "wait": "Run every stage that is not done, checking the jobs every 10 minutes, until the run is done or "
            "failed. You can leave the progress screen.",
    "next": "Run the next stage that is not done (waiting for its jobs), then stop: the run is paused. Look at its "
            "output, then go on.",
    "until": "Choose a stage: the run goes on until that stage is done, then pauses.",
    "rerun_failed": "Run the failed stage again once its cause is fixed, then go on to the end. Its failed attempt "
                    "is kept in logs/<id>/attempt<N>/; the stages before it are kept.",
    "rerun_failed_production": "Resubmit the failed chunks with more tries, then go on to the end. Job files stay.",
    "rerun": "Choose a stage: it and every stage after it are set aside (kept in logs/<id>/attempt<N>/) and run "
             "again.",
    "edit": "Edit the run's own recipe and bundle files (not those in Analyses/). The next advance or rerun reads "
            "them.",
    "history": "The run's recipe versions and every earlier attempt of its stages, with their logs.",
    "inspect": "Show the saved stage states and live job counts without changing the run.",
}


def help_key(key, view):
    """The ACTION_HELP key of an action of a run view (a failed production has its own)."""
    retry = view.get("retry") or {}
    return "rerun_failed_production" if key == "rerun_failed" and retry.get("tries") else key


def _actions(view):
    """The actions of a run view (interactive.run_preview), in their fixed order; what cannot be done is left out
    (CL §55 step 4, M1)."""
    if not view or view.get("loading") or view.get("error"):
        return []
    if view.get("advancing"):
        return [("select", "Follow the running advance"), ("history", "History"), ("inspect", "Inspect status")]
    lock = view.get("lock")
    if lock and not (lock.get("lost") and lock.get("local")):
        return [("select", "Review lost advance / take over" if lock.get("lost") else "View advance lock"),
                ("history", "History"), ("inspect", "Inspect status")]
    choices = []
    if view.get("can_advance"):
        following = view.get("next")
        choices += [("wait", "Advance to the end"), ("next", "Next stage only" + (": " + following if following
                                                                                  else "")),
                    ("until", "Advance until...")]
    retry = view.get("retry")
    if retry:
        choices.append(("rerun_failed", "Rerun %s (failed)" % retry["stage"]))
    return choices + [("rerun", "Rerun from..."), ("edit", "Edit run config"), ("history", "History"),
                      ("inspect", "Inspect status")]


def _details(ui, screen, rect, view, mode, focused, action, offset):
    top, left, rows, width = rect
    if view.get("error"):
        lines = ui._wrap("Cannot read run: " + view["error"], width)
        return ui._viewport(screen, rect, lines, offset, line_colors=["error"] * len(lines))
    if not view.get("run_id"):
        draw_loading(ui, screen, rect)
        return offset, 1
    ui._line(screen, top, left, ("Run: " + view["run_id"])[:width], color=ui.styles["accent"])
    state = "Saved state: " + view["state"] + (" | Advancing" if view.get("advancing") else "")
    if view.get("loading") or view.get("reading"):
        state += " | READING STATUS" if mode == "inspect" else " | Loading"
        state += " " + "|/-\\"[int(time.monotonic() * 8) % 4]
    elif mode == "inspect" and view.get("command_state") in ("FAILED", "STOPPED", "LOST"):
        state += " | Status command: " + view["command_state"]
    ui._line(screen, top + 1, left, state[:width])
    body = (top + 3, left, max(1, rows - 3), width)
    if mode == "inspect":
        lines = [part for line in view.get("output", ()) for part in ui._wrap(printable(line), width)]
        if not lines and (view.get("loading") or view.get("reading")):
            draw_loading(ui, screen, body)
            return offset, 1
        lines = lines or ["No status output. Press R to retry."]
        return ui._viewport(screen, body, lines, offset)
    choices = _actions(view)
    lines, colors = [], []
    for index, (_, label) in enumerate(choices):
        lines.append(("> " if focused and index == action else "  ") + label)
        colors.append("accent" if focused and index == action else None)
    retry, lock = view.get("retry"), view.get("lock")
    if focused and choices:
        help_text = ACTION_HELP.get(help_key(choices[action][0], view))
        if help_text:
            lines += ["", help_text]
    if view.get("pending"):
        lines += ["", "! " + view["pending"]]
        colors += [None] * (len(lines) - len(colors) - 1) + ["warning"]
    if retry:
        lines += ["", "Failed: " + retry.get("message", "")]
        if retry.get("tries"):
            lines += ["Tries: %d made; a retry allows up to %d" % tuple(retry["tries"])]
        changed = retry.get("changed")
        lines += ["Bundle changes: " + (", ".join("%s %s" % pair for pair in changed.items()) if changed else
                                      "unknown" if changed is None else "none")]
    if lock:
        lines += ["", "Advance on %s (pid %s)" % (lock.get("host", "?"), lock.get("pid", "?")),
                  "No sign of life for %ds." % lock.get("quiet", 0) if lock.get("lost") else
                  "Another advance holds this run's lock."]
    width_id = max([len(stage["id"]) for stage in view.get("stages", ())] + [4])
    lines += ["", "Stages"] + ["%-8s %s%s%s" % (stage["state"], stage["id"].ljust(width_id),
                                              "  <- next" if stage["id"] == view.get("next") else "",
                                              "  %d earlier attempt%s" % (stage["attempts"], "s" if
                                                                          stage["attempts"] > 1 else "")
                                              if stage.get("attempts") else "") +
                               ((": " + stage["message"]) if stage.get("message") else "")
                               for stage in view.get("stages", ())]
    colors += [None] * (len(lines) - len(colors))
    wrapped = [(part, color) for line, color in zip(lines, colors) for part in ui._wrap(printable(line), width)]
    return ui._viewport(screen, body, [line for line, _ in wrapped], offset,
                        line_colors=[color for _, color in wrapped])


def pick(ui, screen, labels, colors, summaries, preview, mode, position, live, finding=False):
    ui._setup(screen)
    screen.timeout(100)
    selected = min(position.get("selected", 0), len(labels) - 1)
    offset, action = position.get("offset", 0), position.get("action", 0)
    focused = position.get("pane", False)
    started = time.monotonic()
    count = len(summaries)
    try:
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            wide = width >= MIN_WIDTH and height >= MIN_HEIGHT
            ui._header(screen, "Continue an existing run" if mode == "continue" else "Inspect run status", badge=True)
            list_width = max(44, int(width * 0.4)) if wide else width - 2
            rect = ui._panel(screen, 3, 1, height - 6, list_width,
                             "Finding runs..." if finding else "Runs" if wide else "Menu")
            top, left, rows, columns = rect
            state_width = max([10] + [len(str(row[1] or "UNREADABLE")) for row in summaries])
            offsets = [i + (i >= count and count > 0) for i in range(len(labels))]
            first = 0
            while first < selected and offsets[selected] - offsets[first] >= max(1, rows):
                first += 1
            for index in range(first, len(labels)):
                row = offsets[index] - offsets[first]
                if row >= rows:
                    break
                label = labels[index]
                if wide and index < count:
                    name, state, _ = summaries[index]
                    state = state or ("loading..." if "loading..." in label else "UNREADABLE")
                    name_width = max(4, columns - state_width - 5)
                    name = name if len(name) <= name_width else name[:name_width - 3] + "..."
                    label = name.ljust(name_width) + " | " + state
                    if " | advancing:" in labels[index]:
                        label += " *"
                label = ("> " if index == selected else "  ") + label
                ui._line(screen, top + row, left, label[:columns], index == selected and not (wide and focused),
                         ui.styles.get(colors[index], 0))
            view = preview(selected if wide and selected < count else None)
            choices = _actions(view) if mode == "continue" else []
            action = min(action, max(0, len(choices) - 1))
            page = 1
            if wide:
                right = ui._panel(screen, 3, list_width, height - 6, width - list_width - 1,
                                  "Actions and stages" if mode == "continue" else "Run status")
                if finding:
                    draw_loading(ui, screen, right)
                elif selected >= count:
                    hint = "Enter a run directory manually." if selected == count else "Return to the main menu."
                    ui._line(screen, right[0], right[1], hint[:right[3]])
                else:
                    offset, page = _details(ui, screen, right, view, mode, focused, action, offset)
            else:
                focused = False
            editable = mode == "continue" and any(key == "edit" for key, _ in choices)
            footer = ("Up/Down Move | Enter Select | Esc Back" if not wide else
                      "Up/Down Action | Enter Select | Tab Runs | E Edit | R Refresh | Esc Runs" if focused and editable
                      else "Up/Down Action | Enter Select | Tab Runs | PgUp/Dn Details | R Refresh | Esc Runs" if focused
                      else "Up/Down Run | Enter Actions | Tab Pane | E Edit | PgUp/Dn Details | R Refresh | Esc Back"
                      if editable else
                      "Up/Down Run | Enter Actions | Tab Pane | PgUp/Dn Details | R Refresh | Esc Back"
                      if mode == "continue" else
                      "Up/Down Run | Enter Full screen | PgUp/Dn Status | R Refresh | Esc Back")
            ui._footer(screen, footer)
            screen.refresh()
            key = screen.getch()
            if key in (27, 3):
                if wide and focused:
                    focused = False
                    continue
                return "back", None
            if key in (9, getattr(ui.curses, "KEY_RIGHT", None), getattr(ui.curses, "KEY_LEFT", None)) and wide:
                focused = not focused if mode == "continue" and choices else False
                if focused:
                    offset = 0
            elif key in (ui.curses.KEY_UP, ui.curses.KEY_DOWN):
                step = 1 if key == ui.curses.KEY_DOWN else -1
                if focused and choices:
                    action = (action + step) % len(choices)
                    offset = 0
                else:
                    selected = (selected + step) % len(labels)
                    offset, action = 0, 0
            elif key == ui.curses.KEY_NPAGE and wide:
                offset += page
            elif key == ui.curses.KEY_PPAGE and wide:
                offset = max(0, offset - page)
            elif key in (ord("r"), ord("R")) and wide and selected < count:
                preview(selected, refresh=True)
            elif key in (ord("e"), ord("E")) and wide and selected < count and editable:
                return "edit", selected
            elif key in (10, 13, ui.curses.KEY_ENTER):
                if selected == count:
                    return "manual", None
                if selected == count + 1:
                    return "back", None
                if wide and mode == "continue":
                    if choices and focused:
                        return choices[action][0], selected
                    if choices:
                        focused, action, offset = True, 0, 0
                else:
                    return "select", selected
            if live and time.monotonic() - started >= 0.5:
                return "refresh", None
    except KeyboardInterrupt:
        return "back", None
    finally:
        position.update(selected=selected, offset=offset, action=action, pane=focused)
