"""What a save recomputes, what it re-sorts, and why it is not gated on the refusals.

Three facts, each with a reason outside this module:

**`finding_count` is recomputed, never taken from the body.**
`key_promotion._miscounted` refuses a key whose count and entries disagree, and a
person deleting an entry in a browser leaves a stale count behind by default. So
the count is derived on every save and a typed one is ignored.

**The entries are re-sorted by `(file, line, id)`.** `key_promotion._out_of_order`
refuses a key that is not, for a reason the promotion module states: two
revisions of one key have to be diffable.

**The refusals are reported and not enforced.** This is the correction that
matters, and the first version of this feature had it the other way round.
Nearly everything `key_promotion.refusals` reports about a draft concerns the
*manifest* -- "the manifest names no framework or language; both are human
judgements about the app and a draft cannot supply them" -- which this editor
cannot fix and a drafted pin can never satisfy. Gated on that, the endpoint
could never have saved anything at all. `promote_key.py` is the gate; this page
corrects entries and says what still blocks promotion.

The two rules a save *is* refused for are `test_key_edit_refusals.py`'s subject.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient                     # noqa: E402

from keys import key_promotion                                # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    APP, ENTRY_COUNT, HUMAN_PIN_FIELDS, KEYS_ENDPOINT, NO_SUCH_DRAFT, STORED_ORDER,
    client_over, entry_ids, entry_named, key_on_disk, plant, planted_client,
    read_draft, save_draft, saved)

# The entry a test deletes, and what the count must become. Named rather than
# computed from the reply, so a save that dropped everything cannot pass.
DELETED_ENTRY = "K-03"
COUNT_AFTER_DELETION = ENTRY_COUNT - 1
ORDER_AFTER_DELETION = [name for name in STORED_ORDER if name != DELETED_ENTRY]

# A count nobody could have derived, to show the field is recomputed rather than
# trusted. `_miscounted` is what would refuse it at promotion.
TYPED_COUNT = 99

CORRECTED_ENTRY = "K-01"
CORRECTED_TITLE = "user text is interpolated into the system instructions"
CORRECTED_DESCRIPTION = "the template puts the question inside the instructions"

# The one refusal a drafted manifest always carries, matched by its opening
# rather than transcribed whole -- `test_key_routes.py` holds the full sentence.
PIN_REFUSAL_OPENING = "the manifest names no framework or language"


def edited_draft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                 pin_fields: dict | None = None) -> tuple[TestClient, Path, dict]:
    """A client, its drafts folder, and the draft as it stands -- how each test starts."""
    client, drafts = planted_client(monkeypatch, tmp_path, pin_fields=pin_fields)
    return client, drafts, read_draft(client)["key"]


def without(key: dict, entry_id: str) -> dict:
    """The same key with one entry removed, which is the only structural edit the page offers."""
    return {**key, "findings": [entry for entry in key["findings"]
                                if entry["id"] != entry_id]}


# --- the count ----------------------------------------------------------------

def test_deleting_an_entry_recomputes_the_count(monkeypatch, tmp_path) -> None:
    """The case that made the rule: a stale count is what `_miscounted` refuses."""
    client, _drafts, key = edited_draft(monkeypatch, tmp_path)
    assert key["finding_count"] == ENTRY_COUNT
    reply = saved(client, without(key, DELETED_ENTRY))
    assert reply["key"]["finding_count"] == COUNT_AFTER_DELETION
    assert entry_ids(reply["key"]) == ORDER_AFTER_DELETION


def test_the_recomputed_count_is_what_lands_on_disk(monkeypatch, tmp_path) -> None:
    """The reply is not the artifact: `promote_key.py` reads the file, so the file is asserted."""
    client, drafts, key = edited_draft(monkeypatch, tmp_path)
    saved(client, without(key, DELETED_ENTRY))
    assert key_on_disk(drafts)["finding_count"] == COUNT_AFTER_DELETION


def test_a_count_typed_into_the_body_is_ignored(monkeypatch, tmp_path) -> None:
    """Derived, never trusted: a body that names its own count names it wrongly."""
    client, _drafts, key = edited_draft(monkeypatch, tmp_path)
    reply = saved(client, {**key, "finding_count": TYPED_COUNT})
    assert reply["key"]["finding_count"] == ENTRY_COUNT


# --- the order ----------------------------------------------------------------

def test_the_entries_are_re_sorted_on_every_save(monkeypatch, tmp_path) -> None:
    """`_out_of_order` refuses a key that is not, so two revisions of one key stay diffable."""
    client, _drafts, key = edited_draft(monkeypatch, tmp_path)
    shuffled = {**key, "findings": list(reversed(key["findings"]))}
    assert entry_ids(shuffled) != STORED_ORDER
    assert entry_ids(saved(client, shuffled)["key"]) == STORED_ORDER


def test_a_saved_key_is_one_promotion_would_not_refuse_for_its_shape(
        monkeypatch, tmp_path) -> None:
    """The point of both rules at once, asked of the module that owns them.

    The body sent is out of order *and* miscounted -- the two states a browser
    produces. What comes back draws no refusal from `key_promotion` at all,
    which is the only form of this assertion that cannot drift from the checks
    promotion really applies.
    """
    client, drafts, key = edited_draft(monkeypatch, tmp_path, HUMAN_PIN_FIELDS)
    reply = saved(client, {**key, "finding_count": TYPED_COUNT,
                           "findings": list(reversed(key["findings"]))})
    pin = json.loads((drafts / f"{APP}.manifest.json").read_text(encoding="utf-8"))
    assert key_promotion.refusals(reply["key"], pin) == []
    assert reply["refusals"] == []


# --- reported, not enforced ---------------------------------------------------

def test_a_draft_whose_manifest_is_unfinished_can_still_be_corrected(
        monkeypatch, tmp_path) -> None:
    """Every real draft is in this state, so a gate here would make the page useless."""
    client, drafts, key = edited_draft(monkeypatch, tmp_path)
    entry_named(key, CORRECTED_ENTRY)["title"] = CORRECTED_TITLE
    reply = saved(client, key)
    assert entry_named(reply["key"], CORRECTED_ENTRY)["title"] == CORRECTED_TITLE
    assert entry_named(key_on_disk(drafts), CORRECTED_ENTRY)["title"] == CORRECTED_TITLE


def test_the_save_says_what_still_blocks_promotion(monkeypatch, tmp_path) -> None:
    """Saved *and* told: a correction that silently left the key unpromotable would mislead."""
    client, _drafts, key = edited_draft(monkeypatch, tmp_path)
    reply = saved(client, key)
    assert len(reply["refusals"]) == 1
    assert reply["refusals"][0].startswith(PIN_REFUSAL_OPENING)


def test_a_correction_reaches_every_field_the_page_offers(monkeypatch, tmp_path) -> None:
    """Guard: the save above would look the same if it had written the document back unchanged."""
    client, drafts, key = edited_draft(monkeypatch, tmp_path)
    corrected = entry_named(key, CORRECTED_ENTRY)
    corrected["title"] = CORRECTED_TITLE
    corrected["description"] = CORRECTED_DESCRIPTION
    corrected["owasp_id"] = "LLM06"
    stored = entry_named(key_on_disk(drafts), CORRECTED_ENTRY)
    assert stored["title"] != CORRECTED_TITLE
    written = entry_named(saved(client, key)["key"], CORRECTED_ENTRY)
    assert (written["title"], written["description"], written["owasp_id"]) == (
        CORRECTED_TITLE, CORRECTED_DESCRIPTION, "LLM06")


# --- what was written ---------------------------------------------------------

def test_the_reply_is_exactly_what_was_written(monkeypatch, tmp_path) -> None:
    """One document, not two: the page renders what promotion will later read."""
    client, drafts, key = edited_draft(monkeypatch, tmp_path)
    reply = saved(client, without(key, DELETED_ENTRY))
    assert reply["key"] == key_on_disk(drafts)


def test_the_file_is_written_the_way_every_other_document_here_is(
        monkeypatch, tmp_path) -> None:
    """Sorted keys, two-space indent, trailing newline -- so a saved key diffs against a drafted one."""
    client, drafts, key = edited_draft(monkeypatch, tmp_path)
    saved(client, key)
    written = (drafts / f"{APP}.ground_truth.json").read_text(encoding="utf-8")
    assert written.endswith("\n")
    assert written == json.dumps(json.loads(written), indent=2, sort_keys=True) + "\n"


# --- the saves that find nothing to save --------------------------------------

def test_saving_a_draft_that_does_not_exist_is_a_404(monkeypatch, tmp_path) -> None:
    """Read before write: a PUT never creates a key, so a name nobody drafted is not one."""
    client, _drafts, key = edited_draft(monkeypatch, tmp_path)
    response = save_draft(client, key, "never-drafted")
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == "no drafted key for never-drafted"


def test_a_put_may_not_create_a_key_in_an_empty_folder(monkeypatch, tmp_path) -> None:
    """The consequence said plainly: nothing a caller posts becomes a new file on disk."""
    _client, _drafts, key = edited_draft(monkeypatch, tmp_path / "planted")
    empty = tmp_path / "empty-drafts"
    empty.mkdir()
    client = client_over(monkeypatch, empty)
    assert client.put(f"{KEYS_ENDPOINT}/{APP}", json={"key": key}).status_code == NO_SUCH_DRAFT
    assert list(empty.iterdir()) == []


def test_a_name_the_pattern_excludes_is_refused_before_the_write_too(
        monkeypatch, tmp_path) -> None:
    """The guard is in `_path`, which both routes go through -- asserted on both, not one."""
    client, _drafts, key = edited_draft(monkeypatch, tmp_path)
    response = save_draft(client, key, "..%5C..%5Csecret")
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == "no draft has that name"


def test_the_drafts_folder_holds_exactly_the_two_files_it_started_with(
        monkeypatch, tmp_path) -> None:
    """Nothing a save does adds a file: one key, one manifest, before and after."""
    drafts = plant(tmp_path)
    before = sorted(path.name for path in drafts.iterdir())
    client = client_over(monkeypatch, drafts)
    saved(client, read_draft(client)["key"])
    assert sorted(path.name for path in drafts.iterdir()) == before
    assert before == [f"{APP}.ground_truth.json", f"{APP}.manifest.json"]
