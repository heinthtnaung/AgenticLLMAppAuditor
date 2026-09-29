"""Guards on the approval rule reading the band the floors left, not the band the number gives."""

from organisation.approval_rule import ApprovalReason, approval_reasons
from organisation.risk import assess, per_source
from organisation_samples import TOTAL_LOSS, all_answers, finding
from scoring.question import Answer

AGREEING = {"ghsa": TOTAL_LOSS, "nvd": TOTAL_LOSS}
# Two threat categories worth 50 each: THR-1 alone, and THR-2 with THR-3. Both
# weigh 9.8 to 39.4, which bands Medium, and only the first meets a floor.
EXPLOITED = all_answers({"THR-1": Answer.YES})
EXPLOIT_PUBLISHED_AND_AUTOMATED = all_answers({"THR-2": Answer.YES, "THR-3": Answer.YES})


def weighed_and_reasons(answers: dict) -> tuple:
    """Weigh one agreeing finding against the answers and give its scores and approval reasons."""
    one = finding(**AGREEING)
    weighed = assess(one, answers, per_source(one))
    banded = {(scored.score, scored.score_band, scored.band) for scored in weighed.scores}
    return banded, approval_reasons(one, weighed)


def test_a_score_a_floor_raised_to_high_needs_approval_though_its_number_bands_medium():
    banded, reasons = weighed_and_reasons(EXPLOITED)
    assert banded == {(39.4, "Medium", "High")}
    assert reasons == (ApprovalReason.RISK_BAND,)


def test_the_same_number_no_floor_raised_needs_no_approval():
    banded, reasons = weighed_and_reasons(EXPLOIT_PUBLISHED_AND_AUTOMATED)
    assert banded == {(39.4, "Medium", "Medium")}
    assert reasons == ()
