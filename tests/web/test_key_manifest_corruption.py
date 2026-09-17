"""A corrupt `<app>.manifest.json`, and the order a route does its work in.

This is the worse half of the same fault, and it is worse for two reasons.

**The manifest is hand-edited by design, not by accident.**
`key_promotion.GRADED_PIN_FIELDS` says a human types `framework` and `language`
into it -- a drafted pin cannot supply either -- so a truncated manifest is an
ordinary state for a draft to be in, reached by the very edit the workflow asks
for. `key_draft_store.validate` read it with a bare `json.loads`.

**And both writing routes wrote before they validated.** Measured on the old
code, with a good key and `'{"upstream_commit": '` for a manifest:

    verify -> 500
    on disk after the 500: verified: true, verified_by: "A Reviewer"
    retry  -> 400  "demo is already verified by A Reviewer"

A failed request that succeeded, could not be repeated, and left a recorded
human claim nobody made -- on the one route whose whole job is to record that a
human looked. **That is what the last section of this file holds**, and it is
the reason a test about ordering is not the same test as one about a guard: a
`_json_object` that refuses perfectly still leaves the claim on disk if the
write happens first. Both mutations are listed in the report for that reason.

The key half is `test_key_draft_corruption.py`; the two share
`corrupt_fixtures.py` so they cannot drift about what "corrupt" means.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from .corrupt_fixtures import (                              # noqa: E402
    AN_EDIT, CORRUPT_SHAPES, HALF_SAVED, NOT_AN_OBJECT, ROUTES, WRITING_ROUTES,
    corrupt_pin, get_draft, key_file_name, pin_file_name, verify_draft)
from .key_fixtures import (                                  # noqa: E402
    APP, ENTRY_COUNT, OK, REFUSED, STORED_ORDER, entry_ids, key_on_disk,
    planted_client, plant, client_over)
from .key_verify_fixtures import CHECKED_BY, claim, verified_fields   # noqa: E402

# The manifest a person is halfway through typing the framework into. Not a
# hostile input: this is the edit `promote_key.py` asks them to make.
HALF_TYPED_PIN = '{"upstream_commit": '

# What an untouched draft says about being checked, so "the refusal left nothing
# behind" is an equality and not an absence.
UNCLAIMED = (False, None, None)


def with_corrupt_pin(monkeypatch, tmp_path, text: str = HALF_TYPED_PIN):
    """A planted draft whose key is intact and whose manifest a hand edit broke."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    corrupt_pin(drafts, text)
    return client, drafts


# --- every corrupt shape, on every route that validates -------------------------

@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize("text,message", CORRUPT_SHAPES, ids=[t for t, _ in CORRUPT_SHAPES])
def test_a_corrupt_manifest_is_refused_on_every_route(
        monkeypatch, tmp_path, route, text: str, message: str) -> None:
    """The same two faults, in the other file, through `validate` rather than `read`."""
    client, _drafts = with_corrupt_pin(monkeypatch, tmp_path, text)
    response = route(client)
    assert response.status_code == REFUSED, response.text
    assert message in response.json()["detail"]


def test_the_refusal_names_the_manifest_and_not_the_key(monkeypatch, tmp_path) -> None:
    """Two hand-edited files sit beside each other and only one of them is broken.

    Naming the wrong one sends a reader to a file that is perfectly fine, which
    is worse than naming neither: they would go looking for a fault that is not
    there.
    """
    client, _drafts = with_corrupt_pin(monkeypatch, tmp_path)
    detail = get_draft(client).json()["detail"]
    assert pin_file_name() in detail
    assert key_file_name() not in detail


def test_the_key_beside_it_is_still_perfectly_readable(monkeypatch, tmp_path) -> None:
    """Non-vacuity: the refusal is the manifest's, so the key must not be at fault too."""
    _client, drafts = with_corrupt_pin(monkeypatch, tmp_path)
    assert entry_ids(key_on_disk(drafts)) == STORED_ORDER


# --- a refused request leaves nothing behind ------------------------------------

@pytest.mark.parametrize("text,_message", CORRUPT_SHAPES, ids=[t for t, _ in CORRUPT_SHAPES])
def test_a_refused_verify_records_no_claim(
        monkeypatch, tmp_path, text: str, _message) -> None:
    """The assertion with teeth. A 500 used to leave `verified: true` on disk.

    Stated as the whole tuple rather than `verified is False`, so a route that
    wrote a name and a date while failing to set the flag would fail here too.
    """
    client, drafts = with_corrupt_pin(monkeypatch, tmp_path, text)
    assert claim(client, CHECKED_BY).status_code == REFUSED
    assert verified_fields(key_on_disk(drafts)) == UNCLAIMED


def test_the_refused_verify_can_simply_be_repeated(monkeypatch, tmp_path) -> None:
    """The sharpest form: the failed call left no trace, so fixing the file is enough.

    On the old code the retry answered "already verified by A Reviewer" -- the
    claim from the request that had failed. A refusal a caller cannot recover
    from by fixing what was wrong is worse than a crash, because it looks like
    a rule.
    """
    client, drafts = with_corrupt_pin(monkeypatch, tmp_path)
    assert claim(client, CHECKED_BY).status_code == REFUSED
    corrupt_pin(drafts, '{"upstream_commit": "' + "c" * 40 + '"}')
    accepted = claim(client, CHECKED_BY)
    assert accepted.status_code == OK, accepted.text
    assert accepted.json()["key"]["verified_by"] == CHECKED_BY


@pytest.mark.parametrize("text,_message", CORRUPT_SHAPES, ids=[t for t, _ in CORRUPT_SHAPES])
def test_a_refused_save_rewrites_no_entries(
        monkeypatch, tmp_path, text: str, _message) -> None:
    """The save side of the same ordering: `AN_EDIT` would have emptied the findings."""
    client, drafts = with_corrupt_pin(monkeypatch, tmp_path, text)
    response = client.put(f"/api/keys/{APP}", json=AN_EDIT)
    assert response.status_code == REFUSED
    stored = key_on_disk(drafts)
    assert entry_ids(stored) == STORED_ORDER
    assert stored["finding_count"] == ENTRY_COUNT


@pytest.mark.parametrize("route", list(WRITING_ROUTES.values()), ids=list(WRITING_ROUTES))
def test_the_whole_key_is_byte_for_byte_what_it_was(
        monkeypatch, tmp_path, route) -> None:
    """Said over the whole document, so a field nobody thought to name cannot move either."""
    client, drafts = with_corrupt_pin(monkeypatch, tmp_path)
    before = key_on_disk(drafts)
    route(client)
    assert key_on_disk(drafts) == before


# --- non-vacuity: the same requests work with an intact manifest ----------------

@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
def test_an_intact_manifest_refuses_none_of_these_requests(
        monkeypatch, tmp_path, route) -> None:
    """Every refusal above is the manifest's fault, not the request's."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    assert route(client).status_code != REFUSED


def test_a_verify_over_an_intact_manifest_does_record_the_claim(
        monkeypatch, tmp_path) -> None:
    """The floor under the whole file: the route can write, so "it wrote nothing" means something."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    assert verify_draft(client).status_code == OK
    assert verified_fields(key_on_disk(drafts))[:2] == (True, CHECKED_BY)


def test_an_absent_manifest_is_an_ordinary_draft_and_not_a_refusal(
        monkeypatch, tmp_path) -> None:
    """A missing pin answers `{}` and is reported as refusals, never as a broken file.

    The distinction `validate` draws: *absent* is a state a draft is allowed to
    be in, *corrupt* is a file someone has to open. Reading them the same way
    would make a draft with no manifest impossible to correct.
    """
    drafts = plant(tmp_path)
    (drafts / pin_file_name()).unlink()
    client = client_over(monkeypatch, drafts)
    response = get_draft(client)
    assert response.status_code == OK, response.text
    assert response.json()["refusals"] != []


def test_the_corrupt_manifest_is_not_reported_as_a_promotion_refusal(
        monkeypatch, tmp_path) -> None:
    """Guard on the test above: a broken pin must not be answered 200 with a note.

    `refusals` is advice a page renders and a person may ignore; it is the wrong
    channel for "this file will not open". The two are told apart by the status.
    """
    client, _drafts = with_corrupt_pin(monkeypatch, tmp_path, NOT_AN_OBJECT[0])
    assert get_draft(client).status_code == REFUSED
    client, _drafts = with_corrupt_pin(monkeypatch, tmp_path / "second", HALF_SAVED)
    assert get_draft(client).status_code == REFUSED
