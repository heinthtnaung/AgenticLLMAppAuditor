"""The path rule every artifact path field obeys, defined once.

Artifacts have to be machine-independent, so a path in one is always
repo-relative with forward slashes. Two copies of this rule is how the two
copies come to disagree, so both artifact records import it from here.
"""

import re

# A Windows drive letter: one ASCII letter then a colon, as in `C:/src/app.py`.
# Matched precisely rather than by looking for any colon, because a colon is a
# legal character in a POSIX filename and rejecting `notes:draft.py` would
# abort a scan over a file the auditor could have read.
DRIVE_LETTER = re.compile(r"^[A-Za-z]:")


def is_repo_relative_posix(file: str) -> bool:
    """Say whether a path is repo-relative POSIX, so output is machine-independent."""
    if file.startswith("/") or "\\" in file:
        return False
    return DRIVE_LETTER.match(file) is None
