"""Sorts the subjects of a comparison into what can be compared and what cannot.

Two models "agreeing" is only a result if both were asked. The probe reaches
several verdicts without a model -- a template whose text is not written
literally at that line, one that interpolates nothing, a model that could not be
reached -- and counting those as agreement is how a run that consulted nobody
reported "agree on 1 of 1". A measured three-arm run counted three such subjects
among five agreements.

Four buckets, and they partition the subjects seen. `compare_models` asserts
that, so no bucket can be quoted without the other three adding up beside it.
"""

from artifacts.finding import INCONCLUSIVE, NOT_RUN, REFUTED
from checks.semantic_probe import NO_MODEL, NO_TEXT, STATIC_REFUTATION

# Why a verdict rests on no model answer. Closed, and mapped in this one place
# from the probe's own values so the study never invents a third spelling.
TEXT_NOT_LITERAL = "template_text_not_literal"
INTERPOLATES_NOTHING = "template_interpolates_nothing"
MODEL_UNREACHABLE = "model_unreachable"
MODEL_ANSWERED_UNUSABLY = "model_answered_unusably"

# Every arm reached this subject without a model, but not for the same reason.
# Possible only between the two model-dependent reasons above: the other two are
# decided from the template's own text and so fall out the same way in each arm.
MIXED_REASONS = "no_model_answer_for_differing_reasons"

EXCLUSION_REASONS = (TEXT_NOT_LITERAL, INTERPOLATES_NOTHING, MODEL_UNREACHABLE,
                     MODEL_ANSWERED_UNUSABLY, MIXED_REASONS)


def reason_without_a_model(outcome: str, reason: str | None, detail: str) -> str | None:
    """Why this verdict needed no model answer, or None when a model actually answered.

    `detail` decides the static refutation because a concluded probe may carry
    no reason -- `Probe.__post_init__` forbids it -- so the sentence itself is
    the only marker, which is why `semantic_probe` names it as a constant.
    """
    if outcome == INCONCLUSIVE and reason == NO_TEXT:
        return TEXT_NOT_LITERAL
    if outcome == REFUTED and detail == STATIC_REFUTATION:
        return INTERPOLATES_NOTHING
    if outcome == NOT_RUN and reason == NO_MODEL:
        return MODEL_UNREACHABLE
    if outcome == INCONCLUSIVE and reason == NO_MODEL:
        return MODEL_ANSWERED_UNUSABLY
    return None


def _arm_reason(arm: dict, subject: str) -> str | None:
    """One arm's reason for reaching this subject without a model, if it did."""
    return reason_without_a_model(arm["verdicts"][subject],
                                  arm["reasons"].get(subject),
                                  arm["details"].get(subject, ""))


def _shared_reason(reasons: list[str]) -> str:
    """The reason the arms gave, or the marker saying they differed."""
    return reasons[0] if len(set(reasons)) == 1 else MIXED_REASONS


def _absences(arms: list[dict], subjects: list[str]) -> list[dict]:
    """Subjects some arms judged and others never saw, which the planner may narrow away."""
    rows = []
    for subject in subjects:
        seen = [arm["model"] for arm in arms if subject in arm["verdicts"]]
        if len(seen) != len(arms):
            rows.append({"subject": subject, "examined_by": seen,
                         "absent_from": [arm["model"] for arm in arms
                                         if subject not in arm["verdicts"]]})
    return rows


def _excluded(arms: list[dict], subjects: list[str]) -> list[dict]:
    """Subjects *any* arm reached without a model answer, with why.

    Any, not every. One arm answering and another not is not a disagreement --
    "the model called it injectable" against "no model answered" compares a
    verdict with the absence of one, and publishing that as a disagreement is
    the same defect this module exists to remove, in its asymmetric form.
    """
    rows = []
    for subject in subjects:
        reasons = [r for r in (_arm_reason(arm, subject) for arm in arms) if r is not None]
        if reasons:
            rows.append({"subject": subject, "reason": _shared_reason(reasons)})
    return rows


def partition(arms: list[dict]) -> dict:
    """Sort every subject into agreed, disagreed, not put to a model, or not seen by all.

    Arm-absence wins over the other reasons: a subject one arm never saw is not
    comparable whatever the arms that did see it concluded.
    """
    subjects = sorted({s for arm in arms for s in arm["verdicts"]})
    absences = _absences(arms, subjects)
    absent = {row["subject"] for row in absences}
    excluded = _excluded(arms, [s for s in subjects if s not in absent])
    settled = absent | {row["subject"] for row in excluded}
    compared = [s for s in subjects if s not in settled]
    agreed = [s for s in compared if len({arm["verdicts"][s] for arm in arms}) == 1]
    return {
        "subjects_seen": len(subjects),
        "agreements": agreed,
        "disagreements": [{"subject": s,
                           "verdicts": {arm["model"]: arm["verdicts"][s] for arm in arms}}
                          for s in compared if s not in agreed],
        "not_put_to_a_model": excluded,
        "not_examined_by_every_arm": absences,
    }
