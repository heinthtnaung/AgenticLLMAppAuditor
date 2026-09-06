"""Two grading-key entries one produced finding can answer, and what separates them.

`matches_key` joins on `file`, `owasp_id` and a line window, then narrows on
`llm_surface`, `surface_name` and `component` -- but only where the *entry*
names one. So two entries collide when they share file and risk class, their
windows overlap, and no guarded field is spelled differently in both: `null`
against a value separates nothing, because one finding can simply carry the
value, while two different values genuinely cannot both be carried.

A collision costs nothing at score time and shows as a gain: one finding is
counted against two entries and recall reads one higher than the tool earned.
It has already happened here -- two entries of the key this project used to
ship both sat in `tools.py` under `LLM01` with one finding answering both, and
one of them was re-anchored to separate them.

That key was removed on 2026-09-06, so the sweep over its pairs went with it.
The rule did not: `key_promotion._colliding_pairs` refuses a *draft* whose
entries collide, and `tests/compare/test_key_promotion_refusals.py` is where
that refusal is exercised, on and off, over drafts built in the test. This file
is the layer under it -- why a collision matters at all, asked of the join
itself, over entries and a finding built here.
"""

import pytest

from evaluation.grading import GUARDED_ENTRY_FIELDS, matches_key
from evaluation_fixtures import key_entry
from findings_fixtures import produced_finding

# Lines for the constructed pair: the fixture finding sits at 12, an entry
# anchored at 10 opens a window of 10..13 that also covers it, and one
# anchored at 40 opens a window that starts well past it.
ANCHOR_LINE = 12
OVERLAPPING_ANCHOR = 10
SEPARATE_ANCHOR = 40

# Each guarded entry field, the finding field the join compares it against, and
# two values one finding cannot carry at once. Every field is covered rather
# than one sampled, so a fourth added to `GUARDED_ENTRY_FIELDS` is exercised
# instead of silently trusted.
SEPARATING_VALUES = {
    "llm_surface": ("surface_kind", "TOOL_CALL", "PROMPT_TEMPLATE"),
    "surface_name": ("surface_name", "ShellTool", "OtherTool"),
    "component": ("purl", "pkg:pypi/left@1.0", "pkg:pypi/right@2.0"),
}


def produced() -> dict:
    """The fixture finding as `findings.json` holds it: a plain dict, not a record."""
    return produced_finding(line=ANCHOR_LINE)


def test_two_entries_with_overlapping_windows_are_both_answered_by_one_finding() -> None:
    """The double count itself: one finding, two entries, recall one higher than earned."""
    finding = produced()
    anchored = key_entry(id="A", line=ANCHOR_LINE)
    overlapping = key_entry(id="B", line=OVERLAPPING_ANCHOR)
    assert matches_key(finding, anchored) and matches_key(finding, overlapping)


def test_separated_windows_cannot_be_answered_by_the_same_finding() -> None:
    """The fix a colliding pair takes: move an anchor until the windows stop touching."""
    finding = produced()
    anchored = key_entry(id="A", line=ANCHOR_LINE)
    separated = key_entry(id="B", line=SEPARATE_ANCHOR)
    assert matches_key(finding, anchored)
    assert not matches_key(finding, separated)


def test_the_separating_values_cover_every_field_the_join_guards() -> None:
    """The guard: a fourth guarded field must be given values, not skipped."""
    assert tuple(SEPARATING_VALUES) == GUARDED_ENTRY_FIELDS


@pytest.mark.parametrize("field", GUARDED_ENTRY_FIELDS)
def test_a_guarded_field_named_differently_in_both_entries_keeps_them_apart(
        field: str) -> None:
    """Two values of one field cannot both be carried, so overlapping windows are harmless."""
    finding_field, mine, theirs = SEPARATING_VALUES[field]
    anchored = key_entry(id="A", line=ANCHOR_LINE, **{field: mine})
    renamed = key_entry(id="B", line=OVERLAPPING_ANCHOR, **{field: theirs})
    finding = produced_finding(line=ANCHOR_LINE, **{finding_field: mine})
    assert matches_key(finding, anchored)
    assert not matches_key(finding, renamed)


def test_a_guarded_field_left_null_in_one_entry_separates_nothing() -> None:
    """`null` means "do not compare", so an off-surface entry still collides."""
    finding = produced()
    anchored = key_entry(id="A", line=ANCHOR_LINE)
    off_surface = key_entry(id="B", line=OVERLAPPING_ANCHOR,
                            llm_surface=None, surface_name=None)
    assert matches_key(finding, anchored) and matches_key(finding, off_surface)
