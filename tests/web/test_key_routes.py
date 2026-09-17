"""What the drafted-key routes list, what they hand back, and what they refuse to find.

`web/key_routes.py` reads `grading_keys/drafts/` and nothing else. That is the
whole security argument for the feature: `grading_keys/` holds the answers this
tool is scored against, and an unauthenticated endpoint that could rewrite them
would let anyone reaching the port rewrite the project's own measurements. So
the first thing asserted here is *which folder* the routes read, and the second
is that a name arriving in the URL never becomes a path of the caller's choosing.

**A name that is not a draft is `test_key_draft_store.py`.** That module owns
the filesystem join, the folder it is joined against, and every refusal that
comes out of it -- a name the pattern excludes, a name nobody drafted, a draft
that will not parse, a draft that parses to something that is not a key. The
tests follow the module rather than the URL they happen to arrive on. This file
is about what the routes *answer* when the name is a real one.

The refusals a draft carries are read from `key_promotion`, not from a copy:
this file asserts that the one a real drafted manifest always has is reported,
and that a manifest a human has finished carries none.

Nothing here writes to the checkout's own `grading_keys/drafts/`. The key,
the manifest and the tree are built under `tmp_path` by `key_fixtures.py`.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi import FastAPI                                   # noqa: E402

import api                                                    # noqa: E402
import key_edit_guard                                         # noqa: E402
from keys import key_drafting                                 # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    APP, ENTRY_COUNT, HUMAN_PIN_FIELDS, KEYS_ENDPOINT, OK, OTHER_APP,
    STORED_ORDER, SURFACE_COUNT, client_over, entry_ids, key_on_disk, plant,
    planted_client, read_draft)

# What one drafted key's reply carries, as a whole set: a reply that lost
# `frozen_fields` would leave the page with no way to show what it may not edit.
DRAFT_REPLY_KEYS = {"app", "key", "frozen_fields", "refusals"}

# The one refusal a real drafted key always carries. `key_store.manifest` cannot
# write a framework or a language -- they are human judgements about the app --
# so this is the state the editor exists to be usable in, not an edge case.
DRAFTED_PIN_REFUSAL = ("the manifest names no framework or language; both are human "
                       "judgements about the app and a draft cannot supply them")


# The three paths the feature adds, as starlette stores them, and the methods
# each one answers. `PUT` on the collection is deliberately absent: a key is
# corrected by name, never posted as a set. The third is the verify route, and
# it is `POST` on a path of its own rather than a field of the `PUT` -- the save
# freezes `verified` along with `source`, so recording a check has to be a
# different act or the pair could travel together.
#
# An exact equality, not a subset: that strictness is what caught the verify
# route being added and unasserted, and it is also what would catch a route
# gaining `DELETE` on a drafted key.
DRAFT_PATHS = {
    f"{KEYS_ENDPOINT}": {"GET"},
    f"{KEYS_ENDPOINT}/{{app_name}}": {"GET", "PUT"},
    f"{KEYS_ENDPOINT}/{{app_name}}/verify": {"POST"},
}


def methods_of(app: FastAPI) -> dict:
    """Every path one application routes under `/api/keys`, and the methods it answers.

    Accumulated rather than built by comprehension: one path registered with two
    methods is two route objects, and a dict comprehension keeps only the last.
    """
    found: dict = {}
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith(KEYS_ENDPOINT):
            found.setdefault(path, set()).update(set(route.methods) - {"HEAD"})
    return found


# --- attached to the application that is actually served ----------------------

def test_the_drafted_key_routes_are_on_the_application_the_server_runs() -> None:
    """Every other test here builds its own application, so none of them says this one.

    `api.py` assembles the routers; a feature nobody registered would leave all
    of them green and the endpoint absent from the running server.
    """
    assert methods_of(api.app) == DRAFT_PATHS


# --- which folder is read -----------------------------------------------------

def test_the_listing_and_the_read_both_answer_from_the_folder_the_store_was_given(
        monkeypatch, tmp_path) -> None:
    """One binding, two routes, asserted together -- because it was briefly two bindings.

    `key_draft_store` binds `DRAFTED_KEYS_DIR` with `from ... import`, so
    rebinding `key_drafting`'s copy -- which `tests/compare_arms_fixtures.py`
    does, for drafting -- leaves these routes reading `grading_keys/drafts/` in
    the checkout, where real drafts live. Here the source module's copy is
    pointed somewhere else entirely, and both routes still answer from the
    folder the store was given.

    The listing used to glob a *second* binding in `key_routes`, and a fixture
    redirecting one of the two listed a temporary folder while writing through
    the other. That is why the two halves are asserted in one test: they were
    once capable of disagreeing. Which module may bind the name at all is
    `test_key_draft_store.py`.
    """
    somewhere_else = tmp_path / "not-the-drafts"
    somewhere_else.mkdir()
    monkeypatch.setattr(key_drafting, "DRAFTED_KEYS_DIR", somewhere_else)
    client = client_over(monkeypatch, plant(tmp_path))
    assert client.get(KEYS_ENDPOINT).json()["drafts"] == [APP]
    assert read_draft(client)["key"]["app"] == APP


# --- the listing --------------------------------------------------------------

def test_every_drafted_key_on_disk_is_listed_by_the_app_it_was_drafted_for(
        monkeypatch, tmp_path) -> None:
    """Two drafts, both named, sorted -- so a list of one cannot pass by being right once.

    The whole list is asserted rather than membership, which is also what says a
    `.manifest.json` is not a draft: one sits beside each key on disk, and a
    glob over the wrong suffix would offer a pin as a key to correct.
    """
    drafts = plant(tmp_path)
    plant(tmp_path / "second", OTHER_APP)
    for written in (tmp_path / "second" / "drafts").iterdir():
        written.rename(drafts / written.name)
    client = client_over(monkeypatch, drafts)
    assert client.get(KEYS_ENDPOINT).json()["drafts"] == sorted([APP, OTHER_APP])


def test_the_listing_names_what_an_edit_may_not_touch(monkeypatch, tmp_path) -> None:
    """The page shows a key's standing as a fact, so the endpoint has to say which fields those are."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    assert client.get(KEYS_ENDPOINT).json()["frozen_fields"] == list(
        key_edit_guard.FROZEN_FIELDS)


def test_a_folder_that_was_never_created_lists_nothing_rather_than_failing(
        monkeypatch, tmp_path) -> None:
    """No draft has ever been made on this machine, which is normal and not an error."""
    client = client_over(monkeypatch, tmp_path / "never-drafted")
    response = client.get(KEYS_ENDPOINT)
    assert response.status_code == OK
    assert response.json()["drafts"] == []


# --- one draft ----------------------------------------------------------------

def test_one_draft_comes_back_exactly_as_it_sits_on_disk(monkeypatch, tmp_path) -> None:
    """A view, not a twelfth artifact: the editor corrects the document the drafter wrote."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    assert read_draft(client)["key"] == key_on_disk(drafts)


def test_the_draft_comes_back_with_its_entries_and_its_surfaces(
        monkeypatch, tmp_path) -> None:
    """Guard on the test above: two empty documents are equal, so the counts are named."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    key = read_draft(client)["key"]
    assert key["finding_count"] == ENTRY_COUNT
    assert entry_ids(key) == STORED_ORDER
    assert key["expected_surface_count"] == SURFACE_COUNT


def test_the_reply_carries_the_app_the_frozen_fields_and_the_refusals(
        monkeypatch, tmp_path) -> None:
    """Named as a whole set: a reply that lost one leaves the page with nothing to show."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    reply = read_draft(client)
    assert set(reply) == DRAFT_REPLY_KEYS
    assert reply["app"] == APP
    assert reply["frozen_fields"] == list(key_edit_guard.FROZEN_FIELDS)


# --- what promotion would still say -------------------------------------------

def test_a_drafted_manifest_carries_the_one_refusal_a_draft_cannot_fix(
        monkeypatch, tmp_path) -> None:
    """Reported, never enforced: gating the save on this would make a draft uncorrectable."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    assert read_draft(client)["refusals"] == [DRAFTED_PIN_REFUSAL]


def test_a_manifest_a_human_has_finished_carries_no_refusal_at_all(
        monkeypatch, tmp_path) -> None:
    """Non-vacuity: the list above must be able to be empty, or reporting it says nothing."""
    client, _drafts = planted_client(monkeypatch, tmp_path, pin_fields=HUMAN_PIN_FIELDS)
    assert read_draft(client)["refusals"] == []
