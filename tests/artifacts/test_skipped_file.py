"""The SkippedFile data model: validation, ordering, and the backend's exception."""

import pytest
from artifacts.skipped_file import (
    SKIP_REASONS,
    TOO_LARGE,
    UNDECODABLE_BYTES,
    UNPARSEABLE_SYNTAX,
    SkippedFile,
    UnreadableSource,
    sort_key,
)

# The reason strings a later phase reads out of surfaces.json.
EXPECTED_REASONS = {"unparseable_syntax", "undecodable_bytes", "too_large"}


def test_declared_reasons_are_the_documented_strings() -> None:
    """The reason vocabulary is part of the artifact, so its wording is pinned here."""
    assert set(SKIP_REASONS) == EXPECTED_REASONS


def test_valid_record_keeps_its_fields() -> None:
    """A record carries the file, the reason, and the line the parser gave up on."""
    skipped = SkippedFile("app/bad.py", UNPARSEABLE_SYNTAX, 12)
    assert (skipped.file, skipped.reason, skipped.line) == ("app/bad.py", UNPARSEABLE_SYNTAX, 12)


@pytest.mark.parametrize("reason", SKIP_REASONS)
def test_every_declared_reason_is_accepted(reason: str) -> None:
    """Each of the three reasons the walk can record builds a valid record."""
    assert SkippedFile("app/bad.py", reason).reason == reason


def test_unknown_reason_is_rejected() -> None:
    """A reason outside the declared vocabulary fails loudly."""
    with pytest.raises(ValueError, match="unknown skip reason"):
        SkippedFile("app/bad.py", "vibes")


def test_empty_file_is_rejected() -> None:
    """A record with no file names nothing, so it is rejected."""
    with pytest.raises(ValueError, match="must not be empty"):
        SkippedFile("", UNPARSEABLE_SYNTAX)


@pytest.mark.parametrize("bad_file", ["/abs/bad.py", "app\\bad.py"])
def test_non_repo_relative_file_is_rejected(bad_file: str) -> None:
    """Absolute and Windows-style paths are rejected so output stays machine-independent."""
    with pytest.raises(ValueError, match="repo-relative posix path"):
        SkippedFile(bad_file, UNPARSEABLE_SYNTAX)


def test_line_below_one_is_rejected() -> None:
    """Line numbers are 1-indexed, so 0 is invalid."""
    with pytest.raises(ValueError, match="line must be 1 or greater"):
        SkippedFile("app/bad.py", UNPARSEABLE_SYNTAX, 0)


def test_missing_line_is_allowed() -> None:
    """A parser that reports no line still produces a usable record."""
    assert SkippedFile("app/bad.ts", UNPARSEABLE_SYNTAX).line is None


def test_records_sort_by_file_then_reason() -> None:
    """Ordering is by file then reason, so the same repository always serialises the same."""
    records = [
        SkippedFile("b.py", TOO_LARGE),
        SkippedFile("a.py", UNPARSEABLE_SYNTAX),
        SkippedFile("a.py", TOO_LARGE),
    ]
    ordered = [(r.file, r.reason) for r in sorted(records, key=sort_key)]
    assert ordered == [("a.py", TOO_LARGE), ("a.py", UNPARSEABLE_SYNTAX), ("b.py", TOO_LARGE)]


def test_sort_key_ignores_the_line() -> None:
    """`line` is descriptive only, so it takes no part in the ordering."""
    assert sort_key(SkippedFile("a.py", UNPARSEABLE_SYNTAX, 9)) == ("a.py", UNPARSEABLE_SYNTAX)


def test_unreadable_source_carries_its_reason_and_line() -> None:
    """The backend hands the walk the reason, so the walk never parses a message."""
    error = UnreadableSource("cannot parse bad.py", UNPARSEABLE_SYNTAX, 4)
    assert (error.reason, error.line) == (UNPARSEABLE_SYNTAX, 4)


def test_unreadable_source_rejects_an_unknown_reason() -> None:
    """A backend cannot invent a reason a later phase would not recognise."""
    with pytest.raises(ValueError, match="unknown skip reason"):
        UnreadableSource("cannot parse bad.py", "vibes")


@pytest.mark.parametrize("reported", [0, -1, None])
def test_unreadable_source_normalises_a_useless_line(reported: int | None) -> None:
    """A parser reporting no usable line must not abort the scan: the line becomes None."""
    assert UnreadableSource("cannot parse bad.ts", UNDECODABLE_BYTES, reported).line is None


def test_unreadable_source_is_not_a_value_error() -> None:
    """A deliberate skip must stay distinguishable from a detector's own ValueError."""
    assert not issubclass(UnreadableSource, ValueError)
