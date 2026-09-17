"""A save whose `findings` is not a list of entries, and the draft it must not destroy.

**The first fix here was worse than the crash it replaced.** Making
`anchors_moved` and `settled` treat a malformed `findings` as "no entries"
turned the 500 into a 200 -- and `PUT {"key": {"findings": "xy"}}` then wrote an
empty list over a draft holding three real ones. Measured on that version:

    PUT findings 'xy' -> 200
    entries on disk after: 0 []

A correction request destroying the thing it was sent to correct, from an
unauthenticated body, with no hand-edited file involved anywhere. The 500 at
least left the file alone. `entries_malformed` now refuses the body outright and
`key_routes._guard_frozen` asks it first, before any other check.

**The test that matters is the one about the file**, and it deliberately asserts
nothing about the status: a version that answers 200 and empties the draft has
to fail here on the data loss, not on a number. The status and the sentence are
asserted separately, and a real edit is saved below so "nothing changed" cannot
pass by refusing everything.

**A body that *omits* `findings` is refused by the same guard**, and an explicit
`[]` is not. That pair is its own decision and its own file:
`test_key_edit_absent_findings.py`.

Coercion is still right in one place and stays there: reading what is *already
on disk*, where the entries are a file somebody hand-edited and the route's job
is to report on it rather than crash. That half is
`test_key_member_shapes.py`.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import httpx                                                 # noqa: E402
from fastapi.testclient import TestClient                    # noqa: E402

from key_edit_guard import entries_malformed                 # noqa: E402
from keys.grading_keys import MANUAL_REVIEW                  # noqa: E402

from .key_fixtures import (                                  # noqa: E402
    ENTRY_COUNT, OK, REFUSED, STORED_ORDER, entry_ids, entry_named, key_on_disk,
    planted_client, read_draft, save_draft)

# Every body a page bug, a hand-written curl or a sloppy client can send, with
# the sentence each has to be refused with. The type name is in the message
# because "malformed" alone tells nobody what they sent.
MALFORMED_BODIES = {
    "a string": ("xy", "findings must be a list, not str"),
    "null": (None, "findings must be a list, not NoneType"),
    "a list of numbers": ([1, 2], "findings entries must be objects"),
    "a list holding null": ([None], "findings entries must be objects"),
}
BODY_IDS = list(MALFORMED_BODIES)
BODY_CASES = list(MALFORMED_BODIES.values())
BODY_SHAPES = [shape for shape, _message in BODY_CASES]

# What the whole refusal says after the reason, so a reader is told what a save
# is for rather than only what it would not do.
REFUSAL_ADVICE = "A save corrects entries; it cannot replace them"

# The entry a real edit corrects, and the correction. A title is what a human
# fixing a drafted key actually changes.
CORRECTED_ENTRY = "K-01"
CORRECTED_TITLE = "user text is interpolated into the system instructions"

# A body that tries two things at once: move the key's standing, and hand in
# entries that are not entries. Only one of them can be reported first.
LAUNDERED_SOURCE = MANUAL_REVIEW


def a_draft_and_its_client(monkeypatch: pytest.MonkeyPatch,
                           tmp_path: Path) -> tuple[TestClient, Path, dict]:
    """A client, the folder behind it, and the draft as it stands -- how each test starts."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    return client, drafts, read_draft(client)["key"]


def detail_of(response: httpx.Response) -> str:
    """The sentence a refused save answered with, insisting it was a refusal."""
    assert response.status_code == REFUSED, f"{response.status_code}: {response.text}"
    return response.json()["detail"]


# --- the file, which is the half that was lost ----------------------------------

@pytest.mark.parametrize("shape", BODY_SHAPES, ids=BODY_IDS)
def test_a_refused_save_leaves_every_entry_on_disk(monkeypatch, tmp_path,
                                                   shape: object) -> None:
    """Count *and* content, and not one word about the status.

    This is the assertion the broken version fails: it answered 200 and left
    `findings: []` behind. A test that only checked the status would have gone
    green on a route that had just deleted the draft's entries.
    """
    client, drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    save_draft(client, {**key, "findings": shape})
    stored = key_on_disk(drafts)
    assert len(stored["findings"]) == ENTRY_COUNT
    assert entry_ids(stored) == STORED_ORDER
    assert stored["finding_count"] == ENTRY_COUNT


@pytest.mark.parametrize("shape", BODY_SHAPES, ids=BODY_IDS)
def test_the_whole_draft_is_what_it_was_before_the_request(monkeypatch, tmp_path,
                                                           shape: object) -> None:
    """Said over the document, so a field nobody thought to name cannot have moved either."""
    client, drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    before = key_on_disk(drafts)
    save_draft(client, {**key, "findings": shape})
    assert key_on_disk(drafts) == before


# --- and the answer the caller gets ---------------------------------------------

@pytest.mark.parametrize("shape,message", BODY_CASES, ids=BODY_IDS)
def test_a_malformed_findings_is_refused_with_its_own_reason(
        monkeypatch, tmp_path, shape: object, message: str) -> None:
    """400 and a sentence naming what arrived: a client cannot fix "malformed"."""
    client, _drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    assert message in detail_of(save_draft(client, {**key, "findings": shape}))


def test_the_refusal_says_what_a_save_is_for(monkeypatch, tmp_path) -> None:
    """The advice beside the reason: entries are corrected here, never replaced wholesale."""
    client, _drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    assert REFUSAL_ADVICE in detail_of(save_draft(client, {**key, "findings": "xy"}))


def test_the_entries_are_checked_before_anything_else_the_body_did(monkeypatch,
                                                                   tmp_path) -> None:
    """First, because every check after it reads the entries this body does not have."""
    client, _drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    detail = detail_of(save_draft(client, {**key, "findings": "xy",
                                           "source": LAUNDERED_SOURCE}))
    assert "findings must be a list" in detail
    assert "source" not in detail


# --- the off position: a save that should work still works ----------------------

def test_a_real_correction_is_still_saved(monkeypatch, tmp_path) -> None:
    """Without this, every assertion above is satisfied by a route that refuses everything."""
    client, drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    entry_named(key, CORRECTED_ENTRY)["title"] = CORRECTED_TITLE
    assert save_draft(client, key).status_code == OK
    stored = key_on_disk(drafts)
    assert entry_named(stored, CORRECTED_ENTRY)["title"] == CORRECTED_TITLE
    assert entry_ids(stored) == STORED_ORDER


# --- the guard on its own -------------------------------------------------------

def test_a_well_formed_body_is_not_malformed(monkeypatch, tmp_path) -> None:
    """The guard's own off position, asked of the function rather than through a route."""
    client, _drafts, key = a_draft_and_its_client(monkeypatch, tmp_path)
    assert entries_malformed(key) is None


@pytest.mark.parametrize("shape,message", BODY_CASES, ids=BODY_IDS)
def test_the_guard_names_the_shape_it_was_handed(shape: object, message: str) -> None:
    """One reason per shape, straight from the function both routes would consult."""
    assert message in entries_malformed({"findings": shape})


def test_the_guard_names_which_entries_are_not_entries() -> None:
    """Two bad entries among any number: a reason naming neither would not be actionable."""
    assert entries_malformed({"findings": [1, 2]}).endswith("0, 1")


def test_a_key_that_is_not_an_object_at_all_is_refused_too() -> None:
    """Unreachable through the route -- pydantic types `key` as a dict -- and held anyway.

    `entries_malformed` is the editor's answer to "is this a document I can
    read", and `key_verify_route` is one import away from needing it. A guard
    that assumed its own caller's typing is the fault this whole pass is about.
    """
    assert entries_malformed([]) == "the key must be a json object, not list"
