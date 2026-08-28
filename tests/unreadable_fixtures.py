"""Shared test data: two repositories whose files cannot all be read.

The first is one readable file plus one file per parse failure, so a test can
assert both halves of the guarantee at once — the readable file's surfaces
survive, and every unreadable file is named in the artifact rather than only on
stderr. The second exists to test the *order* skips come out in.
"""

from pathlib import Path

from artifacts.skipped_file import TOO_LARGE, UNDECODABLE_BYTES, UNPARSEABLE_SYNTAX
from parsing.repo_loader import MAX_FILE_BYTES

GOOD_FILE = "good.py"
GOOD_SURFACE_NAME = "system_prompt"
GOOD_SOURCE = f'{GOOD_SURFACE_NAME} = "be helpful"\n'

BROKEN_PYTHON_FILE = "bad.py"
BROKEN_PYTHON_SOURCE = "def oops(:\n"

BROKEN_TYPESCRIPT_FILE = "bad.ts"
BROKEN_TYPESCRIPT_SOURCE = "function oops( {\n"

# Bytes that are not valid UTF-8, in a file declaring no PEP 263 encoding
# cookie: the stdlib assumes UTF-8 and cannot read them.
UNDECODABLE_FILE = "nocookie.py"
UNDECODABLE_BYTES_SOURCE = b'x = "\xff\xfe"\n'

# A cookie that declares an encoding the bytes above still do not honour.
UTF8_COOKIE = b"# -*- coding: utf-8 -*-\n"

# What write_unreadable_repo must produce: (file, reason, line).
# bad.ts carries no line because tree-sitter reports none.
EXPECTED_SKIPS = {
    (BROKEN_PYTHON_FILE, UNPARSEABLE_SYNTAX, 1),
    (BROKEN_TYPESCRIPT_FILE, UNPARSEABLE_SYNTAX, None),
    (UNDECODABLE_FILE, UNDECODABLE_BYTES, None),
}


def write_unreadable_repo(root: Path) -> str:
    """Write one readable file and three unreadable ones, and return the repo path."""
    (root / GOOD_FILE).write_text(GOOD_SOURCE, encoding="utf-8")
    (root / BROKEN_PYTHON_FILE).write_text(BROKEN_PYTHON_SOURCE, encoding="utf-8")
    (root / BROKEN_TYPESCRIPT_FILE).write_text(BROKEN_TYPESCRIPT_SOURCE, encoding="utf-8")
    (root / UNDECODABLE_FILE).write_bytes(UNDECODABLE_BYTES_SOURCE)
    return str(root)


# --- A second repository, for skip *ordering* ------------------------------
# Oversized files are collected before the walk, so an oversized name that
# sorts after an unparseable one is the pair an unsorted skip list gets wrong.
OVERSIZED_FILE = "generated.py"
OVERSIZED_SOURCE = "# " + "a" * MAX_FILE_BYTES

# What write_mixed_skip_repo must produce, in the order it must come out in.
EXPECTED_ORDERED_SKIPS = [
    (BROKEN_PYTHON_FILE, UNPARSEABLE_SYNTAX),
    (OVERSIZED_FILE, TOO_LARGE),
]


def write_mixed_skip_repo(root: Path) -> str:
    """Write one unparseable file and one oversized file, and return the repo path."""
    (root / BROKEN_PYTHON_FILE).write_text(BROKEN_PYTHON_SOURCE, encoding="utf-8")
    (root / OVERSIZED_FILE).write_text(OVERSIZED_SOURCE, encoding="utf-8")
    return str(root)
