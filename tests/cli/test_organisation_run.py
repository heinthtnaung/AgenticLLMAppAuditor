"""Guards on wiring the organisation in: answers weigh the findings, or nothing does."""

import json

import pytest

from cli.council_run import assess_one, build_roster
from cli.organisation_run import organisation_of, read_approval, weigh_findings
from cli_samples import ADVISORY, LODASH, answering
from findings.finding import build_finding
from organisation.answers import OrganisationAnswers
from organisation.approval import Approval, NotApproved
from report.council_record import CouncilAssessment, CouncilWithoutVector
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


FINDING = build_finding(LODASH, ADVISORY)


def put_to_council(**replies) -> dict:
    """Put the finding to a real one-member council, keyed as `weigh_findings` takes it."""
    outcome = assess_one(FINDING, build_roster(("small",)), answering(**replies))
    return {outcome.advisory_id: outcome}


def written(directory, **document):
    """Write one answer file the way an operator would."""
    document["answers"] = {
        **{asked.question_id: "No" for asked in APPROVED_QUESTIONS},
        **document.get("answers", {}),
    }
    path = directory / "answers.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_findings_are_weighed_against_the_answers_that_apply_to_them():
    answers = OrganisationAnswers(everywhere=all_answers({"EXP-1": Answer.YES}))
    weighed = weigh_findings((FINDING,), answers, {})
    assert len(weighed) == 1
    assert weighed[0].advisory_id == ADVISORY.advisory_id
    assert weighed[0].scores[0].exposure.score == 40


def test_a_finding_is_weighed_once_per_source_when_no_council_settled_it():
    answers = OrganisationAnswers(everywhere=all_answers({"EXP-1": Answer.YES}))
    assert len(weigh_findings((FINDING,), answers, {})[0].scores) == len(FINDING.scores)


def test_a_council_that_settled_a_vector_collapses_the_range_to_one_score():
    # One agreed technical severity, so there is nothing left to choose between.
    settled = put_to_council()
    assert isinstance(settled[ADVISORY.advisory_id], CouncilAssessment)
    answers = OrganisationAnswers(everywhere=all_answers({"EXP-1": Answer.YES}))
    weighed = weigh_findings((FINDING,), answers, settled)
    assert len(weighed[0].scores) == 1
    assert "council" in weighed[0].scores[0].technical.derived_from


def test_a_council_that_settled_nothing_leaves_the_sources_side_by_side():
    open_still = put_to_council(declining=("S",))
    assert isinstance(open_still[ADVISORY.advisory_id], CouncilWithoutVector)
    answers = OrganisationAnswers(everywhere=all_answers({"EXP-1": Answer.YES}))
    weighed = weigh_findings((FINDING,), answers, open_still)
    assert len(weighed[0].scores) == len(FINDING.scores)


def test_no_answer_file_means_nobody_was_asked_and_nothing_was_approved():
    answers, approval = organisation_of(None)
    assert answers.everywhere == {}
    assert isinstance(approval, NotApproved)
    assert "no answer file" in approval.reason


def test_an_answer_file_with_no_approval_says_the_file_carries_none(tmp_path):
    _, approval = organisation_of(written(tmp_path, answers={"EXP-1": "Yes"}))
    assert isinstance(approval, NotApproved)
    assert "carries no approval" in approval.reason


def test_an_approval_in_the_file_is_read_with_who_what_and_when(tmp_path):
    path = written(tmp_path, approval={
        "approver": "someone@example.com",
        "decision": "overridden",
        "recorded_at": "2026-09-23T09:14:00Z",
        "note": "accepted the risk",
    })
    approval = read_approval(path)
    assert isinstance(approval, Approval)
    assert (approval.approver, approval.decision.value) == ("someone@example.com", "overridden")
    assert approval.note == "accepted the risk"


def test_an_approval_that_names_nobody_is_refused(tmp_path):
    signed = {"decision": "approved", "recorded_at": "2026-09-23T09:14:00Z"}
    path = written(tmp_path, approval=signed)
    with pytest.raises(ValueError, match="must name who made it"):
        read_approval(path)


def test_an_approval_with_no_real_time_is_refused(tmp_path):
    path = written(tmp_path, approval={
        "approver": "someone", "decision": "approved", "recorded_at": "yesterday",
    })
    with pytest.raises(ValueError, match="is not an ISO 8601 instant"):
        read_approval(path)
