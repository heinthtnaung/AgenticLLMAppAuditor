"""The two refusals that are about the document, not about the judgement in it.

A draft reaches `promote_key` after a human has been editing it by hand, so a
deleted field and a count left behind are likelier here than anywhere else in
the project. Both are refused before the five content rules in
`test_key_promotion_refusals.py` run, and the ordering is not cosmetic:
`_out_of_order` and `_colliding_pairs` subscript `file`, `line` and `owasp_id`
unguarded, so a malformed entry reaching them raises `KeyError` -- which is not
in `promote_key.EXPECTED_FAILURES` and would surface as a traceback rather than
a sentence. `test_a_malformed_entry_is_reported_rather_than_raised` is that
claim, and it is the reason the check exists.
"""

from drafted_key_fixtures import ANCHORED_ENTRY, fit_key, fit_pin
from keys.key_promotion import ENTRY_FIELDS, refusals

# What a hand edit removes: the fields the checks and the scorer subscript.
JOIN_FIELD = "file"
NARRATIVE_FIELD = "title"

# A count no longer matching the list it counts, which is what deleting an entry
# by hand leaves behind.
WRONG_COUNT = 7

# The two counted pairs, so neither can be dropped without a test noticing.
COUNT_FIELDS = ("finding_count", "expected_surface_count")


def only(said: list[str]) -> str:
    """The one refusal a test expected, failing loudly when another fired beside it."""
    assert len(said) == 1, said
    return said[0]


def key_holding(entry: dict) -> dict:
    """A fit key whose one entry has been replaced by a hand-edited one.

    Not built through `key_drafting.key_document`: that sorts the entries and
    would raise on the missing field itself, which is a fact about the drafter
    and not about the file a human hands to `promote_key`.
    """
    return {**fit_key(), "findings": [entry]}


def without(field: str) -> dict:
    """A corrected entry with one field deleted again."""
    entry = dict(ANCHORED_ENTRY)
    entry.pop(field)
    return entry


# --- an entry missing a field --------------------------------------------------

def test_an_entry_missing_a_field_is_refused_by_id_and_field() -> None:
    """Both halves of what a reader needs: which entry, and what to put back."""
    said = only(refusals(key_holding(without(NARRATIVE_FIELD)), fit_pin()))
    assert ANCHORED_ENTRY["id"] in said and NARRATIVE_FIELD in said


def test_a_malformed_entry_is_reported_rather_than_raised() -> None:
    """An entry with no `file` would crash the order and collision checks."""
    assert only(refusals(key_holding(without(JOIN_FIELD)), fit_pin()))


def test_every_field_the_later_checks_read_is_one_of_them() -> None:
    """The list is what makes the guarantee above true, so it is asserted, not assumed."""
    for field in (JOIN_FIELD, NARRATIVE_FIELD, "line", "owasp_id"):
        assert field in ENTRY_FIELDS


def test_a_malformed_entry_is_the_only_thing_reported() -> None:
    """Nothing after it can be trusted, so a second fault is not listed beside it."""
    key = {**key_holding(without(JOIN_FIELD)), "finding_count": WRONG_COUNT}
    assert only(refusals(key, fit_pin()))


def test_a_complete_entry_is_not_refused() -> None:
    """The off half: it is the missing field that was refused, not the entry."""
    assert refusals(fit_key((ANCHORED_ENTRY,)), fit_pin()) == []


# --- a count that disagrees with what it counts --------------------------------

def test_a_finding_count_that_disagrees_with_the_findings_is_refused() -> None:
    """Every figure computed from the key would be wrong, and nothing else would say so."""
    said = only(refusals({**fit_key(), "finding_count": WRONG_COUNT}, fit_pin()))
    assert "finding_count" in said and str(WRONG_COUNT) in said


def test_a_surface_count_that_disagrees_with_the_surfaces_is_refused() -> None:
    """The same for the list that says whether a surface was missed at all."""
    said = only(refusals({**fit_key(), "expected_surface_count": WRONG_COUNT}, fit_pin()))
    assert "expected_surface_count" in said


def test_both_wrong_counts_are_reported_together() -> None:
    """One run of the command, one list of everything to correct."""
    key = {**fit_key(), "finding_count": WRONG_COUNT,
           "expected_surface_count": WRONG_COUNT}
    said = refusals(key, fit_pin())
    assert len(said) == len(COUNT_FIELDS)


def test_counts_that_match_are_not_refused() -> None:
    """The off half: `key_document` counts its own contents, and nothing is refused."""
    assert refusals(fit_key(), fit_pin()) == []
