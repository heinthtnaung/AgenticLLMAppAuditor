"""Refusing one malformed entry in a grading key's `findings`, and saying which one.

A grading key is hand-placed input since the pinned corpus was removed, and a
malformed *entry* is the likelier mistake than a malformed top level: the file
is a long list, and the fields inside it are the ones a person retypes. Left
unchecked it used to reach `scorer.py` and raise a bare `KeyError` naming a
field but no file and no position -- which tells whoever wrote the key nothing
about where to look. `KeyError` is not one of `evaluate.py`'s expected
failures, so it escaped the CLI as a traceback.

Split from `test_key_check.py`, which is about the shape of the key as a whole;
the artifacts are `test_artifact_check.py`, the read itself `test_harness.py`,
and the source scan holding `ENTRY_FIELDS` to every real entry read is
`test_entry_field_cover.py`. Every case here is a dict: `_check_key` is pure,
so nothing needs a filesystem.

Two directions, and the second is the one that matters most. That each required
field is really required is the refusal half. That an entry carrying **only**
those fields is *accepted* is the other, because a check stricter than the
schema would pass every refusal test here while refusing valid keys -- and the
field it would most plausibly over-require is `component`, which `SCHEMAS.md`
marks optional and `grading.py` reads only behind a `.get()` guard.
"""

from pathlib import Path

import pytest

from evaluation.harness import ENTRY_FIELDS, _check_key
from evaluation_fixtures import grading_key, key_entry

# Stands in for the path the key was read from; nothing here opens it.
KEY_FILE = Path("grading_keys/an-app.ground_truth.json")

# One entry carrying exactly the required fields and nothing else -- in
# particular no `component`, which is optional and belongs only to a
# supply-chain entry.
MINIMAL_ENTRY = {
    "id": "TINY-02", "file": "app/agent.py", "line": 12, "owasp_id": "LLM01",
}


def refuse(entries: list) -> str:
    """Check a key holding these entries and return the refusal it raises."""
    with pytest.raises(ValueError) as raised:
        _check_key(grading_key(entries), KEY_FILE)
    return str(raised.value)


def test_an_entry_with_only_the_required_fields_is_accepted() -> None:
    """The positive guard: a check stricter than the schema would refuse a valid key."""
    key = grading_key([MINIMAL_ENTRY])
    assert _check_key(key, KEY_FILE) is key


def test_component_is_not_a_required_entry_field() -> None:
    """Deliberately absent: it is optional, and most entries are not about a component."""
    # All three are read only behind a `.get()` guard in `grading.py`, so a key
    # omitting them scores fine rather than crashing, and `_check_entry`
    # demands only what would crash. For `component` and `surface_name`, which
    # `SCHEMAS.md` marks optional, requiring them would refuse a valid key;
    # `llm_surface` is required-but-nullable there and still absent here,
    # because this check turns a crash into a message rather than restating the
    # schema.
    for guarded in ("component", "surface_name", "llm_surface"):
        assert guarded not in MINIMAL_ENTRY
    assert "component" not in ENTRY_FIELDS


def test_the_minimal_entry_carries_exactly_the_required_fields() -> None:
    """Guard on the fixture above: a field added to the list must be added to it too."""
    assert set(MINIMAL_ENTRY) == set(ENTRY_FIELDS)


def test_every_field_an_entry_needs_is_required() -> None:
    """One entry per field, each missing exactly that field, so none of them is optional."""
    for field in ENTRY_FIELDS:
        entry = key_entry()
        del entry[field]
        assert f"is missing {field}" in refuse([entry])


def test_two_missing_entry_fields_are_both_named() -> None:
    """Naming one at a time would send the reader back to the same entry twice."""
    entry = key_entry()
    del entry["line"], entry["owasp_id"]
    refusal = refuse([entry])
    assert "line" in refusal and "owasp_id" in refusal


def test_the_malformed_entry_is_named_by_its_position_in_the_key() -> None:
    """A key with twenty findings is unscannable by eye, so the refusal points at one."""
    entry = key_entry()
    del entry["owasp_id"]
    assert f"{KEY_FILE} findings[1] is missing owasp_id" in refuse([key_entry(), entry])


def test_an_entry_that_is_not_an_object_is_refused_with_what_it_is() -> None:
    """A bare id where an entry belongs is valid JSON and would fail on a field lookup."""
    assert "findings[0] must be an object, got str" in refuse(["TINY-01"])


def test_a_null_entry_is_refused_too() -> None:
    """`null` in the list is the shape a half-deleted entry leaves behind."""
    assert "findings[0] must be an object, got NoneType" in refuse([None])


def test_the_entry_refusal_says_where_the_shape_is_written_down() -> None:
    """The reader needs what belongs in an entry, not only that one is wrong."""
    entry = key_entry()
    del entry["file"]
    assert "docs/SCHEMAS.md" in refuse([entry])
