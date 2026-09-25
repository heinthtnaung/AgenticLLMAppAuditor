"""Guards on the organisation's half of the audit record: re-derivable, and honest when absent."""

import math
from dataclasses import replace

from full_runs import ADVISORY_ID, fully_assessed
from organisation.approval import Approval, Decision, NotApproved
from organisation.risk import assess, per_source
from report.council_beside import COUNCIL_SOURCE
from report.json_risk import approval_of, risk_of
from report.record import build_report
from report_samples import PROVENANCE, TOTAL_LOSS, catalogue, component, finding
from scoring.library import question
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

DJANGO = component()
def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


ANSWERS = all_answers({"EXP-1": Answer.YES, "BUS-1": Answer.YES, "THR-1": Answer.UNKNOWN})


def a_report(findings=(), risk=(), approval=None):
    """Build one report from whatever a test is about."""
    return build_report(PROVENANCE, catalogue(DJANGO), findings, {}, (), risk, approval)


def weighed(one):
    """Score one finding against the same environment every test here uses."""
    return assess(one, ANSWERS, per_source(one))


def test_every_answer_and_weight_that_produced_a_score_is_in_the_record():
    # A score nobody can re-derive is not a score, so the question, the answer,
    # what a Yes was worth and what this answer contributed are all here.
    one = finding(DJANGO)
    rendered = risk_of(a_report((one,), (weighed(one),)), one.advisory.advisory_id)
    exposure = rendered["categories"]["exposure"]["answers"]
    internet = next(entry for entry in exposure if entry["question_id"] == "EXP-1")
    assert internet == {
        "question_id": "EXP-1",
        "question": question("EXP-1").text,
        "answer": "Yes",
        "yes_weight": 40,
        "contribution": 40,
    }


def test_the_weighting_that_combined_the_categories_is_in_the_record():
    # The category scores were re-derivable and the total was not: the 30/25/25/20
    # weighting lived only in `docs/SCORING_MODEL.md`.
    one = finding(DJANGO)
    rendered = risk_of(a_report((one,), (weighed(one),)), one.advisory.advisory_id)
    assert rendered["scores"][0]["technical_weight"] == 0.30
    weights = {name: entry["weight"] for name, entry in rendered["categories"].items()}
    assert weights == {"exposure": 0.25, "business": 0.25, "threat": 0.20}


def test_the_recorded_weighting_re_derives_the_recorded_total():
    # Every weight sits beside the term it multiplies, so the total re-derives
    # with nothing paired by position.
    one = finding(DJANGO)
    rendered = risk_of(a_report((one,), (weighed(one),)), one.advisory.advisory_id)
    score = rendered["scores"][0]
    categories = rendered["categories"].values()
    terms = [score["technical_score"] * score["technical_weight"]]
    terms += [category["score"] * category["weight"] for category in categories]
    assert round(math.fsum(terms), 2) == score["score"]


def test_a_category_carries_its_raw_total_beside_the_clamped_score():
    # The clamp is invisible in the score alone, and it is the step the design
    # is most particular about.
    one = finding(DJANGO)
    rendered = risk_of(a_report((one,), (weighed(one),)), one.advisory.advisory_id)
    business = rendered["categories"]["business"]
    assert business["score"] == 40
    assert business["raw_total"] == 40
    assert business["clamped"] is False


def test_the_record_carries_one_score_per_source_and_names_each():
    one = finding(DJANGO, vectors={"ghsa": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"})
    rendered = risk_of(a_report((one,), (weighed(one),)), one.advisory.advisory_id)
    assert [entry["technical_from"] for entry in rendered["scores"]] == ["ghsa CVSS base score 9.8"]


def test_the_record_says_whether_the_source_changes_the_band():
    one = finding(DJANGO)
    rendered = risk_of(a_report((one,), (weighed(one),)), one.advisory.advisory_id)
    assert rendered["band_depends_on_the_source"] is False
    assert rendered["bands"]


def test_an_unknown_answer_is_flagged_and_the_question_named():
    one = finding(DJANGO)
    rendered = risk_of(a_report((one,), (weighed(one),)), one.advisory.advisory_id)
    assert rendered["provisional"] is True
    assert rendered["scores"][0]["unknown_questions"] == ["THR-1"]


def test_a_councils_settled_vector_sits_beside_the_scores_and_says_it_was_not_used():
    # Its members settled 9.8 on a finding ghsa put at 7.5, and the ruling was
    # that the vector is shown beside the published scores and never weighed.
    rendered = risk_of(fully_assessed(), ADVISORY_ID)
    assert rendered["council_figure"] == {
        "source": COUNCIL_SOURCE,
        "vector": TOTAL_LOSS,
        "base_score": 9.8,
        "used_in_score": False,
    }


def test_the_scores_are_the_same_with_a_council_beside_them_as_without():
    # Anything reading the council's vector into a score moves one of these.
    beside = risk_of(fully_assessed(), ADVISORY_ID)
    alone = risk_of(replace(fully_assessed(), council={}), ADVISORY_ID)
    assert alone.pop("council_figure") is None
    beside.pop("council_figure")
    assert beside == alone


def test_a_finding_nobody_weighed_carries_null_rather_than_a_zero():
    one = finding(DJANGO)
    assert risk_of(a_report((one,)), one.advisory.advisory_id) is None


def test_an_approval_is_recorded_with_who_what_and_when():
    signed = Approval("someone@example.com", Decision.OVERRIDDEN, "2026-09-23T09:14:00Z", "why")
    assert approval_of(a_report(approval=signed)) == {
        "approved": True,
        "approver": "someone@example.com",
        "decision": "overridden",
        "recorded_at": "2026-09-23T09:14:00Z",
        "note": "why",
    }


def test_an_audit_nobody_approved_says_so_rather_than_looking_signed():
    rendered = approval_of(a_report(approval=NotApproved("nobody has approved this audit")))
    assert rendered == {"approved": False, "reason": "nobody has approved this audit"}


def test_an_audit_with_no_approval_given_at_all_still_says_so():
    assert approval_of(a_report())["approved"] is False
