"""What recording a human check writes: three fields, a server date, and a file.

`POST /api/keys/{app}/verify` is the one route that changes a drafted key's
standing. Before 2026-09-16 there was nothing to record: `harness.check_key`
refused `tool_drafted` with `verified: true`, so the only way to say a human had
read the entries was to edit `source` -- which erases
`key_drafted_by_scored_system`, the warning that actually matters. The pairing is
legal now and this route is how the claim is made.

**The date is the server's, and the clock is a seam.** `key_verify_route` calls
`run_record.today` by name, so the tests that care about the stamp point that at
a fixed date; the one that cares it is really today brackets the call with the
real clock rather than trusting a single sample. A `verified_date` in the
request body is ignored, and that is asserted rather than assumed -- pydantic's
default is to drop unknown fields, which is a default and not a promise.

Four files, one claim each, not one file split to a line count. What this route
*leaves alone* is `test_key_verify_standing.py`; which names it turns down is
`test_key_verify_refusals.py`; which draft it may touch and which folder it may
write into is `test_key_verify_confinement.py`. This one is only about what a
recorded check writes.

Nothing here writes to the checkout's own `grading_keys/drafts/`. The draft, its
manifest and the tree its anchors quote are built under `tmp_path`.
"""

import json

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from run_record import today                                  # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    APP, HUMAN_PIN_FIELDS, key_on_disk, planted_client, read_draft)
from .key_verify_fixtures import (                            # noqa: E402
    BACKDATED, CHECKED_BY, FIXED_DATE, PADDED_CHECKED_BY, claimed, drafts_listing,
    freeze_clock, verified_fields)

# What one reply carries, as a whole set. The same envelope `GET /api/keys/{app}`
# answers with, so the page needs one parser and not one per endpoint.
VERIFY_REPLY_KEYS = {"app", "key", "frozen_fields", "refusals"}

# The two files a drafted app has on disk, in the order a sorted listing gives
# them. Named so a route that wrote a third -- a backup, a lock -- is caught.
DRAFT_KEY_FILE = f"{APP}.ground_truth.json"
DRAFT_FILES = [DRAFT_KEY_FILE, f"{APP}.manifest.json"]

# How many refusals a drafted manifest always carries, and the word that names
# the one thing a draft cannot supply for itself.
DRAFTED_PIN_REFUSAL_COUNT = 1
PIN_REFUSAL_WORD = "framework"


# --- what the reply says ------------------------------------------------------

def test_a_recorded_check_sets_the_three_fields(monkeypatch, tmp_path) -> None:
    """The whole feature: one act, three fields, and a name that is a claim not an identity."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    freeze_clock(monkeypatch)
    assert verified_fields(claimed(client)["key"]) == (True, CHECKED_BY, FIXED_DATE)


def test_the_draft_was_unverified_before_the_claim(monkeypatch, tmp_path) -> None:
    """Non-vacuity under everything else: a key born verified would satisfy all of it."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    assert verified_fields(read_draft(client)["key"]) == (False, None, None)


def test_the_reply_is_the_same_envelope_the_draft_is_read_with(
        monkeypatch, tmp_path) -> None:
    """Named as a whole set: a page with two shapes to parse grows two ways to be wrong."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    reply = claimed(client)
    assert set(reply) == VERIFY_REPLY_KEYS
    assert reply["app"] == APP


def test_a_padded_name_is_stored_stripped(monkeypatch, tmp_path) -> None:
    """A browser field carries whatever was typed; the stored claim names a person."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    assert claimed(client, PADDED_CHECKED_BY)["key"]["verified_by"] == CHECKED_BY


# --- the date is the server's -------------------------------------------------

def test_the_date_comes_from_the_server_clock(monkeypatch, tmp_path) -> None:
    """Pointed at a fixed date, the stamp is that date -- so it is read, not invented."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    freeze_clock(monkeypatch)
    assert claimed(client)["key"]["verified_date"] == FIXED_DATE


def test_a_date_sent_by_the_client_cannot_land(monkeypatch, tmp_path) -> None:
    """The backdating case: a claim's date is when a person looked, not what they typed."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    freeze_clock(monkeypatch)
    stamped = claimed(client, verified_date=BACKDATED)["key"]["verified_date"]
    assert stamped == FIXED_DATE
    assert stamped != BACKDATED


def test_a_backdated_claim_does_not_reach_disk_either(monkeypatch, tmp_path) -> None:
    """Asserted on the file, because the reply could be right and the write wrong."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    freeze_clock(monkeypatch)
    claimed(client, verified_date=BACKDATED)
    assert key_on_disk(drafts)["verified_date"] == FIXED_DATE


def test_an_unfrozen_clock_stamps_today(monkeypatch, tmp_path) -> None:
    """Guard on the three above: a route reading a clock nobody moves is still wrong.

    Bracketed rather than sampled once, so a run crossing midnight UTC fails
    nothing: the stamp has to be one of the two dates the real clock read either
    side of the call.
    """
    client, _drafts = planted_client(monkeypatch, tmp_path)
    before = today()
    stamped = claimed(client)["key"]["verified_date"]
    assert stamped in {before, today()}


# --- what lands on disk -------------------------------------------------------

def test_the_file_on_disk_holds_the_recorded_check(monkeypatch, tmp_path) -> None:
    """A reply that agreed with nothing written would lose the claim on the next read."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    freeze_clock(monkeypatch)
    claimed(client)
    assert verified_fields(key_on_disk(drafts)) == (True, CHECKED_BY, FIXED_DATE)


def test_the_file_is_written_the_way_every_other_document_here_is(
        monkeypatch, tmp_path) -> None:
    """Two spaces, sorted keys, one trailing newline -- so a draft stays diffable."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claimed(client)
    written = (drafts / DRAFT_KEY_FILE).read_text(encoding="utf-8")
    assert written == json.dumps(key_on_disk(drafts), indent=2, sort_keys=True) + "\n"


def test_the_drafts_folder_still_holds_exactly_its_two_files(
        monkeypatch, tmp_path) -> None:
    """No backup, no second copy: the claim is recorded in the draft itself."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claimed(client)
    assert drafts_listing(drafts) == DRAFT_FILES


# --- what promotion would still say -------------------------------------------

def test_the_reply_reports_what_promotion_would_still_say(monkeypatch, tmp_path) -> None:
    """A recorded check fixes nothing about the manifest, and the page is told so."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    reply = claimed(client)
    assert len(reply["refusals"]) == DRAFTED_PIN_REFUSAL_COUNT
    assert PIN_REFUSAL_WORD in reply["refusals"][0]


def test_a_draft_a_human_has_finished_is_verified_with_no_refusal_left(
        monkeypatch, tmp_path) -> None:
    """Non-vacuity for the test above, and the state a promotion is really run from."""
    client, _drafts = planted_client(monkeypatch, tmp_path, pin_fields=HUMAN_PIN_FIELDS)
    reply = claimed(client)
    assert reply["refusals"] == []
    assert reply["key"]["verified"] is True
