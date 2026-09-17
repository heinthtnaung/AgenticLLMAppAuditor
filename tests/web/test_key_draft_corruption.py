"""A drafted key that is on disk and is not a usable grading key.

A draft is hand-edited between being written and being promoted, so this is the
least trustworthy input the project has: a file the editor found, opened, and
cannot work with. It is a 400 and never a 404 -- the draft exists, and telling
someone it does not would send them looking for a file sitting in front of them.

**Two faults, two sentences, and the second one was a defect.**
`key_draft_store.read` caught `JSONDecodeError` alone. A three-byte `[]` is
valid json, is not an object, and went straight to `.get()` in `key_promotion`
-- so `GET`, `PUT` and `POST /verify` all answered **500** with
`AttributeError: 'list' object has no attribute 'get'`. The guarded reader's own
docstring said "naming a corrupt one rather than crashing on it", which the
three bytes falsified.

**The message says "not a json object" rather than "not a grading key object",
and that generalisation is the point.** The same reader now opens the manifest
too, and a manifest is not a grading key -- a message naming the wrong kind of
document would send a reader looking for the wrong fault in the right file. The
two sentences are still distinct and each still names the shape it found.

The manifest half -- which is worse, because both writing routes used to write
before they validated -- is `test_key_manifest_corruption.py`. Which name may
reach a filesystem join at all is `test_key_draft_store.py`.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from .corrupt_fixtures import (                              # noqa: E402
    CORRUPT_SHAPES, HALF_SAVED, NOT_AN_OBJECT, ROUTES, UNPARSEABLE, WRITING_ROUTES,
    WRONG_SHAPE, corrupt_key, get_draft, key_file_name, stored_key)
from .key_fixtures import NO_SUCH_DRAFT, REFUSED, planted_client   # noqa: E402

# The shape the wrong-shape message has to name, so a reader is told what the
# file holds rather than only that it is wrong.
SHAPE_OF_A_LIST = "list"


def refusal_through(client, drafts, text: str, route=get_draft) -> str:
    """Corrupt the key, drive one route, and return the sentence it refused with."""
    corrupt_key(drafts, text)
    response = route(client)
    assert response.status_code == REFUSED, response.text
    return response.json()["detail"]


def refusal_for(monkeypatch, tmp_path, text: str, route=get_draft) -> str:
    """The same over a draft planted for this one call.

    Two calls need two `tmp_path` folders -- `plant` writes the tree its anchors
    quote and will not `mkdir` over itself -- so a test wanting two refusals
    uses `refusal_through` against one planted client instead.
    """
    client, drafts = planted_client(monkeypatch, tmp_path)
    return refusal_through(client, drafts, text, route)


# --- every corrupt shape, on every route that reads -----------------------------

@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize("text,message", CORRUPT_SHAPES, ids=[t for t, _ in CORRUPT_SHAPES])
def test_a_corrupt_draft_is_refused_on_every_route_that_reads_it(
        monkeypatch, tmp_path, route, text: str, message: str) -> None:
    """One guarded read serves all three, so all three are driven rather than assumed.

    The table pairs each shape with the sentence it earns, so a test cannot
    assert that a file was refused without saying which of the two faults it was
    refused for.
    """
    assert message in refusal_for(monkeypatch, tmp_path, text, route)


@pytest.mark.parametrize("text,_message", CORRUPT_SHAPES, ids=[t for t, _ in CORRUPT_SHAPES])
def test_a_corrupt_draft_is_not_a_404(monkeypatch, tmp_path, text: str, _message) -> None:
    """The distinction the status carries: the file is there, and a human has to fix it."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    corrupt_key(drafts, text)
    assert get_draft(client).status_code != NO_SUCH_DRAFT


def test_the_refusal_names_the_file_it_could_not_read(monkeypatch, tmp_path) -> None:
    """Two hand-edited files sit beside each other, so a reader is told which one to open."""
    assert key_file_name() in refusal_for(monkeypatch, tmp_path, HALF_SAVED)


def test_the_wrong_shape_refusal_names_the_shape_it_found(monkeypatch, tmp_path) -> None:
    """A message saying only "not an object" leaves a reader guessing what it is instead."""
    assert SHAPE_OF_A_LIST in refusal_for(monkeypatch, tmp_path, NOT_AN_OBJECT[0])


# --- the two sentences stay apart ----------------------------------------------

def test_the_two_corrupt_file_messages_are_different(monkeypatch, tmp_path) -> None:
    """Two faults, two sentences: find the syntax error, or find the wrong shape.

    One message for both would be true and useless. The status is the same 400
    either way, so the sentence is the only thing that tells a reader what they
    are looking for.
    """
    client, drafts = planted_client(monkeypatch, tmp_path)
    unparseable = refusal_through(client, drafts, HALF_SAVED)
    wrong_shape = refusal_through(client, drafts, NOT_AN_OBJECT[0])
    assert UNPARSEABLE in unparseable and WRONG_SHAPE not in unparseable
    assert WRONG_SHAPE in wrong_shape and UNPARSEABLE not in wrong_shape


def test_the_message_does_not_call_a_manifest_a_grading_key(monkeypatch, tmp_path) -> None:
    """The wording generalised when the reader started opening the manifest too.

    Held here, on the key, because this is where "grading key" *would* have been
    correct -- so a message narrowed back to it would pass every test about the
    key and mis-describe every manifest.
    """
    assert "grading key" not in refusal_for(monkeypatch, tmp_path, NOT_AN_OBJECT[0])


# --- and nothing is written on the way out --------------------------------------

@pytest.mark.parametrize("route", list(WRITING_ROUTES.values()), ids=list(WRITING_ROUTES))
@pytest.mark.parametrize("text,_message", CORRUPT_SHAPES, ids=[t for t, _ in CORRUPT_SHAPES])
def test_a_refused_read_never_rewrites_the_file(
        monkeypatch, tmp_path, route, text: str, _message) -> None:
    """Recovery is only possible if the bytes survive, so both writing routes are driven."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    corrupt_key(drafts, text)
    route(client)
    assert stored_key(drafts) == text


# --- non-vacuity ----------------------------------------------------------------

@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
def test_an_intact_draft_is_refused_on_none_of_these_routes(
        monkeypatch, tmp_path, route) -> None:
    """The planted draft is a real key, so every refusal above is about the file."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    assert route(client).status_code != REFUSED
