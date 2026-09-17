"""What verifying a drafted key leaves alone, which is everything that matters.

This is the safety argument for allowing `tool_drafted` with `verified: true` at
all, asserted against the document the route really wrote. Verifying clears one
qualification, `key_unverified`, and no other: the key stays `tool_drafted`, so
`key_ai_drafted` and `key_drafted_by_scored_system` both go on firing and a
verified drafted key can never read as an independent measurement.

**Two ends of one claim, and neither is redundant.**
`tests/compare/test_drafted_key_circularity.py` asks the scorer directly, over a
key built by a fixture; this file reads the key back off disk after the route
wrote it. The scorer could be right about a document this route never produces,
and the route could write a document the scorer never sees -- so both ends are
held, and the join between them is the file on disk.

**The equality over the whole document is the load-bearing one.** Naming the
three fields that move says nothing about a fourth: an implementation that also
reset `finding_count`, dropped an entry or touched `expected_surfaces` would
satisfy every membership check here. Stated as "everything but those three is
what it was", it fails on any of them.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from evaluation.harness import check_key                      # noqa: E402
from evaluation.scorer import score_app                       # noqa: E402
from evaluation_fixtures import findings_document, surfaces_document   # noqa: E402
from keys.grading_keys import TOOL_DRAFTED                    # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    APP, ENTRY_COUNT, STORED_ORDER, entry_ids, key_on_disk, planted_client)
from .key_verify_fixtures import CHECKED_BY, claimed          # noqa: E402

# The three fields a recorded check is allowed to move. Everything else in the
# document is compared before against after.
CLAIM_FIELDS = ("verified", "verified_by", "verified_date")

# The qualifications a key's own standing earns, spelled as the scorer publishes
# them rather than imported, so a rename in `scorer.py` fails here loudly.
AI_DRAFTED = "key_ai_drafted"
SCORED_SYSTEM = "key_drafted_by_scored_system"
UNVERIFIED = "key_unverified"


def qualifications_for(key: dict) -> set[str]:
    """Everything a scoring run would attach to a figure bounded by this key."""
    return set(score_app(APP, key, findings_document(),
                         surfaces_document())["qualifications"])


def without_the_claim(key: dict) -> dict:
    """The key with the three fields a check moves taken out."""
    return {field: value for field, value in key.items() if field not in CLAIM_FIELDS}


# --- what it does not touch ---------------------------------------------------

def test_the_source_is_untouched_by_the_whole_operation(monkeypatch, tmp_path) -> None:
    """The safety argument's first half: a checked draft is still a drafted key."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    assert claimed(client)["key"]["source"] == TOOL_DRAFTED
    assert key_on_disk(drafts)["source"] == TOOL_DRAFTED


def test_the_entries_are_untouched_by_the_whole_operation(monkeypatch, tmp_path) -> None:
    """Signing off a key is not editing it: nothing it claims about the app moves."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claimed(client)
    stored = key_on_disk(drafts)
    assert entry_ids(stored) == STORED_ORDER
    assert stored["finding_count"] == ENTRY_COUNT


def test_everything_but_the_three_fields_is_what_it_was(monkeypatch, tmp_path) -> None:
    """The equality that makes the two above more than samples of a bigger document."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    before = key_on_disk(drafts)
    claimed(client)
    assert without_the_claim(key_on_disk(drafts)) == without_the_claim(before)


def test_the_three_fields_really_did_move(monkeypatch, tmp_path) -> None:
    """Guard on the equality above: it would also hold if the route wrote nothing."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claimed(client)
    stored = key_on_disk(drafts)
    assert stored["verified"] is True
    assert stored["verified_by"] == CHECKED_BY


# --- and what that means for a figure -----------------------------------------

def test_the_verified_draft_is_a_key_the_scorer_accepts(monkeypatch, tmp_path) -> None:
    """The route writes a legal document, asked of the gate a scoring run applies first."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claimed(client)
    stored = key_on_disk(drafts)
    assert check_key(stored, tmp_path / "read-back") is stored


def test_the_verified_draft_still_carries_both_drafting_warnings(
        monkeypatch, tmp_path) -> None:
    """The entire reason the pairing is allowed, over the document this route wrote."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claimed(client)
    said = qualifications_for(key_on_disk(drafts))
    assert AI_DRAFTED in said
    assert SCORED_SYSTEM in said


def test_the_claim_clears_the_unverified_warning_and_no_other(
        monkeypatch, tmp_path) -> None:
    """Both directions over the whole list: one qualification goes, none arrives."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    before = qualifications_for(key_on_disk(drafts))
    claimed(client)
    after = qualifications_for(key_on_disk(drafts))
    assert before - after == {UNVERIFIED}
    assert after - before == set()


def test_the_unverified_warning_was_there_to_clear(monkeypatch, tmp_path) -> None:
    """Non-vacuity: a scorer that never attached it would satisfy the test above."""
    _client, drafts = planted_client(monkeypatch, tmp_path)
    assert UNVERIFIED in qualifications_for(key_on_disk(drafts))
