"""No two shipped key entries may be answerable by one produced finding.

`matches_key` joins on `file`, `owasp_id` and a line window, then narrows on
`llm_surface`, `surface_name` and `component` -- but only where the *entry*
names one. So two entries collide when they share file and risk class, their
windows overlap, and no guarded field is spelled differently in both: `null`
against a value separates nothing, because one finding can simply carry the
value, while two different values genuinely cannot both be carried.

A collision costs nothing at score time and shows as a gain: one finding is
counted against two entries and recall reads one higher than the tool earned.
It has already happened here -- `DVLA-08` and `DVLA-09` both sat in `tools.py`
under `LLM01` with one finding at `tools.py:37` answering both, and `DVLA-09`
was re-anchored to `tools.py:32` to separate them.

The window comes from `grading.line_window`, never re-derived here: a private
copy of the arithmetic would stop tracking the rule it is meant to police.

What is deliberately not here: the two anchors themselves. `DVLA-09` at 32 and
`DVLA-08` at 37 are pinned field by field in `test_shipped_key_entries.py`, so
what this file adds is the *rule* -- it fails for any future pair, not only for
the one that has already been fixed. The clauses that make an entry match
*nothing* are `test_shipped_key_join.py`, the opposite failure to this one.
"""

from itertools import combinations

import pytest

from evaluation.grading import GUARDED_ENTRY_FIELDS, line_window, matches_key
from evaluation_fixtures import key_entry
from findings_fixtures import produced_finding
from shipped_key_fixtures import shipped_keys

# Pairs of shipped entries that share a file and a risk class, and so are the
# only ones a window overlap could ever join. Two today: `DVLA-01`/`DVLA-06` in
# `main.py` and `DVLA-08`/`DVLA-09` in `tools.py`. Pinned so the sweep below
# cannot go quiet by finding nothing left to compare.
SAME_FILE_AND_CLASS_PAIRS = 2

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


def windows_overlap(first_entry: dict, second_entry: dict) -> bool:
    """True when some line satisfies both entries' match windows.

    Each window is checked for holding a line at all first: `line_end` below
    `line` closes the window before it opens, and no finding matches such an
    entry -- the plain interval test would call that pair a collision.
    """
    first_open, first_close = line_window(first_entry)
    second_open, second_close = line_window(second_entry)
    if first_open > first_close or second_open > second_close:
        return False
    return first_open <= second_close and second_open <= first_close


def guarded_fields_agree(first_entry: dict, second_entry: dict) -> bool:
    """True unless some guarded field is spelled differently in both entries.

    Only a field named in *both* separates them: where one is `null` the join
    does not compare it, so one finding can satisfy the other's value.
    """
    for field in GUARDED_ENTRY_FIELDS:
        first, second = first_entry.get(field), second_entry.get(field)
        if first and second and first != second:
            return False
    return True


def can_share_one_finding(first_entry: dict, second_entry: dict) -> bool:
    """True when a single finding could answer both entries, double-counting recall."""
    if first_entry["file"] != second_entry["file"]:
        return False
    if first_entry["owasp_id"] != second_entry["owasp_id"]:
        return False
    if not windows_overlap(first_entry, second_entry):
        return False
    return guarded_fields_agree(first_entry, second_entry)


# --- The mechanism, over entries and a finding built here -------------------

def test_two_entries_with_overlapping_windows_are_both_answered_by_one_finding() -> None:
    """The double count itself: one finding, two entries, recall one higher than earned."""
    finding = produced()
    anchored = key_entry(id="A", line=ANCHOR_LINE)
    overlapping = key_entry(id="B", line=OVERLAPPING_ANCHOR)
    assert matches_key(finding, anchored) and matches_key(finding, overlapping)


def test_the_collision_check_agrees_with_the_join_on_that_pair() -> None:
    """Guard: the helper below is not asserting something the join does not do."""
    assert can_share_one_finding(key_entry(id="A", line=ANCHOR_LINE),
                                 key_entry(id="B", line=OVERLAPPING_ANCHOR))


def test_separated_windows_cannot_be_answered_by_the_same_finding() -> None:
    """The fix applied to `DVLA-09`: move the anchor until the windows stop touching."""
    anchored = key_entry(id="A", line=ANCHOR_LINE)
    separated = key_entry(id="B", line=SEPARATE_ANCHOR)
    assert not can_share_one_finding(anchored, separated)


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
    assert not can_share_one_finding(anchored, renamed)
    # And the join agrees: the finding that answers one cannot answer the other.
    finding = produced_finding(line=ANCHOR_LINE, **{finding_field: mine})
    assert matches_key(finding, anchored)
    assert not matches_key(finding, renamed)


def test_a_guarded_field_left_null_in_one_entry_separates_nothing() -> None:
    """`null` means "do not compare", so an off-surface entry still collides."""
    anchored = key_entry(id="A", line=ANCHOR_LINE)
    off_surface = key_entry(id="B", line=OVERLAPPING_ANCHOR,
                            llm_surface=None, surface_name=None)
    assert can_share_one_finding(anchored, off_surface)
    assert matches_key(produced(), off_surface)


# --- What the shipped key may hold ------------------------------------------

def comparable_pairs() -> list[tuple[str, dict, str, dict]]:
    """Every pair within one key sharing a file and a risk class: the only ones that can collide.

    Within one key, never across two: an app is scored against its own key
    alone, so two keys naming `main.py` under `LLM01` are not a collision and
    reporting one would be a false alarm the moment a second key ships.
    """
    return [(f"{app}/{first['id']}", first, f"{app}/{second['id']}", second)
            for app, key in shipped_keys()
            for first, second in combinations(key["findings"], 2)
            if first["file"] == second["file"] and first["owasp_id"] == second["owasp_id"]]


def test_the_shipped_key_still_has_pairs_worth_comparing() -> None:
    """The guard: with no same-file, same-class pair the sweep below proves nothing."""
    assert len(comparable_pairs()) == SAME_FILE_AND_CLASS_PAIRS


def test_no_two_shipped_entries_can_be_answered_by_the_same_finding() -> None:
    """A collision would let one finding count twice and read as recall the tool did not earn."""
    for first_label, first, second_label, second in comparable_pairs():
        assert not can_share_one_finding(first, second), (
            f"{first_label} {line_window(first)} and {second_label} {line_window(second)} "
            "overlap in the same file and risk class, so one finding answers both")
