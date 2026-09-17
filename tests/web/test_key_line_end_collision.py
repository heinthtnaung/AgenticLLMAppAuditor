"""The one draft shape on which a route reads `line_end` at all, and the check that does it.

**A wrong-typed `line_end` is unreachable on an ordinary draft**, and that is
not a quirk of the fixture -- it is what `key_promotion._colliding_pairs` does.
It windows a pair of entries only when the two share a file *and* a risk class,
and `key_fixtures.DRAFTED_ENTRIES` holds no such pair: K-01 is agent.py/LLM01,
K-03 agent.py/LLM06, K-02 tools.py/LLM06. So `test_key_entry_types.py` can say
what a bad `line_end` must be *reported* as, and nothing there can say what it
must not *crash* as, because nothing there reads it.

This file makes the pair and drives it. Two things come out of that, and the
second is the larger one:

- the `line_end` rows of a 500 sweep stop being rows that look like coverage and
  are not -- they now fail if the type check is removed, which over the ordinary
  draft they did not;
- **`_colliding_pairs` -> `_windows_overlap` -> `line_window` gets its first
  test.** It is a real path a real key reaches, it is the one place a bad
  `line_end` becomes a 500 rather than a reported refusal, and nothing in this
  suite drove it before.

`true` is deliberately not swept below. It is the shape that *returns* rather
than raising -- an inverted window, a start after its end -- so it can never be
a 500 and its claim is a refusal instead. That claim is
`tests/evaluation/test_key_entry_line_end.py`, which asserts the window and the
findings it therefore answers: none.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient                     # noqa: E402

from .corrupt_fixtures import (                               # noqa: E402
    ROUTES, answered, corrupt_entry_field, get_draft, key_file, put_draft)
from .key_fixtures import STORED_ORDER, planted_client        # noqa: E402

# The two `line_end` shapes that reach `line_window`'s `+` and raise there.
CRASHING_LINE_ENDS = {"a string": "20", "a list": [20]}
CRASHING_IDS = list(CRASHING_LINE_ENDS)
CRASHING_SHAPES = list(CRASHING_LINE_ENDS.values())

# The routes that read the pair off disk. A PUT validates the body it just
# settled, and the body `put_draft` sends holds no entries at all -- so no pair
# of *its* entries can collide, and a PUT could not reach `line_window` whatever
# the file says. Its own claim is the last test, spelled out rather than left as
# two sweep rows that could never fail.
READING_ROUTES = {name: call for name, call in ROUTES.items() if name != "PUT"}

# The opening of the sentence a colliding pair earns, and the two entries that
# have to be named in it. Read off the stored order rather than spelled.
COLLISION_SAID = "could be counted against both"
COLLIDING_PAIR = STORED_ORDER[:2]


def make_two_entries_collide(drafts: Path) -> None:
    """Give the second stored entry the risk class of the first, so the pair collides.

    **This is the fixture, and it is deliberately not part of
    `key_fixtures.plant()`.** Folded back into the general one it would give
    every draft in every other file a standing "one finding could be counted
    against both" refusal that has nothing to do with what those files test --
    and folding it in is also how the sweep below would quietly go back to
    driving a shape no route reads.

    Two entries sharing a file and a risk class is exactly what the general
    fixture avoids, and exactly what this file needs.
    """
    path = key_file(drafts)
    key = json.loads(path.read_text(encoding="utf-8"))
    first, second = key["findings"][0], key["findings"][1]
    key["findings"][1] = {**second, "owasp_id": first["owasp_id"]}
    path.write_text(json.dumps(key, indent=2, sort_keys=True), encoding="utf-8")


def a_colliding_draft(monkeypatch: pytest.MonkeyPatch,
                      tmp_path: Path) -> tuple[TestClient, Path]:
    """A client over a draft whose first two entries share a file and a risk class."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    make_two_entries_collide(drafts)
    return client, drafts


# --- the fixture really makes the collision it claims to -------------------------

def test_a_colliding_draft_reaches_the_collision_check(monkeypatch, tmp_path) -> None:
    """The first test of that path, and the non-vacuity guard for the sweep below."""
    client, _drafts = a_colliding_draft(monkeypatch, tmp_path)
    said = answered(get_draft(client))["refusals"]
    assert any(COLLISION_SAID in sentence for sentence in said), said


def test_the_refusal_names_both_entries_that_collide(monkeypatch, tmp_path) -> None:
    """A reader has to be told which two, since fixing it means editing one of them."""
    client, _drafts = a_colliding_draft(monkeypatch, tmp_path)
    said = answered(get_draft(client))["refusals"]
    assert any(all(entry in sentence for entry in COLLIDING_PAIR)
               for sentence in said), said


def test_an_ordinary_draft_has_no_colliding_pair(monkeypatch, tmp_path) -> None:
    """The other half of the claim, and the reason this file exists at all.

    If the planted draft already collided, the tests above would pass while
    proving nothing about the fixture -- and `line_end` would have been reachable
    from `test_key_entry_types.py` all along.
    """
    client, _drafts = planted_client(monkeypatch, tmp_path)
    said = answered(get_draft(client))["refusals"]
    assert not any(COLLISION_SAID in sentence for sentence in said), said


# --- and what a wrong-typed line_end does on it ----------------------------------

@pytest.mark.parametrize("route", list(READING_ROUTES.values()), ids=list(READING_ROUTES))
@pytest.mark.parametrize("shape", CRASHING_SHAPES, ids=CRASHING_IDS)
def test_a_wrong_typed_line_end_is_not_a_server_error_when_two_entries_collide(
        monkeypatch, tmp_path, route, shape: object) -> None:
    """The 500 a bad `line_end` really can be: `_windows_overlap` adds the tolerance to it."""
    client, drafts = a_colliding_draft(monkeypatch, tmp_path)
    corrupt_entry_field(drafts, "line_end", shape)
    answered(route(client))


@pytest.mark.parametrize("route", list(READING_ROUTES.values()), ids=list(READING_ROUTES))
def test_a_colliding_draft_with_a_sound_line_end_still_answers(monkeypatch, tmp_path,
                                                               route) -> None:
    """The off position: a collision on its own is a refusal to report, never a failure."""
    client, drafts = a_colliding_draft(monkeypatch, tmp_path)
    corrupt_entry_field(drafts, "line_end", None)
    answered(route(client))


@pytest.mark.parametrize("shape", CRASHING_SHAPES, ids=CRASHING_IDS)
def test_a_save_answers_over_the_same_draft_and_cannot_reach_that_window(
        monkeypatch, tmp_path, shape: object) -> None:
    """The PUT, stated rather than swept: it validates its own body, not the file.

    The body sent holds no entries, so there is no pair of them to collide and
    nothing reads the `line_end` on disk. Asserted because it is the reason the
    sweep above runs over two routes and not three -- a reader who finds that
    asymmetry should find the answer beside it.
    """
    client, drafts = a_colliding_draft(monkeypatch, tmp_path)
    corrupt_entry_field(drafts, "line_end", shape)
    answered(put_draft(client))
