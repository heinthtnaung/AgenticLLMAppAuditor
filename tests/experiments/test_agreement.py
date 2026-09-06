"""Which subjects did two models actually get asked about, and which did they not?

Agreement between two models is only a result if both were asked. The probe
reaches several verdicts with no model at all -- a template whose text is not
written literally at that line, one that interpolates nothing, a server that
could not be reached -- and counting those as agreement is how a measured run
printed "agree on 1 of 1" having consulted nobody, and an older five-template
run published "agree on 5 of 5" with three never asked.

So the two assertions that matter in every test here are the pair: the subject
is in the bucket it belongs in, *and* it is in neither `agreements` nor
`disagreements`. One without the other is what passed before.

The asymmetric case is the one that was actually wrong. `_excluded` asked
whether *every* arm had reached the subject without a model, so one arm
answering and another not made the subject comparable, and the run published a
verdict against the absence of one as a disagreement. Two tests below hold the
`any` that replaced it, one per model-dependent reason.

The arms are built by `arm_fixtures`, not by running an audit: what is under
test is the sorting rule, and `test_prompt_labelling_seam.py` covers the run.
"""

from agreement import (
    EXCLUSION_REASONS, INTERPOLATES_NOTHING, MIXED_REASONS, MODEL_ANSWERED_UNUSABLY,
    MODEL_UNREACHABLE, TEXT_NOT_LITERAL, partition)
from compare_models import BUCKETS
from .arm_fixtures import (
    ANSWERED_UNUSABLY_STATE, CLEARED_STATE, FIRST, FLAGGED_STATE, FOURTH, HOSTED,
    INTERPOLATES_NOTHING_STATE, LOCAL, MODEL_UNREACHABLE_STATE, SECOND, State, THIRD,
    TEXT_NOT_LITERAL_STATE, arm)


def both_arms_reaching(state: State) -> list[dict]:
    """Two arms that reached the one subject in the same state."""
    return [arm(LOCAL, {FIRST: state}), arm(HOSTED, {FIRST: state})]


def excluded_for(state: State) -> dict:
    """The single not-put-to-a-model row two arms in that state produce."""
    result = partition(both_arms_reaching(state))
    assert result["agreements"] == [] and result["disagreements"] == []
    assert len(result["not_put_to_a_model"]) == 1
    return result["not_put_to_a_model"][0]


def test_a_template_whose_text_is_not_literal_was_never_put_to_a_model() -> None:
    """The probe could not read the template, so neither model was asked about it."""
    assert excluded_for(TEXT_NOT_LITERAL_STATE) == {"subject": FIRST,
                                                    "reason": TEXT_NOT_LITERAL}


def test_a_template_that_interpolates_nothing_was_never_put_to_a_model() -> None:
    """The probe refuted it from the text alone, which is not the models agreeing."""
    assert excluded_for(INTERPOLATES_NOTHING_STATE) == {"subject": FIRST,
                                                        "reason": INTERPOLATES_NOTHING}


def test_an_unreachable_model_is_not_an_answer() -> None:
    """Both servers refused the call, so there is no verdict to compare."""
    assert excluded_for(MODEL_UNREACHABLE_STATE) == {"subject": FIRST,
                                                     "reason": MODEL_UNREACHABLE}


def test_a_model_answering_neither_word_is_not_an_answer() -> None:
    """Both models replied and neither said VULNERABLE or SAFE."""
    assert excluded_for(ANSWERED_UNUSABLY_STATE) == {"subject": FIRST,
                                                     "reason": MODEL_ANSWERED_UNUSABLY}


def test_two_arms_stopped_by_different_things_are_marked_as_such() -> None:
    """One server was unreachable and the other answered unusably: one shared marker."""
    arms = [arm(LOCAL, {FIRST: MODEL_UNREACHABLE_STATE}),
            arm(HOSTED, {FIRST: ANSWERED_UNUSABLY_STATE})]
    result = partition(arms)
    assert result["not_put_to_a_model"] == [{"subject": FIRST, "reason": MIXED_REASONS}]
    assert result["agreements"] == [] and result["disagreements"] == []


def test_one_arm_answering_and_one_unreachable_is_not_a_disagreement() -> None:
    """The asymmetry: one model was asked and one could not be, so there is nothing to compare."""
    arms = [arm(LOCAL, {FIRST: FLAGGED_STATE}),
            arm(HOSTED, {FIRST: MODEL_UNREACHABLE_STATE})]
    result = partition(arms)
    assert result["not_put_to_a_model"] == [{"subject": FIRST, "reason": MODEL_UNREACHABLE}]
    assert result["agreements"] == [] and result["disagreements"] == []


def test_one_arm_answering_and_one_answering_unusably_is_not_a_disagreement() -> None:
    """The same asymmetry with the other model-dependent reason: a reply carrying no verdict."""
    arms = [arm(LOCAL, {FIRST: ANSWERED_UNUSABLY_STATE}),
            arm(HOSTED, {FIRST: CLEARED_STATE})]
    result = partition(arms)
    assert result["not_put_to_a_model"] == [{"subject": FIRST,
                                             "reason": MODEL_ANSWERED_UNUSABLY}]
    assert result["agreements"] == [] and result["disagreements"] == []


def test_every_exclusion_reason_is_reachable() -> None:
    """Non-vacuity: the tests above cover the closed list, with none left over."""
    reached = {TEXT_NOT_LITERAL, INTERPOLATES_NOTHING, MODEL_UNREACHABLE,
               MODEL_ANSWERED_UNUSABLY, MIXED_REASONS}
    assert reached == set(EXCLUSION_REASONS)


def test_a_subject_one_arm_never_saw_is_not_a_disagreement() -> None:
    """The planner may narrow a check away: an absent arm contributed `None` before."""
    arms = [arm(LOCAL, {FIRST: FLAGGED_STATE, SECOND: FLAGGED_STATE}),
            arm(HOSTED, {FIRST: FLAGGED_STATE})]
    result = partition(arms)
    assert result["not_examined_by_every_arm"] == [
        {"subject": SECOND, "examined_by": [LOCAL], "absent_from": [HOSTED]}]
    assert result["agreements"] == [FIRST]
    assert result["disagreements"] == []


def test_arm_absence_wins_over_the_exclusion_reasons() -> None:
    """A subject one arm never saw is not comparable, whatever the other arm reached."""
    arms = [arm(LOCAL, {FIRST: FLAGGED_STATE, SECOND: TEXT_NOT_LITERAL_STATE}),
            arm(HOSTED, {FIRST: FLAGGED_STATE})]
    result = partition(arms)
    assert [row["subject"] for row in result["not_examined_by_every_arm"]] == [SECOND]
    assert result["not_put_to_a_model"] == []


def test_two_models_answering_differently_disagree() -> None:
    """Both were genuinely asked and said opposite things, which is the one real result."""
    arms = [arm(LOCAL, {FIRST: FLAGGED_STATE}), arm(HOSTED, {FIRST: CLEARED_STATE})]
    result = partition(arms)
    assert result["disagreements"] == [
        {"subject": FIRST, "verdicts": {LOCAL: FLAGGED_STATE[0], HOSTED: CLEARED_STATE[0]}}]
    assert result["agreements"] == []
    assert result["not_put_to_a_model"] == []


def test_the_four_buckets_partition_every_subject_seen() -> None:
    """One subject in each bucket at once: four sorted, four seen, one apiece."""
    arms = [arm(LOCAL, {FIRST: FLAGGED_STATE, SECOND: FLAGGED_STATE,
                        THIRD: MODEL_UNREACHABLE_STATE, FOURTH: FLAGGED_STATE}),
            arm(HOSTED, {FIRST: FLAGGED_STATE, SECOND: CLEARED_STATE,
                         THIRD: MODEL_UNREACHABLE_STATE})]
    result = partition(arms)
    assert result["subjects_seen"] == 4
    assert [len(result[bucket]) for bucket in BUCKETS] == [1, 1, 1, 1]
    assert sum(len(result[bucket]) for bucket in BUCKETS) == result["subjects_seen"]
