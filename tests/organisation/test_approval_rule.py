"""Guards on which findings need approval: a High or Critical risk, or sources that disagree."""

import pytest

from organisation.approval_rule import APPROVAL_BANDS, ApprovalReason, approval_reasons
from organisation.risk import assess, per_source
from organisation_samples import LOW_CONFIDENTIALITY, TOTAL_LOSS, all_answers, finding
from scoring.bands import RISK_BANDS
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

AGREEING = {"ghsa": TOTAL_LOSS, "nvd": TOTAL_LOSS}
DISAGREEING = {"ghsa": TOTAL_LOSS, "nvd": LOW_CONFIDENTIALITY}
# Measured against those vectors: TOTAL_LOSS comes out 29.4 Medium unexposed,
# 65.65 High exposed and in production, and 84.4 Critical with every Yes.
UNEXPOSED = all_answers()
EXPOSED = all_answers({"EXP-1": Answer.YES, "EXP-2": Answer.YES, "EXP-3": Answer.YES,
                       "BUS-1": Answer.YES, "BUS-2": Answer.YES})
EVERY_YES = all_answers({asked.question_id: Answer.YES for asked in APPROVED_QUESTIONS})
# Internet-facing and nothing else: ghsa's 9.8 comes out 50.65 High, nvd's 5.3 37.15 Medium.
STRADDLING = all_answers({"EXP-1": Answer.YES, "EXP-2": Answer.YES, "EXP-3": Answer.YES})


def reasons_for(vectors: dict[str, str], answers=None) -> tuple[ApprovalReason, ...]:
    """Give the reasons one finding needs approval, weighed against answers or unweighed."""
    one = finding(**vectors)
    weighed = None if answers is None else assess(one, answers, per_source(one))
    return approval_reasons(one, weighed)


def test_agreeing_sources_in_a_medium_band_need_no_approval():
    assert reasons_for(AGREEING, UNEXPOSED) == ()


@pytest.mark.parametrize("answers", [EXPOSED, EVERY_YES], ids=["High", "Critical"])
def test_a_high_or_critical_organisation_score_needs_approval(answers):
    assert reasons_for(AGREEING, answers) == (ApprovalReason.RISK_BAND,)


def test_sources_that_disagree_need_approval_with_no_score_weighed():
    # Without answers there is no risk score, so this half is the only one that can apply.
    assert reasons_for(DISAGREEING) == (ApprovalReason.SOURCES_DISAGREE,)


def test_a_finding_meeting_both_halves_is_given_both_reasons_in_the_rules_order():
    assert reasons_for(DISAGREEING, EXPOSED) == (
        ApprovalReason.RISK_BAND, ApprovalReason.SOURCES_DISAGREE,
    )


def test_one_source_in_a_high_band_is_enough_whatever_the_others_say():
    # Taking the lowest would choose a source, which is the precedence the design leaves open.
    assert ApprovalReason.RISK_BAND in reasons_for(DISAGREEING, STRADDLING)


def test_the_approval_bands_are_organisation_bands_and_the_reason_names_each():
    named = {name for _, name in RISK_BANDS}
    assert set(APPROVAL_BANDS) <= named
    assert all(band in ApprovalReason.RISK_BAND.value for band in APPROVAL_BANDS)


def test_a_risk_score_for_another_advisory_is_refused_rather_than_marking_this_one():
    other = finding("CVE-2000-0001", **AGREEING)
    weighed = assess(other, EXPOSED, per_source(other))
    with pytest.raises(ValueError, match="CVE-2000-0001 was paired with CVE-2021-23337"):
        approval_reasons(finding(**AGREEING), weighed)
