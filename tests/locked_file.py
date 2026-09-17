"""One file this process cannot open, for the tests that read a hand-editable file.

The third way a hand-edited file goes wrong, after "not json" and "json of the
wrong shape": nobody can open it. `chmod 000` is the reachable cause -- a person
tightening permissions on a folder of keys, or a file restored from an archive
that did not carry its mode.

It matters because `OSError` is neither a `ValueError` nor a
`json.JSONDecodeError`, so a reader that caught only the parse error let it past
as a traceback. Two modules did, one of them written to fix that very fault.

**It can only be tested where the read really is denied.** `chmod 000` does not
deny the owner when the owner is root, and some filesystems ignore the mode
entirely, so `locked` *attempts the read* and skips when it succeeds. A test
that passed here by reading the file fine would be worse than no test.

The other `OSError` a hand could leave -- a directory where the file should be
-- reaches neither guard: `key_draft_store.read` and `fetch_repo._pin_for` both
test `is_file()` first, so it is a 404 and a "nothing pins this tree", not a
read failure. That is why the mode is the case tested.

`tests/parsing/test_extractor_skip_limits.py` locks a file the same way for a
different claim: that a locked *source* file aborts a scan, which is a limit the
extractor has rather than a guard it keeps.
"""

from pathlib import Path

import pytest

# Every permission bit off. Named because `0o000` in a test reads as a typo.
NO_PERMISSIONS = 0o000

SKIPPED_BECAUSE_READABLE = ("chmod 000 did not deny this process a read "
                            "(running as root, or on a filesystem that ignores the mode)")


def locked(path: Path) -> Path:
    """Take every permission off one file, proving the read really fails before going on."""
    path.chmod(NO_PERMISSIONS)
    try:
        path.read_text(encoding="utf-8")
    except OSError:
        return path
    pytest.skip(SKIPPED_BECAUSE_READABLE)
