"""An edit to a drafted key may not move the key's own standing.

Refused **by name** rather than silently restored, and that choice is the
subject of this file. An editor that quietly put `source` back would accept a
request that meant to launder the key and answer as though it had worked -- 200,
with a document that says something the caller did not ask for.

**The laundering case is the one that matters, and it is not hypothetical.**
All three pairings are valid documents -- `tool_drafted` + `verified: false`,
`tool_drafted` + `verified: true` since 2026-09-16, and `manual_review` +
`verified: true` -- so flipping `source` and `verified` together passes every
check this project has. A test below asserts exactly that: the laundered
document draws no refusal at all from `key_promotion`, which is what makes
`FROZEN_FIELDS` load-bearing rather than belt-and-braces. The qualification
`key_drafted_by_scored_system` is about **validity, not quality**: a human
checking every entry has checked the entries, and has not made the tool's own
choice of what to include independent of the tool.

**Freezing `verified` too is not redundant, and it became less redundant.**
`check_key` used to refuse `tool_drafted` + `verified: true`, so a save that
moved `verified` alone would have been caught downstream at promotion. That
guard is gone: the pairing is legal, and a `verified` a save could move would be
a claim recorded with no name, no date and no route -- which is why the verify
route stamps both and this list keeps all four of `source`, `verified`,
`verified_by` and `verified_date` frozen for a save.

The other rule an edit is held to -- that it may not type a `file`, a `line` or
a `code_anchor`, because those quote source this page has never read -- is
`test_key_edit_anchors.py`. The two were one file until the pair grew past what
a reader should have to scroll.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import json
from pathlib import Path

import httpx
import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient                     # noqa: E402

import key_edit_guard                                         # noqa: E402
from keys import key_promotion                                # noqa: E402
from keys.grading_keys import MANUAL_REVIEW, TOOL_DRAFTED     # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    APP, HUMAN_PIN_FIELDS, REFUSED, entry_named, key_on_disk, planted_client,
    read_draft, save_draft, saved)

# What a laundering edit would set, and what the draft really says.
LAUNDERED_SOURCE = MANUAL_REVIEW
LAUNDERED_BY = "A Person Who Did Not Check It"
LAUNDERED_DATE = "2026-09-15"

# The entry a correction is made to, and the correction itself: a title is the
# kind of thing a human fixing a drafted key actually changes.
CORRECTED_ENTRY = "K-01"
CORRECTED_TITLE = "user text is interpolated into the system instructions"

# A field of the drafted key that is not frozen and not an anchor, so a save has
# something it is *allowed* to change.
EDITABLE_ENTRY_FIELD = "title"


def a_key_to_edit(monkeypatch: pytest.MonkeyPatch,
                  tmp_path: Path) -> tuple[TestClient, Path, dict]:
    """A client, the folder behind it, and the draft as it stands -- how each test starts."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    return client, drafts, read_draft(client)["key"]


def refusal_from(response: httpx.Response) -> str:
    """The sentence a refused edit answered with, insisting it was a refusal."""
    assert response.status_code == REFUSED, response.text
    return response.json()["detail"]


# --- the standing an edit may not move ----------------------------------------

def test_the_laundering_edit_is_refused_naming_both_fields(monkeypatch, tmp_path) -> None:
    """The pair, flipped together: the edit this rule exists for, refused by name."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    detail = refusal_from(save_draft(client, {**key, "source": LAUNDERED_SOURCE,
                                              "verified": True}))
    assert "source, verified" in detail
    assert TOOL_DRAFTED in detail


def test_the_laundered_document_would_have_been_accepted_by_everything_else(
        monkeypatch, tmp_path) -> None:
    """Why the rule is not belt-and-braces: promotion itself finds nothing wrong with it.

    The laundered document is well formed, at the right schema version, with a
    source in the vocabulary and a verification claim that no longer contradicts
    it. Nothing downstream objects, so this endpoint is the only thing standing
    between a drafted key and one that reads as human-authored.
    """
    client, drafts = planted_client(monkeypatch, tmp_path, pin_fields=HUMAN_PIN_FIELDS)
    key = read_draft(client)["key"]
    laundered = {**key, "source": LAUNDERED_SOURCE, "verified": True,
                 "verified_by": LAUNDERED_BY, "verified_date": LAUNDERED_DATE}
    pin = json.loads((drafts / f"{APP}.manifest.json").read_text(encoding="utf-8"))
    assert key_promotion.refusals(laundered, pin) == []
    assert save_draft(client, laundered).status_code == REFUSED


def test_the_refused_edit_changed_nothing_on_disk(monkeypatch, tmp_path) -> None:
    """A refusal that had already written would be worse than no rule at all."""
    client, drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    before = key_on_disk(drafts)
    save_draft(client, {**key, "source": LAUNDERED_SOURCE, "verified": True})
    assert key_on_disk(drafts) == before
    assert key_on_disk(drafts)["source"] == TOOL_DRAFTED


@pytest.mark.parametrize("field", key_edit_guard.FROZEN_FIELDS)
def test_every_frozen_field_is_refused_by_name(monkeypatch, tmp_path, field: str) -> None:
    """Each one, not the two that made the rule: a field frozen in name only is not frozen."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    detail = refusal_from(save_draft(client, {**key, field: _something_else(key[field])}))
    assert field in detail


def _something_else(value: object) -> object:
    """Any value of the same shape that is not the one on disk."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, list):
        return value[:-1]
    return f"{value}-moved"


def test_an_edit_that_repeats_the_frozen_fields_unchanged_is_accepted(
        monkeypatch, tmp_path) -> None:
    """Non-vacuity, and the real client's behaviour: the page posts the whole document back."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    entry_named(key, CORRECTED_ENTRY)[EDITABLE_ENTRY_FIELD] = CORRECTED_TITLE
    reply = saved(client, key)
    assert entry_named(reply["key"], CORRECTED_ENTRY)[EDITABLE_ENTRY_FIELD] == CORRECTED_TITLE
    assert reply["key"]["source"] == TOOL_DRAFTED


def test_the_surfaces_the_extractor_found_are_frozen_too(monkeypatch, tmp_path) -> None:
    """Not a human judgement: edit these and the key can no longer say a surface was *missed*."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    detail = refusal_from(save_draft(client, {**key, "expected_surfaces": []}))
    assert "expected_surfaces" in detail


# --- and the half of the pair a route does move -------------------------------

def test_a_save_may_not_move_verified_on_its_own_either(monkeypatch, tmp_path) -> None:
    """The half that used to be caught downstream, and now is not caught anywhere else.

    A save flipping `verified` alone leaves a document `check_key` accepts and
    `key_promotion` passes -- a recorded human check with nobody's name on it
    and no date. The verify route exists so that claim carries both.
    """
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    detail = refusal_from(save_draft(client, {**key, "verified": True}))
    assert "verified" in detail
    assert "verify route" in detail


def test_the_key_that_save_would_have_written_is_one_nothing_else_refuses(
        monkeypatch, tmp_path) -> None:
    """Non-vacuity for the test above: the refusal is this endpoint's and no one else's."""
    client, drafts = planted_client(monkeypatch, tmp_path, pin_fields=HUMAN_PIN_FIELDS)
    key = read_draft(client)["key"]
    pin = json.loads((drafts / f"{APP}.manifest.json").read_text(encoding="utf-8"))
    assert key_promotion.refusals({**key, "verified": True}, pin) == []


def test_a_save_may_not_type_a_verifier_or_a_date(monkeypatch, tmp_path) -> None:
    """Both stamps are the route's: a typed date is a claim that can be backdated."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    detail = refusal_from(save_draft(client, {**key, "verified_by": LAUNDERED_BY,
                                              "verified_date": LAUNDERED_DATE}))
    assert "verified_by, verified_date" in detail
