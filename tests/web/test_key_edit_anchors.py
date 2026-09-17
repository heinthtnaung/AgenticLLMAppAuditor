"""An edit to a drafted key may not type a `file`, a `line` or a `code_anchor`.

**An anchor is a quotation.** Those three fields name source this page has never
read, and `key_drafting._anchor` reads each one off disk for exactly that reason
-- a model asked to quote text it was not shown invents it, and so would a
person typing into a browser. So the rule is not "these are read-only because
the form does not offer them"; it is that nothing on this side of the request
has seen the source they claim to quote. The refusal names how many entries
tried, so a caller fixing one is not sent round again for the next.

**The hole in it is closed, and the last four tests are that fix's regression.**
`_anchors_moved` built its `before` map from the entries already on disk and
skipped any id it did not know, so an edit could *append* an entry carrying a
typed file, line and anchor and draw no objection from anything downstream --
the entry is well formed and carries a non-empty anchor, so `key_promotion`
passes it, and promotion would have published ground truth quoting a line nobody
read. An unknown id now counts as an anchor moved, and the sentence says so.

The other rule an edit is held to -- that it may not move the key's standing --
is `test_key_edit_refusals.py`, which this was split from when the pair grew
past a file a reader should have to scroll.

Both directions are held: an edit that types an anchor is refused *and* writes
nothing, and the two edits the page exists to make -- correcting a title, and
deleting a wrong entry -- are not refused.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

from pathlib import Path

import httpx
import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient                     # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    ENTRY_COUNT, REFUSED, STORED_ORDER, entry_ids, entry_named, key_on_disk,
    planted_client, read_draft, save_draft)

# The entry a correction is made to, and the correction itself: a title is the
# kind of thing a human fixing a drafted key actually changes.
CORRECTED_ENTRY = "K-01"
CORRECTED_TITLE = "user text is interpolated into the system instructions"
EDITABLE_ENTRY_FIELD = "title"

# An anchor typed rather than quoted, and a line nobody read.
INVENTED_ANCHOR = "os.system(whatever_the_editor_typed)"
INVENTED_LINE = 4242
INVENTED_FILE = "a-file-that-was-never-read.py"

# An entry the drafter never wrote, with every field a well-formed one carries --
# so nothing downstream would object to it, which is the point.
APPENDED_ENTRY = {
    "id": "K-99", "file": INVENTED_FILE, "line": INVENTED_LINE,
    "owasp_id": "LLM06", "llm_surface": "TOOL_CALL", "surface_name": None,
    "component": None, "detection": "static", "title": "typed, never read",
    "description": "an entry the drafter never wrote",
    "code_anchor": INVENTED_ANCHOR}

# What one entry looks like when it is the only one that tried.
ONE_ENTRY = 1


def anchor_refusal(count: int) -> str:
    """The opening of the sentence a moved or invented anchor is refused with.

    Built from the count and written once, because four assertions quote it and
    a reworded message that four tests no longer recognise is how an
    exact-message check quietly stops being one.
    """
    return f"{count} entries add or move a file, line or anchor"


def a_key_to_edit(monkeypatch: pytest.MonkeyPatch,
                  tmp_path: Path) -> tuple[TestClient, Path, dict]:
    """A client, the folder behind it, and the draft as it stands -- how each test starts."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    return client, drafts, read_draft(client)["key"]


def refusal_from(response: httpx.Response) -> str:
    """The sentence a refused edit answered with, insisting it was a refusal."""
    assert response.status_code == REFUSED, response.text
    return response.json()["detail"]


# --- the anchors an edit may not type -----------------------------------------

@pytest.mark.parametrize("field,typed", [("file", INVENTED_FILE),
                                         ("line", INVENTED_LINE),
                                         ("code_anchor", INVENTED_ANCHOR)])
def test_moving_an_anchor_on_an_entry_is_refused(monkeypatch, tmp_path,
                                                 field: str, typed: object) -> None:
    """All three, because all three are quotations from source this page has not read."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    entry_named(key, CORRECTED_ENTRY)[field] = typed
    detail = refusal_from(save_draft(client, key))
    assert detail.startswith(anchor_refusal(ONE_ENTRY))


def test_the_refusal_counts_every_entry_that_tried(monkeypatch, tmp_path) -> None:
    """Named as a number: a caller fixing one must not find the next by saving again."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    for entry in key["findings"]:
        entry["line"] = INVENTED_LINE
    detail = refusal_from(save_draft(client, key))
    assert detail.startswith(anchor_refusal(ENTRY_COUNT))


def test_correcting_a_title_is_not_a_moved_anchor(monkeypatch, tmp_path) -> None:
    """Non-vacuity: the anchor rule must not refuse the edit the page exists to make."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    entry_named(key, CORRECTED_ENTRY)[EDITABLE_ENTRY_FIELD] = CORRECTED_TITLE
    assert save_draft(client, key).status_code != REFUSED


def test_an_entry_the_draft_never_held_may_not_type_an_anchor_either(
        monkeypatch, tmp_path) -> None:
    """The closed hole: an *appended* entry types a file, a line and an anchor unchecked.

    `_anchors_moved` built its `before` map from the entries already on disk and
    skipped any id it did not know, so this request was accepted: the key was
    saved with the invented anchor in it, `finding_count` was recomputed to
    include it, and `key_promotion.refusals` did not object either -- the entry
    carries every required field and a non-empty anchor. Promotion would then
    have published ground truth quoting a line nobody looked at.

    The editor's own UI cannot add an entry, so this was reachable only by a
    hand-made PUT -- which is the threat model of an endpoint with no
    authentication, not an edge case outside it.
    """
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    key["findings"].append(dict(APPENDED_ENTRY))
    assert save_draft(client, key).status_code == REFUSED


def test_the_appended_entry_is_counted_as_one_that_tried(monkeypatch, tmp_path) -> None:
    """Counted, not merely refused: the sentence has to name the entry the caller added."""
    client, _drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    key["findings"].append(dict(APPENDED_ENTRY))
    assert refusal_from(save_draft(client, key)).startswith(anchor_refusal(ONE_ENTRY))


def test_the_appended_entry_never_reached_the_draft_on_disk(monkeypatch, tmp_path) -> None:
    """What the refusal is for: an invented anchor that was written is already published."""
    client, drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    before = key_on_disk(drafts)
    key["findings"].append(dict(APPENDED_ENTRY))
    save_draft(client, key)
    assert key_on_disk(drafts) == before
    assert entry_ids(key_on_disk(drafts)) == STORED_ORDER


def test_deleting_an_entry_is_not_an_invented_anchor(monkeypatch, tmp_path) -> None:
    """Non-vacuity on the new half: an id the edit drops is not an id it typed.

    The rule counts entries the *edit* carries that the draft did not, so a
    shorter list must pass -- deleting a wrong entry is the second thing this
    page exists for, after correcting a title, and `DERIVED_COUNTS` recomputes
    `finding_count` precisely so that it can.
    """
    client, drafts, key = a_key_to_edit(monkeypatch, tmp_path)
    key["findings"] = [entry for entry in key["findings"]
                       if entry["id"] != CORRECTED_ENTRY]
    assert save_draft(client, key).status_code != REFUSED
    assert key_on_disk(drafts)["finding_count"] == ENTRY_COUNT - 1
