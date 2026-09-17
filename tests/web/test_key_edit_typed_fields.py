"""A *body* carrying a retyped `line`, and the two rules that already cover it.

Split from `test_key_entry_types.py`, whose subject is the drafted key on disk
and the three routes that read it. This one is the other direction -- what a PUT
may send -- and it is a different subject with a different answer, because the
save path never reaches a type check at all.

**It is covered twice, and only one of the two is design.**

- A body that *sets* `file` or `line` is refused by `key_edit_guard`'s anchor
  rule, because both are in `ANCHORED_FIELDS`: an anchor is a quotation of
  source the browser has never read. `id` is refused by the same function for a
  different reason -- `anchors_moved` keys its before-map on `id`, so an entry
  whose id changed is an entry the draft never held, and appending one is what
  that clause exists to stop. Both rules were written for provenance and happen
  to cover types, which is an **accident** -- so the last test states it as an
  assertion. A change to `ANCHORED_FIELDS` would open a route nothing else
  guards, and nothing but that test would say so.
- A body that merely *carries back* the value already on disk is not refused,
  and must not be: a person reading a hand-edited draft and saving a corrected
  title cannot be made to fix the line first. That path reaches `settled`'s
  sort, where `_line` coerces a non-int to 0 rather than raising -- **by
  design**, and its docstring says so. The refusals come back in the reply.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import key_edit_guard                                         # noqa: E402
from drafted_key_fixtures import scorer_sentence              # noqa: E402
from evaluation.harness import TYPED_ENTRY_FIELDS             # noqa: E402

from .corrupt_fixtures import answered, corrupt_entry_field   # noqa: E402
from .key_fixtures import (                                   # noqa: E402
    ENTRY_COUNT, REFUSED, STORED_ORDER, entry_ids, entry_named, key_on_disk,
    planted_client, read_draft, save_draft)

# The entry a test edits -- `findings[0]` as the draft is stored, read off the
# fixture's own order rather than spelled, so a re-sorted draft cannot leave a
# test editing one entry and asserting about another.
FIRST_ENTRY = STORED_ORDER[0]

# A line number typed as text, and an id typed as a number -- what a page bug or
# a hand-built request sends. The id is the shape a *model* can produce too,
# which is why the drafter bounds it as well: `tests/compare/test_drafted_key_ids.py`.
A_TEXT_LINE = "4"
A_NUMERIC_ID = 1

# The field `anchors_moved` builds its before-map from, so a body that changes
# it names an entry the draft never held. Spelled once, because the test below
# is the only place the second half of the accident is written down.
THE_MAP_IS_KEYED_ON = "id"

# The opening of the sentence a typed `file`, `line` or `id` in a body earns. Spelled
# in full by `test_key_edit_anchors.py`, which owns that rule; matched by its
# middle here so the two do not both have to be reworded together.
ANCHOR_REFUSAL = "add or move a file, line or anchor"


def test_a_body_that_retypes_a_line_is_refused_as_an_invented_anchor(monkeypatch,
                                                                     tmp_path) -> None:
    """The PUT never reaches a type check, because `line` is a field it may not move at all."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    key = read_draft(client)["key"]
    entry_named(key, FIRST_ENTRY)["line"] = A_TEXT_LINE
    response = save_draft(client, key)
    assert response.status_code == REFUSED, response.text
    assert ANCHOR_REFUSAL in response.json()["detail"]


def test_that_refusal_leaves_the_draft_exactly_as_it_was(monkeypatch, tmp_path) -> None:
    """A refused save writes nothing, so the line on disk is still the one read off source."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    key = read_draft(client)["key"]
    held = entry_named(key, FIRST_ENTRY)["line"]
    entry_named(key, FIRST_ENTRY)["line"] = A_TEXT_LINE
    save_draft(client, key)
    stored = key_on_disk(drafts)
    assert len(stored["findings"]) == ENTRY_COUNT
    assert entry_named(stored, FIRST_ENTRY)["line"] == held


def test_the_page_can_still_read_a_text_line_and_save_it_back(monkeypatch,
                                                              tmp_path) -> None:
    """The half that is by design: a hand-edited draft stays correctable.

    The body carries the same text line the file holds, so the anchor rule sees
    nothing moved and `settled` goes on to sort the entries.
    `key_edit_guard._line` coerces for the sort rather than raising, so this is
    a 200 that reports the entry -- not a 500 that loses the draft.
    """
    client, drafts = planted_client(monkeypatch, tmp_path)
    corrupt_entry_field(drafts, "line", A_TEXT_LINE)
    said = answered(save_draft(client, read_draft(client)["key"]))["refusals"]
    assert said == [scorer_sentence(key_on_disk(drafts))]


def test_a_body_that_renumbers_an_id_is_refused_as_an_entry_the_draft_never_held(
        monkeypatch, tmp_path) -> None:
    """The third typed field, refused by the other clause of the same rule.

    Not because `id` is anchored -- it is not -- but because it is the key
    `anchors_moved` builds its before-map from, so changing it makes the entry
    unknown. The sentence is the same one; the reason is not.
    """
    client, _drafts = planted_client(monkeypatch, tmp_path)
    key = read_draft(client)["key"]
    entry_named(key, FIRST_ENTRY)["id"] = A_NUMERIC_ID
    response = save_draft(client, key)
    assert response.status_code == REFUSED, response.text
    assert ANCHOR_REFUSAL in response.json()["detail"]


def test_that_refusal_leaves_every_entry_under_the_id_it_had(monkeypatch,
                                                             tmp_path) -> None:
    """A renumbered entry saved would be ground truth under a label nobody chose."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    key = read_draft(client)["key"]
    entry_named(key, FIRST_ENTRY)["id"] = A_NUMERIC_ID
    save_draft(client, key)
    assert entry_ids(key_on_disk(drafts)) == STORED_ORDER


def test_the_body_is_safe_by_accident_and_this_is_what_the_accident_is() -> None:
    """Every typed field is one a body may not move, by one rule or the other.

    Asserted as a subset rather than left as prose: a change to either half --
    `ANCHORED_FIELDS` losing a name, or `anchors_moved` keying its map on
    something else -- would open this route to a body the type check never sees,
    and nothing else would fail.
    """
    may_not_move = set(key_edit_guard.ANCHORED_FIELDS) | {THE_MAP_IS_KEYED_ON}
    assert set(TYPED_ENTRY_FIELDS) <= may_not_move
