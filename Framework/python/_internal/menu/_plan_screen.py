# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The plan of a recipe (Start a new run, after a recipe is selected): what a run would do, before it starts.

The data is the plan that the operations computed in the menu's own process (prepare_plan: a dry plan, nothing
is written; see _navigation.py for its keys). Two panels:

    left  Start run          red and refused with errors, yellow with warnings (it still starts); closed while
                             stages are checking
          Overview           where the run goes, the PicoProducer config, the totals (the focus when it opens)
          Errors (N)         only when there are any
          Warnings (N)       only when there are any
          1 <stage id> ...   one row per stage; a turning mark while its checks run
    right the selected row's details: a stage's inputs, files, samples (production) or commands (local stages);
          the decay animation while the stage is checking

The screen opens with a quick plan: the checks that open data files (the tuples' branches, slow on EOS) run behind
it in a process of their own (update(): None, or the whole plan that then replaces the view, in place). Until it
comes, the stages that have them say checking and Start is closed.

F switches the commands of a local stage between one cut line each and the full, wrapped command. E opens the
file screen of the analysis (Edit analysis: its files, the editor on one; navigation.edit_analysis). Also here: stage_table() (the stage table of the recipe list) and there_are() ("There are 2 errors").
"""

import time

from ._loading import draw_loading

__all__ = ["show_plan", "stage_table", "there_are", "table"]


GAP = "  "  # between two columns of a table
CUT = "..."
START_HELP = {"error": "The recipe has errors (see Errors): it cannot start until they are fixed.",
              "warning": "Start a run of this recipe. It has warnings (see Warnings); it can still run.",
              None: "Start a run of this recipe: create its run directory and advance it once.",
              "checking": "The tuple files of the stages marked in the list are checked (their branches). Start "
                          "opens when the checks are done; the other rows can be read meanwhile."}
CHECKING = "Checking the tuple files (their branches)..."
FRAME = 0.15  # seconds between two draws while stages are checking (the animation's frame)
SPIN = "|/-\\"  # the mark of a checking stage in the list, one character per frame


# =============================================================================
# ================================== TEXT =====================================


def there_are(count, what):
    """'There is 1 error', 'There are 2 errors'."""
    return "There is 1 %s" % what if count == 1 else "There are %d %ss" % (count, what)


def _cut(text, width):
    text = str(text)
    if len(text) <= width:
        return text
    return text[:max(0, width - len(CUT))] + CUT[:width]


def table(headers, rows, width, fill=None):
    """Aligned columns, two spaces apart; each line is cut at width (never wrapped: the columns stay aligned).
    fill: the index of the column that takes what is left of the width (cut with ...); it is left out if less than
    8 columns are left for it."""
    rows = [[str(value) for value in row] for row in rows]
    widths = [max([len(header)] + [len(row[index]) for row in rows]) for index, header in enumerate(headers)]
    if fill is not None:
        left = width - sum(w for index, w in enumerate(widths) if index != fill) - len(GAP) * (len(widths) - 1)
        if left < 8:
            headers = [h for index, h in enumerate(headers) if index != fill]
            rows = [[v for index, v in enumerate(row) if index != fill] for row in rows]
            widths = [w for index, w in enumerate(widths) if index != fill]
        else:
            widths[fill] = min(widths[fill], left)
    lines = []
    for row in [list(headers)] + rows:
        cells = [_cut(value, w).ljust(w) for value, w in zip(row, widths)]
        lines.append(_cut(GAP.join(cells).rstrip(), width))
    return lines


def stage_table(stages, width):
    """The stages of a recipe view, (id, type, description[, reads]) each, as # / Stage ID / Input / Description;
    the Description is cut first when the width is short."""
    rows = [(index, stage[0], stage[3] if len(stage) > 3 else "-", stage[2] or "")
            for index, stage in enumerate(stages, 1)]
    return table(["#", "Stage ID", "Input", "Description"], rows, width, fill=3)


# =============================================================================
# ================================= DETAILS ===================================


def _headed(lines):
    """A table's lines with their roles: the header in the accent color."""
    return [(line, "accent" if index == 0 else None) for index, line in enumerate(lines)]


def _checking(view):
    return any(stage.get("checking") for stage in view.get("stages", ()))


def _rows(view, mark=""):
    """The rows of the left panel: (key, label, role); None is an empty line between two groups. mark: after the
    label of a checking stage."""
    errors, warnings = view.get("errors", ()), view.get("warnings", ())
    start = "error" if errors else "warning" if warnings else "good"
    if _checking(view):
        rows = [("start", "Start run (wait)", None), None, ("overview", "Overview", None)]
    else:
        rows = [("start", "Start run", start), None, ("overview", "Overview", None)]
    if errors:
        rows.append(("errors", "Errors (%d)" % len(errors), "error"))
    if warnings:
        rows.append(("warnings", "Warnings (%d)" % len(warnings), "warning"))
    rows.append(None)
    for index, stage in enumerate(view.get("stages", ())):
        role = "error" if errors else "warning" if stage.get("note") else None
        label = "%d %s" % (index + 1, stage["id"]) + (" " + mark if mark and stage.get("checking") else "")
        rows.append((index, label, role))
    return rows


def _title(view, key):
    if key == "start":
        return "Start run"
    if key == "overview":
        return "Overview"
    if key in ("errors", "warnings"):
        return key.capitalize()
    stage = view["stages"][key]
    return "%s (%s)" % (stage["id"], stage["type"])


def _details(ui, view, key, width, full):
    """The lines of the right panel for the selected row: (text, role) each."""
    lines = []

    def add(text, role=None):
        lines.extend((part, role) for part in ui._wrap(text, width))

    errors, warnings = view.get("errors", ()), view.get("warnings", ())
    if key == "start":
        if _checking(view):
            add(START_HELP["checking"])
            return lines
        add(START_HELP["error" if errors else "warning" if warnings else None],
            "error" if errors else "warning" if warnings else None)
        return lines
    if key in ("errors", "warnings"):
        for message in errors if key == "errors" else warnings:
            add("- " + message, "error" if key == "errors" else "warning")
        return lines
    if key == "overview":
        for line in view.get("overview", ()):
            add(line)
        if errors:
            add("")
            add(there_are(len(errors), "error") + ": see Errors.", "error")
        if warnings:
            add("")
            add(there_are(len(warnings), "warning") + ": see Warnings.", "warning")
        return lines
    stage = view["stages"][key]
    if stage.get("description"):
        add(stage["description"])
    add("Inputs: " + (stage.get("inputs") or stage.get("reads") or "none"))
    if stage.get("note"):
        add("")
        add(stage["note"], "error" if errors else "warning")
    if stage.get("files"):
        add("")
        lines.extend(_headed(table(["option", "file", "from"], stage["files"], width, fill=1)))
    if stage.get("samples") is not None:
        add("")
        samples = _headed(table(["era", "channel", "sample", "files", "chunks", "try", "conflict"], stage["samples"],
                                width))
        lines.extend((line, "warning" if role is None and line.endswith("yes") else role) for line, role in samples)
        add("%d sample(s), %d job(s)" % (len(stage["samples"]), stage.get("jobs", 0)))
    if stage.get("steps") is not None:
        add("")
        add("Working directory: " + stage.get("cwd", ""))
        if stage.get("subdirs"):
            add("Commands run in: %s (relative to the working directory)" % ", ".join(stage["subdirs"]))
        add("")
        label_width = max([len(label) for label, _ in stage["steps"]] + [0])
        for index, (label, command) in enumerate(stage["steps"], 1):
            number = "%2d. " % index
            if full:  # cut in pieces of the width, not at spaces: a long path would leave short lines
                add(number + label)
                step = max(1, width - len(number))
                lines.extend((" " * len(number) + command[at:at + step], None) for at in range(0, len(command), step))
            else:
                lines.append((_cut(number + label.ljust(label_width) + GAP + command, width), None))
        add("%d command(s)" % len(stage["steps"]))
    if stage.get("notes"):
        add("")
        add("Notes:")
        for note in stage["notes"]:
            add("- " + note, "warning")
    return lines


# =============================================================================
# ================================== SCREEN ===================================


def show_plan(ui, screen, title, view, position, update=None):
    """Draw the plan until the user answers: "start" (Enter on Start run, only without errors and once no stage is
    checking), "edit" (E) or "back" (Esc). position: the selected row, the details' offset and the command form,
    kept by the caller. update: while stages are checking, asked at every frame (see the module's docstring)."""
    ui._setup(screen)
    selected = position.get("selected", "overview")
    offset, full = position.get("offset", 0), position.get("full", False)
    try:
        while True:
            checking = _checking(view)
            screen.timeout(int(FRAME * 1000) if checking and update else -1)
            rows = _rows(view, SPIN[int(time.monotonic() / FRAME) % len(SPIN)] if checking else "")
            keys = [row[0] for row in rows if row is not None]
            selected = selected if selected in keys else "overview"
            screen.erase()
            height, width = screen.getmaxyx()
            ui._header(screen, title, badge=True)
            page = 1
            stage = view["stages"][selected] if isinstance(selected, int) else None
            steps = stage is not None and stage.get("steps") and not stage.get("checking")
            list_width = min(max(22, max(len(row[1]) for row in rows if row) + 6), width // 3)
            top, left, lines, columns = ui._panel(screen, 3, 1, height - 6, list_width, "Plan")
            at = [index for index, row in enumerate(rows) if row is not None and row[0] == selected][0]
            first = max(0, at - lines + 1)
            for row_index, row in enumerate(rows[first:first + lines]):
                if row is None:
                    continue
                key, label, role = row
                ui._line(screen, top + row_index, left, (("> " if key == selected else "  ") + label)[:columns],
                         key == selected, ui.styles.get(role, 0) if role else 0)
            right = ui._panel(screen, 3, list_width, height - 6, width - list_width - 1, _title(view, selected))
            if stage is not None and stage.get("checking"):
                ui._line(screen, right[0], right[1], CHECKING[:right[3]], color=ui.styles["accent"])
                draw_loading(ui, screen, (right[0] + 1, right[1], right[2] - 1, right[3]))
            else:
                content = _details(ui, view, selected, right[3], full)
                offset, page = ui._viewport(screen, right, [text for text, _ in content], offset,
                                            line_colors=[role for _, role in content])
            can_start = selected == "start" and not view.get("errors") and not checking
            ui._footer(screen, "Up/Down Select | " + ("Enter Start | " if can_start else "") + "E Edit | " +
                       (("F Short commands | " if full else "F Full commands | ") if steps else "") +
                       "PgUp/Dn Details | Esc Back")
            screen.refresh()
            key = screen.getch()
            if checking and update:
                done = update()
                if done is not None:  # the whole plan: in place, the caller keeps it
                    view.clear()
                    view.update(done)
            if key in (27, 3):
                return "back"
            if key in (ord("e"), ord("E")):
                return "edit"
            if key in (ui.curses.KEY_UP, ui.curses.KEY_DOWN):
                step = 1 if key == ui.curses.KEY_DOWN else -1
                selected, offset = keys[(keys.index(selected) + step) % len(keys)], 0
            elif key == ui.curses.KEY_NPAGE:
                offset += page
            elif key == ui.curses.KEY_PPAGE:
                offset = max(0, offset - page)
            elif key in (ord("f"), ord("F")) and steps:
                full, offset = not full, 0
            elif key in (10, 13, ui.curses.KEY_ENTER) and can_start:
                return "start"
    except KeyboardInterrupt:
        return "back"
    finally:
        position.update(selected=selected, offset=offset, full=full)
