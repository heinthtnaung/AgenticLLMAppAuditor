"""One unreadable file must cost its own surfaces only, and be recorded in the artifact.

A file that cannot be parsed used to abort the whole walk, losing every surface
from every other file. Recording it in surfaces.json rather than only on stderr
is what lets a later phase tell a skipped file from a detector that missed.
"""

import ast
import json
import os
import tokenize

import pytest
from conftest import scan_to_json
from parsing import extractor_python
from parsing.extractor import extract_repo
from parsing.extractor_python import read_source
from artifacts.surface import Surface
from artifacts.skipped_file import (
    TOO_LARGE,
    UNDECODABLE_BYTES,
    UNPARSEABLE_SYNTAX,
    UnreadableSource,
    sort_key,
)
from unreadable_fixtures import (
    BROKEN_PYTHON_FILE,
    BROKEN_PYTHON_SOURCE,
    BROKEN_TYPESCRIPT_FILE,
    BROKEN_TYPESCRIPT_SOURCE,
    EXPECTED_ORDERED_SKIPS,
    EXPECTED_SKIPS,
    GOOD_FILE,
    GOOD_SOURCE,
    GOOD_SURFACE_NAME,
    OVERSIZED_FILE,
    OVERSIZED_SOURCE,
    UNDECODABLE_BYTES_SOURCE,
    UNDECODABLE_FILE,
    UTF8_COOKIE,
    write_mixed_skip_repo,
    write_unreadable_repo,
)

# Undecodable bytes behind an encoding declaration that promises otherwise.
COOKIE_FILE = "cookie.py"

# A colon is legal in a POSIX filename, and looks like a Windows drive letter.
COLON_FILE = "notes:draft.py"
COLON_SURFACE_NAME = "draft_prompt"
COLON_SOURCE = f'{COLON_SURFACE_NAME} = "be helpful"\n'


def test_walk_continues_past_an_unreadable_file(tmp_path) -> None:
    """One unparseable file costs its own surfaces, never the whole scan's."""
    scan = extract_repo(write_unreadable_repo(tmp_path))
    assert [(s.file, s.name) for s in scan.surfaces] == [(GOOD_FILE, GOOD_SURFACE_NAME)]


def test_walk_records_every_unreadable_file(tmp_path) -> None:
    """Each unreadable file is recorded with its reason and the line the parser reached."""
    scan = extract_repo(write_unreadable_repo(tmp_path))
    assert {(s.file, s.reason, s.line) for s in scan.skipped} == EXPECTED_SKIPS


def test_broken_python_is_recorded_with_its_line(tmp_path) -> None:
    """A Python file with invalid syntax is unparseable_syntax at the line ast reported."""
    (tmp_path / BROKEN_PYTHON_FILE).write_text(BROKEN_PYTHON_SOURCE, encoding="utf-8")
    skipped = extract_repo(str(tmp_path)).skipped
    assert [(s.file, s.reason, s.line) for s in skipped] == [
        (BROKEN_PYTHON_FILE, UNPARSEABLE_SYNTAX, 1)
    ]


def test_broken_typescript_is_recorded_without_a_line(tmp_path) -> None:
    """tree-sitter reports no usable line, so the record carries the file and reason only."""
    (tmp_path / BROKEN_TYPESCRIPT_FILE).write_text(BROKEN_TYPESCRIPT_SOURCE, encoding="utf-8")
    skipped = extract_repo(str(tmp_path)).skipped
    assert [(s.file, s.reason, s.line) for s in skipped] == [
        (BROKEN_TYPESCRIPT_FILE, UNPARSEABLE_SYNTAX, None)
    ]


def test_undecodable_file_is_recorded_as_undecodable(tmp_path) -> None:
    """Bytes that are not text in the declared encoding are undecodable_bytes."""
    (tmp_path / UNDECODABLE_FILE).write_bytes(UNDECODABLE_BYTES_SOURCE)
    skipped = extract_repo(str(tmp_path)).skipped
    assert [(s.file, s.reason) for s in skipped] == [(UNDECODABLE_FILE, UNDECODABLE_BYTES)]


def test_oversized_file_is_recorded_as_too_large(tmp_path) -> None:
    """A file above MAX_FILE_BYTES joins the same skip list as a parse failure."""
    (tmp_path / OVERSIZED_FILE).write_text(OVERSIZED_SOURCE, encoding="utf-8")
    skipped = extract_repo(str(tmp_path)).skipped
    assert [(s.file, s.reason, s.line) for s in skipped] == [(OVERSIZED_FILE, TOO_LARGE, None)]


def test_skips_come_out_sorted_by_file_and_reason(tmp_path) -> None:
    """Oversized files are collected before the walk, so the list is sorted, not just appended."""
    skipped = extract_repo(write_mixed_skip_repo(tmp_path)).skipped
    assert [(s.file, s.reason) for s in skipped] == EXPECTED_ORDERED_SKIPS
    assert skipped == sorted(skipped, key=sort_key)


def test_the_artifact_records_skips_in_the_order_the_scan_returned(tmp_path) -> None:
    """Sorting at the walk, not only in the serialiser, keeps warnings and records in step."""
    repo = write_mixed_skip_repo(tmp_path)
    returned = [(s.file, s.reason) for s in extract_repo(repo).skipped]
    document = json.loads(scan_to_json(repo))
    assert [(r["file"], r["reason"]) for r in document["skipped_files"]] == returned


def test_a_readable_repository_records_no_skips(tmp_path) -> None:
    """A clean scan reports an empty skip list, so it cannot be read as a partial one."""
    (tmp_path / GOOD_FILE).write_text(GOOD_SOURCE, encoding="utf-8")
    assert extract_repo(str(tmp_path)).skipped == []


def test_undecodable_bytes_without_a_cookie_raise_syntax_error(tmp_path) -> None:
    """The stdlib reports a missing encoding as SyntaxError, naming the absolute path."""
    source = tmp_path / UNDECODABLE_FILE
    source.write_bytes(UNDECODABLE_BYTES_SOURCE)
    with pytest.raises(SyntaxError) as raised:
        with tokenize.open(source) as handle:
            handle.read()
    assert str(tmp_path) in raised.value.msg


def test_undecodable_bytes_with_a_cookie_raise_unicode_decode_error(tmp_path) -> None:
    """A declared utf-8 encoding fails later, as UnicodeDecodeError: a different exception type."""
    source = tmp_path / COOKIE_FILE
    source.write_bytes(UTF8_COOKIE + UNDECODABLE_BYTES_SOURCE)
    with pytest.raises(UnicodeDecodeError):
        with tokenize.open(source) as handle:
            handle.read()


@pytest.mark.parametrize("cookie", [b"", UTF8_COOKIE])
def test_read_source_reports_both_decode_failures_the_same_way(tmp_path, cookie: bytes) -> None:
    """Two different stdlib exceptions map to one reason, because the raise site sets it."""
    source = tmp_path / UNDECODABLE_FILE
    source.write_bytes(cookie + UNDECODABLE_BYTES_SOURCE)
    with pytest.raises(UnreadableSource) as raised:
        read_source(source)
    assert raised.value.reason == UNDECODABLE_BYTES


def test_skip_records_carry_no_absolute_path(tmp_path) -> None:
    """SyntaxError.msg can hold an absolute path, so the artifact stores the reason instead."""
    document = json.loads(scan_to_json(write_unreadable_repo(tmp_path)))
    assert str(tmp_path) not in json.dumps(document)
    assert [r for r in document["skipped_files"] if r["file"].startswith("/")] == []


def test_a_detector_value_error_still_escapes(tmp_path, monkeypatch) -> None:
    """UnicodeDecodeError is a ValueError, so the walk must catch neither: a bug stays loud."""
    def raise_value_error(tree: ast.AST, file_label: str) -> list[Surface]:
        """Stand in for a detector with a bug in it."""
        raise ValueError("detector bug")

    monkeypatch.setattr(extractor_python, "DETECTORS", (raise_value_error,))
    (tmp_path / GOOD_FILE).write_text(GOOD_SOURCE, encoding="utf-8")
    with pytest.raises(ValueError, match="detector bug"):
        extract_repo(str(tmp_path))


@pytest.mark.skipif(os.name == "nt", reason="Windows filenames cannot contain a colon")
def test_a_colon_in_a_filename_does_not_abort_the_scan(tmp_path) -> None:
    """A readable file whose name holds a colon costs no surfaces, its own or any other's.

    The path rule once treated any colon in the first segment as a drive
    letter, so `Surface` raised out of `extract_repo` and the scan lost
    `good.py` along with it. Both files' surfaces are expected, and no skip.
    """
    (tmp_path / GOOD_FILE).write_text(GOOD_SOURCE, encoding="utf-8")
    (tmp_path / COLON_FILE).write_text(COLON_SOURCE, encoding="utf-8")
    scan = extract_repo(str(tmp_path))
    assert [(s.file, s.name) for s in scan.surfaces] == [
        (GOOD_FILE, GOOD_SURFACE_NAME),
        (COLON_FILE, COLON_SURFACE_NAME),
    ]
    assert scan.skipped == []
