"""Guards on asking why the sources differ: disputed findings only, one call each, right model."""

import io
import json

import pytest

from cli.council_run import NO_TEXT_TO_READ, assess_one, build_roster, escalation_member
from cli.explanation_run import (
    NO_LOCAL_EXPLAINER,
    NOT_DISPUTED,
    explainer_of,
    explaining,
    explanations,
)
from cli_samples import ADVISORY, LEGAL, LODASH, QUOTATION, advisory_like
from council.explanation_prompt import EXPLANATION_PROMPT_VERSION, ExplanationPrompt
from council.roster import Member, Roster
from findings.finding import build_finding
from report.explanation_record import DroppedMetric, SourcesExplained, SourcesNotExplained

DISPUTED = build_finding(LODASH, ADVISORY)
AGREEING = build_finding(LODASH, advisory_like("CVE-AGREED"))
SILENT = build_finding(LODASH, advisory_like("CVE-SILENT", details="  ", vectors=ADVISORY.vectors))
ROSTER = build_roster(("small", "other"))
EXPLAINER = escalation_member("big:27b")
# ghsa reads C, I and A as H; nvd reads them L, N and N.
EXPLAINED = {"items": [{"metric": "C", "why": "It names no data.", "quotation": QUOTATION}]}


def recording(asked: list):
    """Answer a member's question with a legal value and the explainer's from the table."""

    def said(member, prompt):
        """Note the question, then answer it as the question it is."""
        asked.append((member.name, prompt))
        if isinstance(prompt, ExplanationPrompt):
            return json.dumps(EXPLAINED)
        value = LEGAL[prompt.metric]
        return json.dumps({"value": value, "evidence": QUOTATION, "confidence": "high"})

    return {"ollama": said}


def test_the_explainer_is_the_escalation_model_where_one_is_named_else_the_first_member():
    assert explainer_of(ROSTER, EXPLAINER) is EXPLAINER
    assert explainer_of(ROSTER, None) == ROSTER.members[0]


def test_a_hosted_member_is_passed_over_for_the_first_local_one():
    hosted = Member("far", "openrouter", "far/model", "far", runs_local=False, egress=True)
    near = ROSTER.members[0]
    assert explainer_of(Roster((hosted, near)), None) == near


def test_a_roster_with_no_local_member_and_no_escalation_model_is_refused_saying_why():
    hosted = Member("far", "openrouter", "far/model", "far", runs_local=False, egress=True)
    with pytest.raises(ValueError, match="no local member to explain with") as refused:
        explainer_of(Roster((hosted,)), None)
    assert str(refused.value) == NO_LOCAL_EXPLAINER


def test_a_disputed_finding_is_asked_once_and_its_explanation_kept():
    asked = []
    (record,) = explanations((DISPUTED,), EXPLAINER, recording(asked))
    assert [name for name, _ in asked] == ["big:27b"]
    assert isinstance(record, SourcesExplained)
    assert (record.model, record.prompt_version, record.dropped) == (
        "big:27b", EXPLANATION_PROMPT_VERSION, 0,
    )
    assert [(one.metric, one.evidence, one.evidence_verified) for one in record.items] == [
        ("C", QUOTATION, True),
    ]


def test_the_explainer_is_shown_each_source_s_value_on_the_disputed_metrics_only():
    asked = []
    explanations((DISPUTED,), EXPLAINER, recording(asked))
    [(_, prompt)] = asked
    assert prompt.metrics == ("C", "I", "A")
    assert "C (Confidentiality): ghsa H, nvd L" in prompt.system
    assert "AV (" not in prompt.system and "CVSS:3.1" not in prompt.system + prompt.user


def test_agreeing_sources_are_not_asked_about_and_say_why():
    asked = []
    records = explanations((AGREEING, SILENT), EXPLAINER, recording(asked))
    assert asked == []
    assert records == (
        SourcesNotExplained("CVE-AGREED", NOT_DISPUTED),
        SourcesNotExplained("CVE-SILENT", NO_TEXT_TO_READ),
    )


def test_an_explanation_that_quoted_nothing_says_which_model_and_why():
    def inventing(member, prompt):
        """Explain with a quotation the advisory does not hold."""
        return json.dumps({"items": [{"metric": "C", "why": "x", "quotation": "not in it"}]})

    (record,) = explanations((DISPUTED,), EXPLAINER, {"ollama": inventing})
    assert record == SourcesNotExplained(
        ADVISORY.advisory_id,
        "big:27b: the model offered 1 item, and none was kept (unverified quotation 1)",
        (DroppedMetric("C", "x", "not in it", False, "unverified quotation"),),
    )


def test_each_explanation_call_is_said_before_it_is_made_counting_the_disputed_alone():
    out = io.StringIO()
    findings = (AGREEING, DISPUTED)
    explanations(findings, EXPLAINER, recording([]), explaining(findings, out))
    assert out.getvalue() == f"explanation 1/1  finding {ADVISORY.advisory_id}  big:27b\n"


def test_the_step_the_harness_replays_never_asks_for_an_explanation():
    # `assess_one` is what every saved pass is replayed through; an explanation
    # asked there would be a call no pass recorded, and nothing would re-derive.
    asked = []
    assess_one(DISPUTED, ROSTER, recording(asked), escalation=EXPLAINER)
    assert not any(isinstance(prompt, ExplanationPrompt) for _, prompt in asked)
