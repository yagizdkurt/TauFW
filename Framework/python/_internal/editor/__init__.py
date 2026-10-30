# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""A self-contained terminal file editor, independent of Menu and Framework.

    result = edit_file(screen, path, validate=check_draft)

The caller owns the curses session. validate(draft_path), if supplied, checks a
temporary file before it replaces the destination: return problem strings (or
None), or raise an exception to reject the save. The editor preserves the text,
including comments. It imports curses only when opened and uses no TauFW APIs.

F2 saves; Esc leaves, asking first about unsaved changes. Result.saved means at
least one save succeeded, even if later edits were discarded. Result.error is
set if the editor could not open or had to close because of an unexpected error.
"""
from dataclasses import dataclass
from typing import Optional

__all__ = ["EditResult", "edit_file"]


@dataclass(frozen=True)
class EditResult:
    saved: bool = False
    error: Optional[str] = None


def edit_file(screen, path, *, validate=None, title="Text editor", appearance=None, reference=None, curses_module=None,
              follow_size=False):
    """Edit an existing UTF-8 file on an existing curses screen; always return EditResult.

    Expected save failures stay on the editor screen so the buffer can be fixed
    or copied. Other ordinary exceptions become result.error after terminal
    cleanup. appearance optionally supplies banner lines, highlight spans and
    preallocated curses styles; the editor never imports its caller's UI.
    reference optionally names a read-only Markdown or text file beside the
    editor. F5 switches panes; F4 shows/hides it. A missing reference is shown
    as a message in that pane and never prevents editing or saving.
    curses_module is optional dependency injection for terminal tests.
    follow_size: the size is asked from the terminal at each key, as the menu does (a library such as ROOT can
    take the resize signal from curses); False for terminal tests.
    This is an exception boundary, not isolation from hangs or process crashes.
    """
    editor = None
    try:
        from ._file import Document
        from ._screen import Editor
        if curses_module is None:
            import curses as curses_module
        editor = Editor(screen, curses_module, Document(path), title, validate, appearance, reference,
                        follow_size=follow_size)
        editor.run()
        return EditResult(saved=editor.saved)
    except KeyboardInterrupt:
        return EditResult(saved=editor.saved if editor else False)
    except Exception as error:
        return EditResult(saved=editor.saved if editor else False,
                          error="%s: %s" % (type(error).__name__, error))
