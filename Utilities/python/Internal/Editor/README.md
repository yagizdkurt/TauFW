# Terminal editor

`Editor` edits an existing local UTF-8 file on a caller-owned curses screen.
It depends only on the Python standard library, imports curses on demand, and
does not import Menu, Framework, UserConfig, ROOT or CMSSW.

```python
from TauFW.Utilities.Internal.Editor import edit_file

result = edit_file(screen, path, title="Settings", validate=check_draft)
```

`check_draft(path)` receives a temporary file beside the destination. It must
only read it. Return an iterable of problem strings, a single problem string,
or `None`; an exception also rejects the save. Application-specific rules stay
with the caller. The user config adapter reuses `UserConfig.load()` and
`manage.setting_problems()` without copying their rules into Editor.

F2 saves. Esc, F10 and Ctrl-C leave, asking about unsaved edits first. In that
question, F2 saves and leaves, D discards unsaved changes, and Esc keeps editing.
Arrow keys, Home/End, Page Up/Page Down, Backspace and Delete edit the document.
Tab inserts spaces up to the next two-column tab stop. Enter inserts a newline
without automatic indentation, so multiline terminal pastes retain their indentation.

## Read-only reference pane

Pass `reference=path_to_readme` to show a Markdown or text file alongside any
edited file. The caller chooses both paths and the title; Editor has no knowledge
of the user config or the repository layout. The menu's user config action passes
`Docs/Guide/1-GettingStarted/UserConfig.md` from its own checkout, including when
`TAUFW_USER_CONFIG` points outside that checkout.

```python
result = edit_file(screen, "settings.yaml", title="Settings",
                   validate=check_draft, reference="README.md")
```

At 110 columns or more, the editor uses about 60% of the width and the reference
uses the rest. Below that, the editor opens alone and the reference takes the
body's full width when selected. The existing minimum remains 40 x 10.

- F5 switches focus; on a narrow terminal it switches the visible pane too.
- F4 hides the reference or opens it with focus. Hiding returns to editing.
- Up/Down and Page Up/Down move within the focused pane, independently.
- In the reference, Left/Right scroll long code lines horizontally, Home goes
  to the start and End goes to the last page. Typing, Tab and deletion are ignored.
- Tab still indents in the editor. F2 saves the edited file from either pane;
  Esc/F10/Ctrl-C leave with the usual unsaved-changes question.

The focused pane's title has a `>` marker and its border is highlighted when
colors are available. The edit cursor, reference position and hidden-pane choice
survive toggling and resizing. Reflow keeps the reference near the same source
location. Save errors and confirmation panels take priority over pane controls.

Markdown presentation supports headings, soft-wrapped paragraphs, lists, inline
code/emphasis, links shown with their targets, fenced code and pipe tables.
Tables are shown as labelled fields to fit a narrow pane. Fenced code and plain
text retain indentation and use horizontal scrolling. Other Markdown constructs
remain source text; this is a terminal reader, not a full Markdown/browser engine.
The file is read once when opened. An unavailable or invalid UTF-8 reference shows
an error inside its pane without preventing editing or saving the main file.
`_reference.py` owns reading, formatting and viewport position without importing
curses; `_screen.py` owns layout, focus and key routing. No new dependencies.

`EditResult.saved` means that at least one save succeeded during the session.
`EditResult.error` describes an opening or unexpected editor failure. Ordinary
save errors stay inside the editor without dropping the buffer. Cancelling or
leaving an unchanged document returns `saved=False, error=None`.

The editor owns a separate window inside the existing curses session, restores
cursor visibility, and does not change session modes, global colors, the working
directory or environment. The menu imports it only when the action is selected
and catches failures at that boundary. This contains ordinary Python exceptions;
the shared process and terminal still preclude isolation from hangs or crashes.

The file sits inside an ASCII frame, with a marked active line, line numbers,
cursor position, visible line range and save state. Save errors and the unsaved
changes question appear in panels over the document. Long paths are shortened
from the left so the filename stays visible. The minimum terminal is 40 x 10.

The optional `appearance` dictionary supplies caller-owned presentation data:

- `styles`: role-to-curses-attribute mapping (`accent`, `muted`, `active`, `good`,
  `warning`, `error`, plus any banner highlight roles).
- `banner`: a sequence of strings. A banner of up to three rows sits beside the
  title and path; a taller one puts those below it.
- `banner_spans`: `(row, column, text, role)` highlights relative to that banner.
- `large_banner` and `large_banner_spans`: an optional larger variant, used only
  if it fits horizontally and leaves at least 16 rows of editable text.

The TauFW menu always passes its existing three-row badge and initialized color
attributes, including on tall terminals. A standard 80 x 24 terminal shows 16
rows of text; larger terminals give the extra space to the document. Resizing
does not reset the buffer or cursor. Editor never allocates color pairs or changes global colors;
without appearance data it uses a plain title and monochrome frame. With colors
disabled, state labels and the active-line marker still carry the same information.

Saves preserve comments, UTF-8 BOM and the document's LF or CRLF line convention.
The editor writes and flushes a temporary file, runs validation, checks for an
external change, copies permission bits, then replaces the destination. It follows
an existing symlink and updates its target. External-change detection compares
contents; it is not a lock against concurrent writers. Mixed LF/CRLF files are
normalized to CRLF when changed and saved. Failed saves remove the temporary file.
