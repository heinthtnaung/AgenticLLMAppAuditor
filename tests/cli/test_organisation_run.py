"""Guards on wiring the organisation in: answers weigh the findings, or nothing does."""

import json

import pytest

from cli.organisation_run import organisation_of, read_approval, weigh_findings
from cli_samples import ADVISORY, LODASH
from findings.finding import build_finding
from organisation.answers import OrganisationAnswers
from organisation.approval import Approval, NotApproved
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


FINDING = build_finding(LODASH, ADVISORY)


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
    weighed = weigh_findings((FINDING,), answers)
    assert len(weighed) == 1
    assert weighed[0].advisory_id == ADVISORY.advisory_id
    assert weighed[0].scores[0].exposure.score == 40


def test_a_finding_is_weighed_once_for_every_published_source_and_from_nothing_else():
    # The published sources are the only technical severities there are here: a
    # council's vector is shown beside the scores and never weighed into them.
    answers = OrganisationAnswers(everywhere=all_answers({"EXP-1": Answer.YES}))
    weighed = weigh_findings((FINDING,), answers)[0]
    published = [one.source for one in FINDING.scores]
    assert [one.technical.source for one in weighed.scores] == published


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
