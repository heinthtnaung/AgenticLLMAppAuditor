"""A drafted key on disk whose entry fields are all present and one is not a number.

**`test_key_member_shapes.py` one level down.** That file drives a draft whose
*members* are the wrong shape -- `findings: "xy"`, `expected_surfaces: 5` -- and
asking the scorer first closed the whole family. It did not close this one:
`check_key` walked down to the entries and stopped at whether the fields were
**there**, so `"line": "4"` reached `key_promotion._out_of_order` and was a 500
on every route that reads the pair. The generalisation is a member's *presence*
versus its *type*, and this is the type half, on the three routes -- for `line`,
`file` and `id`, the three elements of the sort, and for the optional `line_end`
beside them, whose legal `null` the same check must go on accepting.

**`line_end` is read here and crashed elsewhere.** No route reads it on an
ordinary draft at all: `_colliding_pairs` windows a pair only when two entries
share a file *and* a risk class, and the planted draft holds no such pair. So
what a bad one must be *reported* as belongs here, with the other two fields,
and what it must not *crash* as belongs on a draft that collides --
`test_key_line_end_collision.py`, which builds that pair and drives it.

**What a *body* does with these fields is `test_key_edit_typed_fields.py`**,
split off because it is a different subject: a PUT never reaches a type check at
all, being refused by the anchor rule first. Here the subject is the file on
disk, which every route reads.

The pure halves are `tests/evaluation/test_key_entry_types.py` (the scorer's own
check) and `tests/compare/test_key_promotion_entry_types.py` (what promotion
reports). `scorer_sentence` is imported from `drafted_key_fixtures` rather than
spelled a third time.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from drafted_key_fixtures import scorer_sentence              # noqa: E402

from .corrupt_fixtures import (                               # noqa: E402
    ROUTES, answered, corrupt_entry_field, get_draft)
from .key_fixtures import key_on_disk, planted_client         # noqa: E402

# What a hand edit leaves where a line number belongs, where a file name does,
# and where the end of a construct does.
NOT_A_LINE = {"a string": "4", "null": None, "a list": [4], "a bool": True}
NOT_A_FILE = {"an int": 7, "null": None}
NOT_AN_ID = {"an int": 1, "null": None}
NOT_A_LINE_END = {"a string": "20", "a list": [20], "a bool": True}


def cases(field: str, shapes: dict) -> list[tuple[str, object]]:
    """Every (field, shape) pair for one field, in the form `parametrize` takes."""
    return [(field, shape) for shape in shapes.values()]


def case_ids(field: str, shapes: dict) -> list[str]:
    """One readable id per case, so a failure names the field and the shape."""
    return [f"{field} as {name}" for name in shapes]


# The three required fields, whose wrong-typed shapes are 500s on an ordinary
# draft: all three are elements of the `(file, line, id)` sort. Kept apart from
# `line_end` because the fixture that reads *that* one is different.
REQUIRED_TYPES = (cases("line", NOT_A_LINE) + cases("file", NOT_A_FILE)
                  + cases("id", NOT_AN_ID))
REQUIRED_IDS = (case_ids("line", NOT_A_LINE) + case_ids("file", NOT_A_FILE)
                + case_ids("id", NOT_AN_ID))

# Every wrong-typed shape of all three fields. What must be *reported* does not
# depend on the fixture, so the sentence sweep runs over the lot.
EVERY_WRONG_TYPE = REQUIRED_TYPES + cases("line_end", NOT_A_LINE_END)
EVERY_WRONG_TYPE_ID = REQUIRED_IDS + case_ids("line_end", NOT_A_LINE_END)

# The two `line_end` values a producer really writes. The planted draft carries
# none at all, which is the third legal shape and the one the intact-draft test
# already stands on.
A_REAL_LINE_END = 9
MEANS_ONE_LINE = {"null": None, "an int": A_REAL_LINE_END}
ACCEPTED_IDS = list(MEANS_ONE_LINE)
ACCEPTED_SHAPES = list(MEANS_ONE_LINE.values())

# The routes whose `refusals` describe the file on disk. A PUT reports on the
# body it just settled instead, so its claim here is only that it is not a 500.
READING_ROUTES = {name: call for name, call in ROUTES.items() if name != "PUT"}


# --- the file on disk, on every route that reads it ------------------------------

@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize(("field", "shape"), REQUIRED_TYPES, ids=REQUIRED_IDS)
def test_a_wrong_typed_required_field_is_not_a_server_error_on_any_route(
        monkeypatch, tmp_path, route, field: str, shape: object) -> None:
    """The eighteen measured 500s, driven rather than reasoned about."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    corrupt_entry_field(drafts, field, shape)
    answered(route(client))


@pytest.mark.parametrize("route", list(READING_ROUTES.values()), ids=list(READING_ROUTES))
@pytest.mark.parametrize(("field", "shape"), EVERY_WRONG_TYPE, ids=EVERY_WRONG_TYPE_ID)
def test_the_refusal_reported_is_the_scorers_own_sentence(
        monkeypatch, tmp_path, route, field: str, shape: object) -> None:
    """The point of asking the scorer first: it already knows what is wrong with this.

    All three fields, on the ordinary draft: what a route must *report* does not
    depend on whether any pair of entries collides.
    """
    client, drafts = planted_client(monkeypatch, tmp_path)
    corrupt_entry_field(drafts, field, shape)
    said = answered(route(client))["refusals"]
    assert said == [scorer_sentence(key_on_disk(drafts))]


# --- the off positions -----------------------------------------------------------

def test_an_intact_draft_is_not_reported_for_its_entries(monkeypatch, tmp_path) -> None:
    """The off position: without it, a route reporting something about everything would pass.

    The planted draft's entries carry no `line_end`, so this is the absent case
    of the optional field as well.
    """
    client, _drafts = planted_client(monkeypatch, tmp_path)
    said = answered(get_draft(client))["refusals"]
    assert not any("findings[" in sentence for sentence in said), said


@pytest.mark.parametrize("shape", ACCEPTED_SHAPES, ids=ACCEPTED_IDS)
def test_a_line_end_a_producer_really_writes_is_not_reported(monkeypatch, tmp_path,
                                                             shape: object) -> None:
    """The optional half, over the route a person reads a draft through.

    Both drafts this project has written carry `line_end: null`. A type check
    that refused it would report every real draft as malformed on the page --
    while passing every wrong-shape sweep above.
    """
    client, drafts = planted_client(monkeypatch, tmp_path)
    corrupt_entry_field(drafts, "line_end", shape)
    said = answered(get_draft(client))["refusals"]
    assert not any("findings[" in sentence for sentence in said), said
