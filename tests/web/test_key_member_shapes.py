"""A draft on disk that is a json object and holds a member of the wrong shape.

**The root was guarded; the members were not.** `key_draft_store._json_object`
refuses a file that is not an object and hands everything else to
`key_promotion.refusals`, which walked straight into `findings` -- so a key
holding `findings: "xy"` parsed, passed the guard, and raised
`AttributeError: 'str' object has no attribute 'get'` one frame further in. The
same for `expected_surfaces: 5` (`len(5)`) and, in the manifest beside it, for
`upstream_commit: 12345` (`len()` on an int). Every one of them was a **500**,
on every route that reads the pair.

Six of them, across all three routes. They are all one fault, so they are one
table here rather than six tests: the route matrix is `corrupt_fixtures.ROUTES`,
the same three `test_key_draft_corruption.py` drives for a file that will not
parse at all.

**What is asserted is not "it did not 500".** `refusals` now asks the scorer
first, and the scorer already refuses every malformed `findings` by name -- so
the sentence that comes back must be `check_key`'s own, asked of `check_key`
here rather than transcribed. The pure-function half, and the ordering that
makes it true, is `tests/compare/test_key_promotion_member_shapes.py`.

A *body* holding a malformed `findings` is a different subject with a different
answer -- 400, refused, nothing written -- and is
`test_key_edit_malformed_entries.py`.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import httpx                                                 # noqa: E402

from evaluation.harness import check_key                     # noqa: E402
from guarded_read import refusal_from                        # noqa: E402
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX   # noqa: E402

from .corrupt_fixtures import ROUTES, get_draft              # noqa: E402
from .key_fixtures import APP, OK, key_on_disk, planted_client   # noqa: E402

# Every way a hand edit leaves `findings` something other than a list of
# entries. Each is a shape `check_key` already refuses by name.
MALFORMED_FINDINGS = {"a string": "xy", "a list of numbers": [1, 2],
                      "null": None, "a list holding null": [None]}
FINDINGS_IDS = list(MALFORMED_FINDINGS)
FINDINGS_SHAPES = list(MALFORMED_FINDINGS.values())

# The routes whose `refusals` describe the file on disk. A PUT reports on the
# body it just saved instead, so its claim here is only that it is not a 500.
READING_ROUTES = {name: call for name, call in ROUTES.items() if name != "PUT"}

# The other two members, one in each of the draft's two hand-edited files.
A_SCALAR = 5
NOT_A_COMMIT = 12345

# A path of this file's own, taken off the front of `check_key`'s message. The
# placeholder `_scorer_refusal` uses is its business, not this test's.
ASKED_AS = Path("the key on disk")

# The one refusal every drafted manifest carries, which is what an intact draft
# answers with and nothing else.
PIN_REFUSAL_OPENING = "the manifest names no framework or language"


def _rewrite(path: Path, field: str, shape: object) -> None:
    """Leave one member of a hand-edited file holding `shape`, and the rest intact."""
    document = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**document, field: shape}, indent=2, sort_keys=True),
                    encoding="utf-8")


def key_member(drafts: Path, field: str, shape: object) -> None:
    """A hand edit that leaves the drafted key valid json and one member wrong."""
    _rewrite(drafts / f"{APP}{GROUND_TRUTH_SUFFIX}", field, shape)


def pin_member(drafts: Path, field: str, shape: object) -> None:
    """The same edit to the manifest, which a human is asked to type into."""
    _rewrite(drafts / f"{APP}{MANIFEST_SUFFIX}", field, shape)


def scorer_sentence(key: dict) -> str:
    """The sentence the scorer refuses this key with, its path taken off the front."""
    raised = refusal_from(lambda: check_key(key, ASKED_AS), "check_key")
    assert isinstance(raised, ValueError), f"check_key raised {type(raised).__name__}"
    return str(raised).removeprefix(f"{ASKED_AS} ")


def answered(response: httpx.Response) -> dict:
    """One route's body, insisting it answered rather than crashed or refused."""
    assert response.status_code == OK, f"{response.status_code}: {response.text}"
    return response.json()


# --- findings, on every route that reads the pair -------------------------------

@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize("shape", FINDINGS_SHAPES, ids=FINDINGS_IDS)
def test_a_wrong_shaped_findings_is_not_a_server_error_on_any_route(
        monkeypatch, tmp_path, route, shape: object) -> None:
    """Twelve of the measured 500s, driven rather than reasoned about."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    key_member(drafts, "findings", shape)
    answered(route(client))


@pytest.mark.parametrize("route", list(READING_ROUTES.values()), ids=list(READING_ROUTES))
@pytest.mark.parametrize("shape", FINDINGS_SHAPES, ids=FINDINGS_IDS)
def test_the_refusal_reported_is_the_scorers_own_sentence(
        monkeypatch, tmp_path, route, shape: object) -> None:
    """The point of asking the scorer first: it already knows what is wrong with this."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    key_member(drafts, "findings", shape)
    said = answered(route(client))["refusals"]
    assert said == [scorer_sentence(key_on_disk(drafts))]


# --- expected_surfaces, which the scorer does not read --------------------------

@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
def test_a_scalar_expected_surfaces_is_not_a_server_error_either(
        monkeypatch, tmp_path, route) -> None:
    """`len(5)` in `_miscounted`, one field along from the one the scorer speaks for."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    key_member(drafts, "expected_surfaces", A_SCALAR)
    answered(route(client))


def test_a_scalar_expected_surfaces_is_reported_as_counting_none(monkeypatch,
                                                                 tmp_path) -> None:
    """Named, not merely survived: a reader is told which field to look at."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    key_member(drafts, "expected_surfaces", A_SCALAR)
    said = answered(get_draft(client))["refusals"]
    assert any("expected_surfaces" in sentence for sentence in said), said


# --- and upstream_commit, in the manifest beside it -----------------------------

@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
def test_a_commit_that_is_not_a_string_is_not_a_server_error(monkeypatch, tmp_path,
                                                             route) -> None:
    """The second hand-edited file: `_pin_refusals` called `len()` on whatever it found."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    pin_member(drafts, "upstream_commit", NOT_A_COMMIT)
    answered(route(client))


def test_a_commit_that_is_not_a_string_is_reported_by_name(monkeypatch,
                                                           tmp_path) -> None:
    """The refusal a pin with no usable commit has always earned, now reachable."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    pin_member(drafts, "upstream_commit", NOT_A_COMMIT)
    said = answered(get_draft(client))["refusals"]
    assert any("upstream_commit" in sentence for sentence in said), said


# --- the off position -----------------------------------------------------------

def test_an_intact_draft_reports_only_what_every_draft_reports(monkeypatch,
                                                               tmp_path) -> None:
    """Without this, a route reporting something about everything would pass above."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    said = answered(get_draft(client))["refusals"]
    assert len(said) == 1 and said[0].startswith(PIN_REFUSAL_OPENING)
