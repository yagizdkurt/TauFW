# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The screens of an iterative run (CL §55 step 4), opened from Continue > a run:

    pick_stage    Rerun from... / Advance until...   stages left, what happens right (a dry rerun of each stage,
                                                     or which stages an advance until it runs); Enter chooses
    pick_file     Edit run config (and the Start screen's E)   files left (40%), the selected file right (60%);
                                                     Enter opens the editor on it
    show_history  History                            the recipe versions and the stages left; right the selected
                                                     row's past: Tab moves into the attempts, Enter opens a log

The data is plain (interactive.py: stage_choices, run_files / analysis_files, file_text, run_history,
attempt_log); nothing here reads a file or imports the Framework. The panels over them (the rerun's confirm panel,
the rerun hint after a save) are ConsoleUI.ask().
"""
from ._plan_screen import table

__all__ = ["pick_stage", "pick_file", "show_history", "rerun_lines", "until_lines"]


FILE_SHARE = 0.4   # the file list's part of the width (the rest: the file)
SHORT = {"SUBMITTED": "JOBS", "WAITING": "JOBS", "MERGING": "MERGE", "NOT_IMPLEMENTED": "N/A"}


# =============================================================================
# ================================== TEXT =====================================


def _state(state):
    return SHORT.get(state, state)


def _wrapped(ui, lines, width):
    """(text, role) pairs wrapped to the width."""
    return [(part, role) for text, role in lines for part in ui._wrap(text, width)]


def rerun_lines(row, pending=None):
    """What a rerun from the stage of a stage_choices row does, as (text, role) lines (also the confirm panel's)."""
    plan = row.get("plan")
    if plan is None:
        return [(row.get("why") or "This stage cannot start a rerun.", "warning")]
    lines = []
    if plan.get("production"):
        lines += [("%s failed after max_tries: it goes on WAITING with max_tries more tries for its failed chunks; "
                   "nothing is moved (the job files stay). The stages after it run once it is done." % row["id"], None)]
    else:
        lines.append(("Set aside, then run again:", "accent"))
        width = max(len(item["stage"]) for item in plan["rows"])
        for item in plan["rows"]:
            where = ("-> " + item["archive"] if item.get("archive") else
                     "(never ran)" if item["state"] == "NEW" else "(nothing to move)")
            lines.append(("  %s  %-6s  %s" % (item["stage"].ljust(width), _state(item["state"]), where), None))
        lines.append(("", None))
        lines.append(("Kept as they are: " + (", ".join(plan["kept"]) if plan.get("kept") else "none"), None))
    if plan.get("recipe_changes") is not None or pending:
        changes = plan.get("recipe_changes")
        text = (", ".join("%s %s" % item for item in changes.items()) if changes else None) or pending
        lines += [("", None), ("! The edited recipe is taken first (%s)." % (text,), "warning")]
    if plan.get("bundle_changed"):
        lines += [("", None), ("Bundle files changed since the start: " +
                               ", ".join("%s %s" % item for item in plan["bundle_changed"].items()), None)]
    return lines


def until_lines(view, row):
    """What Advance until the stage of a stage_choices row does, as (text, role) lines."""
    if not row.get("until"):
        if view.get("next") is None:
            return [("Every stage is DONE: there is nothing to advance. Rerun from... runs a stage again.", "warning")]
        return [("%s is DONE: Advance until stops after a stage that is not done yet, %s or one after it."
                 % (row["id"], view["next"]), "warning")]
    ids = [stage["id"] for stage in view["stages"]]
    first, last = ids.index(view["next"]), ids.index(row["id"])
    runs = [stage["id"] for stage in view["stages"][first:last + 1] if stage["state"] != "DONE"]
    lines = [("Runs: " + ", ".join(runs), "accent"),
             ("Then the run pauses after %s: look at its output, then Continue." % row["id"], None)]
    later = ids[last + 1:]
    if later:
        lines.append(("Waiting for the next advance: " + ", ".join(later), None))
    if view.get("pending"):
        lines += [("", None), ("! " + view["pending"], "warning")]
    return lines


# =============================================================================
# ============================== STAGE PICKER =================================


def _choosable(row, mode):
    return row.get("plan") is not None if mode == "rerun" else bool(row.get("until"))


def _first(view, mode, preset):
    """The row the picker opens on: the preset stage, else (rerun) the failed or the last DONE stage that can
    start, (until) the next stage."""
    ids = [row["id"] for row in view["stages"]]
    if preset in ids:
        return ids.index(preset)
    rows = [index for index, row in enumerate(view["stages"]) if _choosable(row, mode)]
    if mode == "until":
        return ids.index(view["next"]) if view.get("next") in ids else 0
    failed = [index for index in rows if view["stages"][index]["state"] == "FAILED"]
    done = [index for index in rows if view["stages"][index]["state"] == "DONE"]
    return (failed or done[-1:] or rows or [0])[0]


def pick_stage(ui, screen, title, view, mode, position):
    """Rerun from... (mode "rerun") or Advance until... ("until") of a run: ("pick", stage id) or ("back", None).
    view: stage_choices(); position: {"selected": stage id}, kept by the caller."""
    ui._setup(screen)
    stages = view["stages"]
    selected = _first(view, mode, position.get("selected")) if stages else 0
    offset = 0
    dim = ui.curses.A_DIM if isinstance(getattr(ui.curses, "A_DIM", None), int) else 0  # a test's fake: none
    try:
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            ui._header(screen, title, badge=True)
            id_width = max([len(row["id"]) for row in stages] + [8])
            list_width = min(max(30, id_width + 22), width * 2 // 5)
            top, left, rows, columns = ui._panel(screen, 3, 1, height - 6, list_width, "Stages")
            first = max(0, selected - rows + 1)
            for index, row in enumerate(stages[first:first + rows], first):
                mark = (row["tag"] if mode == "rerun" and row.get("tag") else
                        "next" if mode == "until" and row["id"] == view.get("next") else "")
                label = "%s  %-6s %s" % (row["id"].ljust(id_width), _state(row["state"]), mark)
                role = ("error" if row["state"] == "FAILED" else "good" if row["state"] == "DONE" else None)
                color = ui.styles.get(role, 0) if _choosable(row, mode) else dim
                ui._line(screen, top + index - first, left, (("> " if index == selected else "  ") + label)[:columns],
                         index == selected, color)
            row = stages[selected] if stages else None
            choosable = row is not None and _choosable(row, mode) and not view.get("error")
            heading = ("%s %s" % ("Rerun from" if mode == "rerun" else "Advance until", row["id"]) if choosable else
                       "%s (%s)" % (row["id"], row["type"]) if row else "No stages")
            right = ui._panel(screen, 3, list_width, height - 6, width - list_width - 1, heading)
            if view.get("error"):
                content = [("The run's edited recipe cannot be taken, so nothing can start: fix bundle/recipe.yml "
                            "(Edit run config).", "error"), ("", None), (view["error"], "error")]
            elif row is None:
                content = [("The run has no stages.", None)]
            else:
                content = rerun_lines(row, view.get("pending")) if mode == "rerun" else until_lines(view, row)
            content = _wrapped(ui, content, right[3])
            offset, page = ui._viewport(screen, right, [text for text, _ in content], offset,
                                        line_colors=[role for _, role in content])
            ui._footer(screen, "Up/Down Stage | " + (("Enter Rerun... | " if mode == "rerun" else "Enter Advance | ")
                                                     if choosable else "") + "PgUp/Dn Details | Esc Back")
            screen.refresh()
            key = screen.getch()
            if key in (27, 3):
                return "back", None
            if key in (ui.curses.KEY_UP, ui.curses.KEY_DOWN) and stages:
                selected = (selected + (1 if key == ui.curses.KEY_DOWN else -1)) % len(stages)
                offset = 0
            elif key == ui.curses.KEY_NPAGE:
                offset += page
            elif key == ui.curses.KEY_PPAGE:
                offset = max(0, offset - page)
            elif key in (10, 13, ui.curses.KEY_ENTER) and choosable:
                return "pick", row["id"]
    except KeyboardInterrupt:
        return "back", None
    finally:
        if stages:
            position["selected"] = stages[selected]["id"]


# =============================================================================
# =============================== FILE SCREEN =================================


def _file_tag(item):
    """The marker of a file row, never cut: what changed, or that it is the recipe."""
    state = item.get("state") or ""
    return ("edited" if state.startswith("edited") else "added" if state.startswith("added") else
            "recipe" if item.get("recipe") else "")


def _file_head(item):
    """The first lines of the file panel: what the file is, who reads it, what changed."""
    lines = []
    if item.get("recipe"):
        lines.append(("The recipe: the stages, their options and inputs. Saved only if it passes its checks.", None))
    elif item.get("read_by"):
        lines.append(("Read by: " + ", ".join(item["read_by"]), None))
    else:
        lines.append(("No stage option names it (a python step may still read it).", None))
    if item.get("state"):
        lines.append(("! " + item["state"], "warning"))
    return lines + [("", None)]


def pick_file(ui, screen, title, files, read, position):
    """The files of a run (Edit run config) or of an analysis bundle (Start > E): ("edit", index) or ("back",
    None). read(path) -> the file's lines (file_text); position: {"selected": relative path}, kept by the caller."""
    ui._setup(screen)
    paths = [item["path"] for item in files]
    selected = paths.index(position["selected"]) if position.get("selected") in paths else 0
    offset, shown = 0, {}
    try:
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            ui._header(screen, title, badge=True)
            list_width = max(24, int(width * FILE_SHARE))
            top, left, rows, columns = ui._panel(screen, 3, 1, height - 6, list_width, "Files")
            first = max(0, selected - rows + 1)
            for index, item in enumerate(files[first:first + rows], first):
                tag = _file_tag(item)
                room = max(4, columns - 2 - (len(tag) + 1 if tag else 0))
                name = item["path"] if len(item["path"]) <= room else "..." + item["path"][-(room - 3):]
                label = ("> " if index == selected else "  ") + name.ljust(room) + (" " + tag if tag else "")
                role = "warning" if tag in ("edited", "added") else "accent" if tag == "recipe" else None
                ui._line(screen, top + index - first, left, label[:columns], index == selected,
                         ui.styles.get(role, 0) if role else 0)
            item = files[selected] if files else None
            right = ui._panel(screen, 3, list_width, height - 6, width - list_width - 1,
                              item["path"] if item else "No files")
            if item is None:
                content = [("There are no files to edit.", None)]
            else:
                if selected not in shown:
                    shown[selected] = read(item["file"])
                number = len(str(len(shown[selected])))
                content = _wrapped(ui, _file_head(item), right[3]) + [
                    ("%*d  %s" % (number, index, line), None) for index, line in enumerate(shown[selected], 1)]
            offset, page = ui._viewport(screen, right, [text for text, _ in content], offset,
                                        line_colors=[role for _, role in content])
            ui._footer(screen, "Up/Down File | " + ("Enter Edit | " if item else "") + "PgUp/Dn Scroll | Esc Back")
            screen.refresh()
            key = screen.getch()
            if key in (27, 3):
                return "back", None
            if key in (ui.curses.KEY_UP, ui.curses.KEY_DOWN) and files:
                selected = (selected + (1 if key == ui.curses.KEY_DOWN else -1)) % len(files)
                offset = 0
            elif key == ui.curses.KEY_NPAGE:
                offset += page
            elif key == ui.curses.KEY_PPAGE:
                offset = max(0, offset - page)
            elif key in (10, 13, ui.curses.KEY_ENTER) and item:
                return "edit", selected
    except KeyboardInterrupt:
        return "back", None
    finally:
        if files:
            position["selected"] = files[selected]["path"]


# =============================================================================
# ================================= HISTORY ===================================


def _history_rows(view):
    """The rows of History's left panel: (key, label, role); None is an empty line."""
    rows = [("versions", "Recipe versions (%d)" % len(view["versions"]), "accent"), None]
    width = max([len(stage["id"]) for stage in view["stages"]] + [8])
    for index, stage in enumerate(view["stages"]):
        count = len(stage["attempts"])
        tries = "%d attempt%s" % (count, "s" if count > 1 else "") if count else ""
        role = "error" if stage["state"] == "FAILED" else "good" if stage["state"] == "DONE" else None
        rows.append((index, "%s  %-6s %s" % (stage["id"].ljust(width), _state(stage["state"]), tries), role))
    if view.get("removed"):
        rows += [None, ("removed", "Removed stages (%d)" % len(view["removed"]), None)]
    return rows


def _history_details(ui, view, key, width, focus):
    """(lines as (text, role), [the line of each attempt]) of the right panel; focus: the attempt in focus."""
    if key == "versions":
        rows = [("v%s" % (item["version"]), item["time"], item["text"] + (" (DONE kept: %s)" % ", ".join(item["done"])
                                                                         if item["done"] else ""), item["file"] or "-")
                for item in view["versions"]]
        lines = [(line, "accent" if index == 0 else None)
                 for index, line in enumerate(table(["version", "time", "change", "copy"], rows, width, fill=2))]
        return lines + [("", None), ("Each version is a full copy of the run's recipe in recipes/.", None)], []
    if key == "removed":
        rows = [(item["id"], item["state"], item["time"], item["archive"] or "-") for item in view["removed"]]
        return [(line, "accent" if index == 0 else None)
                for index, line in enumerate(table(["stage", "was", "removed", "kept in"], rows, width))], []
    stage = view["stages"][key]
    lines = [("now  %s%s" % (stage["state"], "  " + stage["time"] if stage["time"] else ""),
              "error" if stage["state"] == "FAILED" else "good" if stage["state"] == "DONE" else None)]
    if stage["message"]:
        lines += [("     " + part, None) for part in ui._wrap(stage["message"], max(1, width - 5))]
    marks = []
    for index, attempt in enumerate(stage["attempts"]):
        why = ("rerun from %s" % attempt["start"] if attempt["reason"] == "rerun" else "failed")
        lines.append(("", None))
        marks.append(len(lines))
        lines.append((("> " if index == focus else "  ") + "#%s  %-18s was %-6s %s" % (
            attempt["attempt"], why, _state(attempt["state"]), attempt["time"]),
                      "accent" if index == focus else None))
        if attempt["message"]:
            lines += [("      " + part, None) for part in ui._wrap(attempt["message"], max(1, width - 6))]
        lines.append(("      " + (attempt["archive"] or "nothing moved (kept in place)"), None))
    if not stage["attempts"]:
        lines += [("", None), ("No earlier attempts: the stage ran once (or not yet).", None)]
    return lines, marks


def show_history(ui, screen, title, view, read_log, position):
    """History of a run until Esc. read_log(archive) -> the lines of an earlier attempt's logs, shown in a panel
    over the screen (Enter on an attempt). position: the selected row, kept by the caller."""
    ui._setup(screen)
    rows = _history_rows(view)
    keys = [row[0] for row in rows if row is not None]
    selected = position.get("selected") if position.get("selected") in keys else "versions"
    offset, focus = 0, None
    try:
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            ui._header(screen, title, badge=True)
            list_width = min(max(30, max(len(row[1]) for row in rows if row) + 6), width * 2 // 5)
            top, left, lines, columns = ui._panel(screen, 3, 1, height - 6, list_width, "History")
            at = [index for index, row in enumerate(rows) if row is not None and row[0] == selected][0]
            first = max(0, at - lines + 1)
            for index, row in enumerate(rows[first:first + lines]):
                if row is None:
                    continue
                key, label, role = row
                ui._line(screen, top + index, left, (("> " if key == selected else "  ") + label)[:columns],
                         key == selected and focus is None, ui.styles.get(role, 0) if role else 0)
            stage = view["stages"][selected] if isinstance(selected, int) else None
            heading = ("Recipe versions" if selected == "versions" else "Removed stages" if selected == "removed"
                       else "%s (%s)" % (stage["id"], stage["type"]))
            right = ui._panel(screen, 3, list_width, height - 6, width - list_width - 1, heading)
            content, marks = _history_details(ui, view, selected, right[3], focus)
            if focus is not None:  # keep the attempt in focus in sight
                offset = min(offset, marks[focus]) if marks[focus] < offset else max(offset, marks[focus] - right[2] + 4)
            offset, page = ui._viewport(screen, right, [text for text, _ in content], offset,
                                        line_colors=[role for _, role in content])
            attempts = bool(stage and stage["attempts"])
            ui._footer(screen, "Up/Down Attempt | Enter Open log | Tab Rows | Esc Rows" if focus is not None else
                       "Up/Down Row | " + ("Tab Attempts | " if attempts else "") + "PgUp/Dn Details | Esc Back")
            screen.refresh()
            key = screen.getch()
            if key in (27, 3):
                if focus is not None:
                    focus = None
                    continue
                return
            if key in (9, getattr(ui.curses, "KEY_RIGHT", None), getattr(ui.curses, "KEY_LEFT", None)):
                focus = None if focus is not None or not attempts else 0
            elif key in (ui.curses.KEY_UP, ui.curses.KEY_DOWN):
                step = 1 if key == ui.curses.KEY_DOWN else -1
                if focus is not None:
                    focus = (focus + step) % len(stage["attempts"])
                else:
                    selected, offset = keys[(keys.index(selected) + step) % len(keys)], 0
            elif key == ui.curses.KEY_NPAGE:
                offset += page
            elif key == ui.curses.KEY_PPAGE:
                offset = max(0, offset - page)
            elif key in (10, 13, ui.curses.KEY_ENTER) and focus is not None:
                attempt = stage["attempts"][focus]
                ui._log_panel(screen, "%s attempt #%s" % (stage["id"], attempt["attempt"]),
                              read_log(attempt["archive"]))
    except KeyboardInterrupt:
        return
    finally:
        position["selected"] = selected
