"""Rules 1 to 3: silence, an empty list, and the surfaces the prompt never showed.

Task 7.4 let the planner narrow a check to some of its surfaces, which means a
finding can now go unfound because the model did not look. `plan_selection` is
the containment; its docstring lists five rules, and this file attacks the three
that are about *surfaces*. `test_plan_selection_refusals.py` attacks the two
that are about *checks* -- which check may be narrowed at all, and how a refusal
is recorded.

**The property being defended is one sentence: every failure mode falls back to
full coverage.** Not "raises", not "narrows a little less" -- falls all the way
back. So each test below asserts two things about a bad narrowing: it is not in
`chosen` (so the check examines everything), and it is in `refused` with a
reason a reader can look up (rule 5), because a refusal nobody recorded is
indistinguishable from a narrowing nobody asked for.

Everything here is pure. `resolve` takes the `described` list as an argument, so
rule 3 is exercised by handing it fewer surfaces than exist rather than by
patching the cap -- the cap itself is attacked at its real value in
`test_planner_describe_cap.py`.
"""

from checks import plan_selection
from plan_selection_fixtures import (
    CHOSEN_ID, DESCRIBED, GHOST_ID, SURFACES, UNDESCRIBED_IDS, refusal_reasons,
    resolve)
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK


# --- rule 1: a check the model does not name runs on everything -------------

def test_an_empty_selection_object_narrows_nothing_and_refuses_nothing() -> None:
    """Silence is not a narrowing: no opinion leaves the audit at full coverage."""
    assert resolve({}) == ({}, [])


def test_a_check_the_model_never_named_examines_every_surface() -> None:
    """`surfaces_for` answers with the whole list, which is what unselected means."""
    chosen, _refused = resolve({TAINT_CHECK: [CHOSEN_ID]})
    assert plan_selection.surfaces_for(PERMISSION_CHECK, chosen, SURFACES) == SURFACES


def test_an_unselected_check_is_handed_the_caller_s_own_list() -> None:
    """No copy and no filter: the check sees exactly the surfaces the audit found."""
    assert plan_selection.surfaces_for(PERMISSION_CHECK, {}, SURFACES) is SURFACES


# --- rule 2: an empty selection is refused, not honoured ---------------------

def test_a_check_narrowed_to_an_empty_list_is_refused() -> None:
    """The false claim this phase exists to prevent, arriving by a legitimate path.

    Honoured, the check would sit in `coverage.checks_run` -- which
    `docs/SCHEMAS.md` defines as "looked and found nothing" -- having examined
    nothing at all.
    """
    chosen, refused = resolve({TAINT_CHECK: []})
    assert chosen == {}
    assert refusal_reasons(refused) == [plan_selection.EMPTY_SELECTION]


def test_a_check_narrowed_to_a_list_of_non_strings_is_refused_the_same_way() -> None:
    """`[null]` names no surface, so it is the empty selection wearing a different shape."""
    chosen, refused = resolve({TAINT_CHECK: [None, 7, {"id": CHOSEN_ID}]})
    assert chosen == {}
    assert refusal_reasons(refused) == [plan_selection.EMPTY_SELECTION]


def test_a_refused_empty_selection_still_examines_every_surface() -> None:
    """The fallback stated as the thing a reader cares about, not as a dict comparison."""
    chosen, _refused = resolve({TAINT_CHECK: []})
    assert plan_selection.surfaces_for(TAINT_CHECK, chosen, SURFACES) == SURFACES


# --- rule 3: surfaces the prompt never described always run ------------------

def test_a_check_narrowed_to_one_surface_still_examines_the_two_never_described() -> None:
    """Rule 3, in counts: one chosen plus the two the model was never shown.

    An implementation that took the model's list literally would exclude every
    surface past the describe cap without saying so -- silently, since the
    narrowing record would report a smaller number and look correct.
    """
    chosen, refused = resolve({TAINT_CHECK: [CHOSEN_ID]})
    assert refused == []
    examined = plan_selection.surfaces_for(TAINT_CHECK, chosen, SURFACES)
    assert len(examined) == 3
    assert len(SURFACES) == 5


def test_the_surfaces_added_back_are_exactly_the_ones_never_described() -> None:
    """Named by id, so "three of five" cannot be satisfied by the wrong three."""
    chosen, _refused = resolve({TAINT_CHECK: [CHOSEN_ID]})
    assert chosen[TAINT_CHECK] == {CHOSEN_ID} | UNDESCRIBED_IDS


def test_narrowing_every_described_surface_is_the_whole_list_again() -> None:
    """The degenerate narrowing: chosen plus unseen is everything, so nothing is lost."""
    chosen, _refused = resolve({TAINT_CHECK: [surface.id for surface in DESCRIBED]})
    assert plan_selection.surfaces_for(TAINT_CHECK, chosen, SURFACES) == SURFACES


def test_a_surface_that_was_described_but_not_chosen_is_the_one_left_out() -> None:
    """Guard: the union must not quietly add back everything, which would make it inert."""
    chosen, _refused = resolve({TAINT_CHECK: [CHOSEN_ID]})
    assert DESCRIBED[1].id not in chosen[TAINT_CHECK]


# --- rule 3, the other half: an id the model was never shown ----------------

def test_an_id_belonging_to_no_surface_is_refused() -> None:
    """A hallucinated id would otherwise narrow a check to nothing at all."""
    chosen, refused = resolve({TAINT_CHECK: [GHOST_ID]})
    assert chosen == {}
    assert refusal_reasons(refused) == [plan_selection.UNKNOWN_SURFACE]


def test_a_real_id_that_was_never_described_is_refused_too() -> None:
    """The model cannot have chosen what it was not shown, so naming it is a mistake."""
    chosen, refused = resolve({TAINT_CHECK: [SURFACES[4].id]})
    assert chosen == {}
    assert refusal_reasons(refused) == [plan_selection.UNKNOWN_SURFACE]


def test_one_bad_id_refuses_the_whole_narrowing_rather_than_part_of_it() -> None:
    """Half-honouring a list the model got wrong is a narrowing nobody asked for."""
    chosen, _refused = resolve({TAINT_CHECK: [CHOSEN_ID, GHOST_ID]})
    assert plan_selection.surfaces_for(TAINT_CHECK, chosen, SURFACES) == SURFACES


def test_the_refusal_names_only_the_ids_it_could_not_place() -> None:
    """A reader debugging the model's reply needs the wrong id, not the whole list."""
    _chosen, refused = resolve({TAINT_CHECK: [CHOSEN_ID, GHOST_ID]})
    assert refused[0]["surface_ids"] == [GHOST_ID]
