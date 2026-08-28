"""The two limits of the skip list, pinned as they behave rather than as they should end up.

Both are recorded as known and deliberate in `docs/SCHEMAS.md`: a non-UTF-8
TypeScript file is skipped or not depending on where the bad bytes sit, and a
file the process cannot open still stops the whole scan. These tests exist so
changing either is a conscious decision with a failing test attached, not an
accident.
"""

import os

import pytest
from parsing.extractor import extract_repo
from artifacts.skipped_file import UNPARSEABLE_SYNTAX
from artifacts.surface import PROMPT_TEMPLATE
from unreadable_fixtures import GOOD_FILE, GOOD_SOURCE

# 0xE9 is a lone continuation-free byte: 'é' in Latin-1, invalid UTF-8 alone.
# Inside a chat message's role it reaches a surface name, which is where the
# replacement character shows up. In an identifier the grammar errors instead,
# so this is the placement that demonstrates the asymmetry.
MANGLED_TYPESCRIPT_FILE = "messages.ts"
MANGLED_TYPESCRIPT_SOURCE = b'const turn = { role: "syst\xe9m", content: "be helpful" };\n'
# Written as an escape, not the character itself: U+FFFD is invisible in most
# editors, and this is the whole point of the test.
MANGLED_SURFACE_NAME = "syst\ufffdm_message"

# The same byte moved into an identifier: the grammar has no rule for it, so
# tree-sitter errors and the file is skipped instead of quietly renamed.
IDENTIFIER_TYPESCRIPT_FILE = "ident.ts"
IDENTIFIER_TYPESCRIPT_SOURCE = b'const syst\xe9m = "be helpful";\n'

# A file whose permissions deny every read, including the owner's.
UNREADABLE_FILE = "locked.py"
NO_PERMISSIONS = 0o000


def test_undecodable_typescript_yields_a_mangled_name_and_no_skip(tmp_path) -> None:
    """Known asymmetry, not the goal: tree-sitter replaces bad bytes, so nothing is skipped."""
    (tmp_path / MANGLED_TYPESCRIPT_FILE).write_bytes(MANGLED_TYPESCRIPT_SOURCE)
    scan = extract_repo(str(tmp_path))
    assert [(s.kind, s.name, s.file) for s in scan.surfaces] == [
        (PROMPT_TEMPLATE, MANGLED_SURFACE_NAME, MANGLED_TYPESCRIPT_FILE)
    ]
    assert scan.skipped == []


def test_undecodable_bytes_in_a_typescript_identifier_are_skipped(tmp_path) -> None:
    """The other half of the same limit: in an identifier the bad byte is a syntax error."""
    (tmp_path / IDENTIFIER_TYPESCRIPT_FILE).write_bytes(IDENTIFIER_TYPESCRIPT_SOURCE)
    scan = extract_repo(str(tmp_path))
    assert [(s.file, s.reason, s.line) for s in scan.skipped] == [
        (IDENTIFIER_TYPESCRIPT_FILE, UNPARSEABLE_SYNTAX, None)
    ]
    assert scan.surfaces == []


def test_an_unopenable_file_aborts_the_whole_scan(tmp_path) -> None:
    """Known limit, not the goal: a permission error is no skip reason, so it stops everything."""
    (tmp_path / GOOD_FILE).write_text(GOOD_SOURCE, encoding="utf-8")
    locked = tmp_path / UNREADABLE_FILE
    locked.write_text(GOOD_SOURCE, encoding="utf-8")
    locked.chmod(NO_PERMISSIONS)
    if os.access(locked, os.R_OK):
        pytest.skip("chmod 000 did not deny reads here (running as root, or on this filesystem)")
    with pytest.raises(PermissionError):
        extract_repo(str(tmp_path))
