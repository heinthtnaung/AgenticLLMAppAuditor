"""Refusing a grading key the scorer would misread, and saying which field is wrong.

A grading key is **hand-placed input** since the pinned corpus was removed:
somebody writes `grading_keys/<app>.ground_truth.json` by hand and the scorer
reads its fields directly. So the shape is checked at the I/O edge instead of
trusted. Without this a key missing one field raises a bare `KeyError` from
inside `scorer.py`, which tells whoever wrote the key nothing about the file
they need to fix.

Split three ways, one job each. `test_harness.py` is about the artifacts a
score is loaded from and `test_artifact_check.py` about their shape;
`test_key_entry_check.py` is about each entry inside this key's `findings`,
which is the likelier hand-editing mistake and so has a file of its own. What
is here is the shape of the key as a whole, and it needs no filesystem at all:
`_check_key` is pure, so every case here is a dict.

`_check_key` is private and tested directly on purpose: each message below is
read by a person editing a JSON file, so the message is the behaviour.

The list is checked in both directions. That every listed field is required is
one half; that every field the scorer really reads is on the list is the other,
and it is read off `scorer.py`'s source at the bottom of this file -- a field
added there and not here would reach the scorer unvalidated and raise exactly
the bare `KeyError` this check exists to prevent.

Limit of that second half: it matches subscripts written on the name `key`, so
a helper that took the same dict under another parameter name, or reached a
field through `.get()`, would not be seen. Every function in `scorer.py` that
takes a key today calls it `key`.
"""

from pathlib import Path

import pytest

from ast_scan import parse, subscript_keys
from conftest import SRC_DIR
from evaluation.harness import KEY_FIELDS, KEY_SCHEMA_VERSION, _check_key
from evaluation_fixtures import grading_key, key_entry

# A schema the scorer does not read, so a key written for an older shape is refused.
WRONG_SCHEMA_VERSION = KEY_SCHEMA_VERSION - 1

# Stands in for the path the key was read from; nothing here opens it.
KEY_FILE = Path("grading_keys/an-app.ground_truth.json")

# The module that reads a key, and the name it reads it through: `key["source"]`
# is a key field, `entry["file"]` is a field of one finding inside it.
SCORER_SOURCE = SRC_DIR / "evaluation" / "scorer.py"
KEY_VARIABLE = "key"

# A read of a field no key has, planted to prove the scan really looks.
PLANTED_FIELD = "invented_key_field"
PLANTED_SOURCE = f'def read(key):\n    return key["{PLANTED_FIELD}"]\n'


def test_a_complete_key_passes_the_check() -> None:
    """Guard for the refusals below: the fixture key really is accepted."""
    key = grading_key([key_entry()])
    assert _check_key(key, KEY_FILE) is key


def test_a_key_with_no_findings_at_all_still_passes() -> None:
    """An app asserted clean has an empty list, which is a claim and not an omission."""
    key = grading_key([])
    assert _check_key(key, KEY_FILE) is key


def test_every_field_the_scorer_reads_is_required() -> None:
    """One key per field, each missing exactly that field, so none of them is optional."""
    for field in KEY_FIELDS:
        key = grading_key([key_entry()])
        del key[field]
        with pytest.raises(ValueError, match=field):
            _check_key(key, KEY_FILE)


def test_the_field_list_is_not_empty() -> None:
    """Guard: an empty `KEY_FIELDS` would make the loop above assert nothing."""
    assert len(KEY_FIELDS) > 5


def test_two_missing_fields_are_both_named() -> None:
    """Naming one at a time would send the reader round the loop twice."""
    key = grading_key([key_entry()])
    del key["verified"], key["verified_by"]
    with pytest.raises(ValueError) as raised:
        _check_key(key, KEY_FILE)
    assert "verified" in str(raised.value) and "verified_by" in str(raised.value)


def test_the_missing_field_message_names_the_file_and_the_schema() -> None:
    """The reader has to find the file, and then find out what belongs in it."""
    key = grading_key([key_entry()])
    del key["findings"]
    with pytest.raises(ValueError) as raised:
        _check_key(key, KEY_FILE)
    assert str(KEY_FILE) in str(raised.value)
    assert "docs/SCHEMAS.md" in str(raised.value)


def test_a_key_written_for_another_schema_version_is_refused() -> None:
    """Field names moved between versions, so a key from an older one cannot be guessed."""
    key = grading_key([key_entry()], schema_version=WRONG_SCHEMA_VERSION)
    with pytest.raises(ValueError) as raised:
        _check_key(key, KEY_FILE)
    assert str(WRONG_SCHEMA_VERSION) in str(raised.value)
    assert str(KEY_SCHEMA_VERSION) in str(raised.value)


def test_a_schema_version_written_as_a_string_is_refused() -> None:
    """`"2"` is a plausible typo in hand-written JSON and is not the version 2."""
    key = grading_key([key_entry()], schema_version=str(KEY_SCHEMA_VERSION))
    with pytest.raises(ValueError, match="schema_version"):
        _check_key(key, KEY_FILE)


def test_a_non_list_findings_field_is_refused() -> None:
    """A key lists what is really there, and a single object would be scored as zero."""
    key = grading_key([key_entry()], findings={"id": "TINY-01"})
    with pytest.raises(ValueError, match="non-list findings"):
        _check_key(key, KEY_FILE)


def test_a_null_findings_field_is_refused() -> None:
    """`null` would read as "no findings", which is the opposite of "not filled in"."""
    key = grading_key([key_entry()], findings=None)
    with pytest.raises(ValueError, match="non-list findings"):
        _check_key(key, KEY_FILE)


def test_a_key_that_is_not_an_object_at_all_is_refused() -> None:
    """A JSON file holding a list parses fine and would fail much later, on a field lookup."""
    with pytest.raises(ValueError, match="must hold a grading key object"):
        _check_key([key_entry()], KEY_FILE)


def test_the_wrong_top_level_type_is_named_in_the_refusal() -> None:
    """The reader is told what their file holds, so they can see what to change."""
    with pytest.raises(ValueError, match="list"):
        _check_key([key_entry()], KEY_FILE)


def test_every_key_field_the_scorer_reads_is_required_here() -> None:
    """The converse of the loop above: an unlisted field reaches the scorer unvalidated."""
    read = subscript_keys(parse(SCORER_SOURCE), KEY_VARIABLE)
    assert read <= set(KEY_FIELDS), sorted(read - set(KEY_FIELDS))


def test_the_scorer_reads_the_key_by_subscript_at_all() -> None:
    """Guard: a scan that found nothing would make the subset above vacuously true."""
    assert len(subscript_keys(parse(SCORER_SOURCE), KEY_VARIABLE)) > 5


def test_the_scan_sees_a_planted_read_of_an_unlisted_field(tmp_path) -> None:
    """Mutation check: a field read off a key must really be picked up by the scan."""
    planted = tmp_path / "planted_scorer.py"
    planted.write_text(PLANTED_SOURCE, encoding="utf-8")
    assert subscript_keys(parse(planted), KEY_VARIABLE) == {PLANTED_FIELD}
