"""Which fields of a drafted key are frozen, and why that set is the document minus two.

`FROZEN_FIELDS` is a tuple of names, and a name is a thing that can be spelled
wrongly, go stale, or quietly fail to cover a field added later. So it is
asserted against the document `keys/key_drafting.key_document` really writes
rather than against a transcript:

- **Every frozen name is a field a drafted key has.** A typo freezes nothing,
  and nothing would say so -- the guard compares `edited[field]` against
  `held.get(field)`, so a misspelled name is simply absent from both.
- **Everything not frozen is `findings` and `finding_count`, exactly.** That is
  the design: the entries are what a human corrects, the count is derived from
  them, and every other field is either identity, standing, or what the
  extractor found. Stated as an equality so that a fourteenth field added to the
  key document has to be classified here, deliberately, rather than becoming
  editable by default.

`docs/SCHEMAS.md` lists the same thirteen fields, which is why they are read off
the producer here: a third copy is a third thing to keep in step.

**All three lists are read off `key_edit_guard`, which is the module that
declares them.** They used to sit in `key_routes.py` and moved when the guard
was split out; `key_routes` still binds `FROZEN_FIELDS` with `from ... import`
because it serves that one to the page, so reading it off the routes would have
gone on passing while the other two failed -- a re-anchoring that fixes two
names and leaves a third pointing at a re-export is how a test ends up asserting
something about the wrong module. The re-export itself is a fact worth holding,
so it is held once, below, as its own claim.

Nothing here starts a server or writes to the checkout's `grading_keys/drafts/`.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no module")

import key_edit_guard                                         # noqa: E402
import key_routes                                             # noqa: E402
from keys import key_promotion                                # noqa: E402

from .key_fixtures import CORRECTABLE_FIELDS, a_drafted_key   # noqa: E402

# The count a drafted key has to carry, and the list it counts. One pair, and
# the one field a save derives rather than accepts.
EXPECTED_DERIVED_COUNTS = {"finding_count": "findings"}

# What a key document holds, as `docs/SCHEMAS.md` states it: thirteen top-level
# fields, all required. Named so the equality below is read as a claim about the
# schema and not only about two constants agreeing with each other.
KEY_DOCUMENT_FIELD_COUNT = 13


def document_fields(tmp_path) -> set[str]:
    """Every top-level field of the key a real `--draft-key` run writes."""
    return set(a_drafted_key(tmp_path))


def test_a_drafted_key_has_the_thirteen_fields_the_schema_documents(tmp_path) -> None:
    """The floor under everything below: an empty document would satisfy any subset check."""
    assert len(document_fields(tmp_path)) == KEY_DOCUMENT_FIELD_COUNT


def test_every_frozen_field_is_a_field_a_drafted_key_really_has(tmp_path) -> None:
    """A misspelled name freezes nothing and says nothing: it is absent from both sides."""
    assert set(key_edit_guard.FROZEN_FIELDS) <= document_fields(tmp_path)


def test_the_fields_an_edit_may_change_are_exactly_the_entries_and_their_count(
        tmp_path) -> None:
    """Stated as an equality: a fourteenth field must be classified, not editable by default."""
    assert document_fields(tmp_path) - set(key_edit_guard.FROZEN_FIELDS) == CORRECTABLE_FIELDS


def test_no_field_is_both_frozen_and_recomputed() -> None:
    """They would contradict: the identity is restored from disk, the count from the entries."""
    assert set(key_edit_guard.DERIVED_COUNTS) & set(key_edit_guard.FROZEN_FIELDS) == set()


def test_the_recomputed_count_names_the_list_it_counts(tmp_path) -> None:
    """`_miscounted` compares exactly this pair, so a count over the wrong list is a silent refusal."""
    assert key_edit_guard.DERIVED_COUNTS == EXPECTED_DERIVED_COUNTS
    assert set(key_edit_guard.DERIVED_COUNTS.values()) <= document_fields(tmp_path)


def test_every_anchored_field_is_one_an_entry_carries(tmp_path) -> None:
    """A name no entry has would be compared against absence and never differ."""
    entry = a_drafted_key(tmp_path)["findings"][0]
    assert set(key_edit_guard.ANCHORED_FIELDS) <= set(entry)


def test_the_anchor_itself_is_the_field_promotion_requires() -> None:
    """One name across two modules: promotion refuses an entry without it, so it is guarded here."""
    assert key_promotion.ANCHOR_FIELD in key_edit_guard.ANCHORED_FIELDS


def test_the_routes_serve_the_guard_s_own_list_rather_than_a_copy() -> None:
    """The one list `key_routes` re-exports, held so the anchor above cannot drift.

    The page is handed `frozen_fields` in every reply and shows a key's standing
    from it. A second tuple spelled in the routes would satisfy every test above
    -- they read the guard -- while the browser was told about a different set.
    """
    assert key_routes.FROZEN_FIELDS is key_edit_guard.FROZEN_FIELDS
