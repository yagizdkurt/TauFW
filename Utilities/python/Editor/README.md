# Terminal editor

`Editor` edits an existing local UTF-8 file on a caller-owned curses screen.
It depends only on the Python standard library, imports curses on demand, and
does not import Menu, Framework, UserConfig, ROOT or CMSSW.

```python
from TauFW.Utilities.Editor import edit_file

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

`EditResult.saved` means that at least one save succeeded during the session.
`EditResult.error` describes an opening or unexpected editor failure. Ordinary
save errors stay inside the editor without dropping the buffer. Cancelling or
leaving an unchanged document returns `saved=False, error=None`.

The editor owns a separate window inside the existing curses session, restores
cursor visibility, and does not change session modes, global colors, the working
directory or environment. The menu imports it only when the action is selected
and catches failures at that boundary. This contains ordinary Python exceptions;
the shared process and terminal still preclude isolation from hangs or crashes.

Saves preserve comments, UTF-8 BOM and the document's LF or CRLF line convention.
The editor writes and flushes a temporary file, runs validation, checks for an
external change, copies permission bits, then replaces the destination. It follows
an existing symlink and updates its target. External-change detection compares
contents; it is not a lock against concurrent writers. Mixed LF/CRLF files are
normalized to CRLF when changed and saved. Failed saves remove the temporary file.
