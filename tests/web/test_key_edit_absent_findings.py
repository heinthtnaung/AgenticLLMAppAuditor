"""A body that omits `findings`, and the explicit empty list it is not.

**One `in` apart, and only one of them is somebody's decision.** An explicit
`findings: []` is a person saying the draft holds nothing worth keeping --
`test_key_edit_save.py` is built on deletion being a legal edit. A body that
simply *omits* the field means nothing in particular: it is a page bug, a
half-built request, a client that reshaped the document. `settled` derives the
entries from whatever is there, so an absent field settled to no entries and the
save answered 200 over a draft holding three real ones. That is the same data
loss `test_key_edit_malformed_entries.py` is about, reached by dropping a field
rather than mangling one. Measured before the decision:

    PUT with no findings key -> 200 | on disk: 0 entries, finding_count 0

The two cases are asserted **side by side, with the count on disk for both**,
and the guard is asked about them in a single test. Splitting them into separate
files, or asserting only the refusal, is what would let a later tidy-up read an
absent `findings` as an empty one again -- which is one character of source and
no failing test.

The refusal names both things the caller might have meant, because "no findings"
is exactly the message a client cannot act on: send the entries you are keeping,
or send `[]` and mean it.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient                    # noqa: E402

from key_edit_guard import entries_malformed                 # noqa: E402

from .key_fixtures import (                                  # noqa: E402
    ENTRY_COUNT, OK, REFUSED, STORED_ORDER, entry_ids, key_on_disk,
    planted_client, read_draft, save_draft)

# The two bodies the whole file is about, as a guard sees them. Spelled
# together because they must never be read the same way again.
OMITS_FINDINGS: dict = {}
DELETES_EVERY_ENTRY: dict = {"findings": []}

# What a draft holds after each: the entries it had, or none at all.
NO_ENTRIES = 0

# The refusal, and both of the things the caller might have meant.
OMISSION_SAID = "names no findings at all"
OR_SEND_AN_EMPTY_LIST = "empty list to delete every one of them"


def a_draft_and_its_client(monkeypatch: pytest.MonkeyPatch,
                           tmp_path: Path) -> tuple[TestClient, Path, dict]:
    """A client, the folder behind it, and the draft as it stands."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    return client, drafts, read_draft(client)["key"]


def without_findings(key: dict) -> dict:
    """The same body with the field dropped, which is what a page bug sends."""
    return {field: value for field, value in key.items() if field != "findings"}


def entries_on_disk(drafts: Path) -> list[str]:
    """The ids the draft really holds, which is the only thing a status cannot tell us."""
    return entry_ids(key_on_disk(drafts))


# --- the omission, which is nobody's decision ------------------------------------

def test_a_body_that_omits_findings_leaves_every_entry_on_disk(monkeypatch,
                                                               tmp_path) -> None:
    """The loss itself, with not one word about the status.

    A guard that reads an absent `findings` as "no entries" empties the draft
    and answers 200, so a test asserting the status alone would pass over a
    route that had just deleted three entries. This one fails on the count.
    """
    client, drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    save_draft(client, without_findings(key))
    assert len(key_on_disk(drafts)["findings"]) == ENTRY_COUNT
    assert entries_on_disk(drafts) == STORED_ORDER


def test_the_omission_is_refused_and_says_what_to_send_instead(monkeypatch,
                                                               tmp_path) -> None:
    """Both options named: the entries you meant to keep, or the empty list you meant."""
    client, _drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    response = save_draft(client, without_findings(key))
    assert response.status_code == REFUSED, response.text
    detail = response.json()["detail"]
    assert OMISSION_SAID in detail
    assert OR_SEND_AN_EMPTY_LIST in detail


# --- the deletion, which is ------------------------------------------------------

def test_deleting_every_entry_on_purpose_still_works(monkeypatch, tmp_path) -> None:
    """The half that must keep working, and the reason the two cannot be one rule.

    Refusing this as well would make the guard tidier and the page poorer: a
    person who has read a drafted key and decided none of it is right has no
    other way to say so.
    """
    client, drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    assert save_draft(client, {**key, **DELETES_EVERY_ENTRY}).status_code == OK
    stored = key_on_disk(drafts)
    assert len(stored["findings"]) == NO_ENTRIES
    assert stored["finding_count"] == NO_ENTRIES


# --- and the one line that tells them apart --------------------------------------

def test_the_guard_tells_an_absent_findings_from_an_empty_one() -> None:
    """Both in one test, so a simplification that merges them cannot pass.

    `"findings" in edited` is the whole difference. Asserted as a pair rather
    than as two tests, because two tests can be deleted one at a time.
    """
    assert entries_malformed(OMITS_FINDINGS) is not None
    assert entries_malformed(DELETES_EVERY_ENTRY) is None
