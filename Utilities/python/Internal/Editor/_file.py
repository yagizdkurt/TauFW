# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Local UTF-8 files: preserve formatting, validate a draft, then replace atomically."""
import os
from pathlib import Path
import stat
import tempfile


class Document:
    def __init__(self, path):
        # Follow a symlink once: saving must replace its target, not the link.
        self.path = Path(path).resolve(strict=True)
        status = self.path.stat()
        if not stat.S_ISREG(status.st_mode):
            raise ValueError("Not a regular file: %s" % self.path)
        self.original = self.path.read_bytes()
        self.mode = stat.S_IMODE(status.st_mode)
        self.bom = self.original.startswith(b"\xef\xbb\xbf")
        text = self.original.decode("utf-8-sig")
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.text = text.replace("\r\n", "\n")

    def _unchanged(self):
        if self.path.read_bytes() != self.original:
            raise OSError("The file changed outside the editor. Your edits are still here; "
                          "leave and reopen the file before saving: %s" % self.path)

    def save(self, text, validate=None):
        """A failed write or validation leaves the destination and last saved text alone.

        Validation receives the draft's path. It must only read that file.
        Checking the original again after validation catches edits made while
        the validator ran; this is conflict detection, not a filesystem lock.
        """
        self._unchanged()
        data = text.replace("\n", self.newline).encode("utf-8")
        if self.bom:
            data = b"\xef\xbb\xbf" + data
        descriptor, name = tempfile.mkstemp(prefix="." + self.path.name + ".", suffix=".tmp",
                                            dir=str(self.path.parent))
        draft = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if validate is not None:
                problems = validate(draft)
                if problems is not None and not isinstance(problems, str):
                    problems = "\n".join(problems)
                if problems:
                    raise ValueError(problems)
            self._unchanged()
            os.chmod(draft, self.mode)
            os.replace(str(draft), str(self.path))
            self.original, self.text = data, text
        except Exception as error:
            # Validators often include the input filename in their messages.
            raise OSError(str(error).replace(str(draft), str(self.path))) from error
        finally:
            draft.unlink(missing_ok=True)
