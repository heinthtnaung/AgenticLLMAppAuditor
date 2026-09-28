"""Guards on explanations in an audit: asked last, beside a council only, and never read back.

`docs/SCORING_MODEL.md` makes the explainer the last model role: it writes the
rationale once every value is fixed, and nothing computes from what it wrote.
"""

import json

from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from council import providers
from council.explanation_prompt import ExplanationPrompt
from report.absences import EXPLANATION, NO_EXPLAINER_ASKED
from report.explanation_record import SourcesExplained
from cli_samples import (
    ADVISORY,
    DATED,
    LEGAL,
    QUOTATION,
    explaining_nothing,
    run_command_line,
    scanners_answering,
    written_answers,
)

BIG = "big:27b"
MEMBERS = ("small", "other")
EXPLAINED = {"items": [{"metric": "C", "why": "It names no data.", "quotation": QUOTATION}]}


def options_for(path, models=MEMBERS, answers=None) -> Options:
    """Build the options one run is about."""
    return Options(
        repository=path, report_format=TEXT_FORMAT, council_models=tuple(models), answers=answers
    )


def recording(asked: list):
    """Answer every question, noting its kind: the council declines S, and the model reads it."""

    def said(member, prompt):
        """Note who was asked what, then answer it as the question it is."""
        explaining = isinstance(prompt, ExplanationPrompt)
        asked.append("explanation" if explaining else f"{member.name} {prompt.metric}")
        if explaining:
            return json.dumps(EXPLAINED)
        if prompt.metric == "S" and member.name != BIG:
            return json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
        value = LEGAL[prompt.metric]
        return json.dumps({"value": value, "evidence": QUOTATION, "confidence": "high"})

    return said


def test_the_explanation_is_asked_only_after_every_council_and_escalation_call(
    tmp_path, monkeypatch
):
    asked = []
    scanners_answering(monkeypatch)
    monkeypatch.setenv("AUDITOR_ESCALATION_MODEL", BIG)
    monkeypatch.setitem(providers.PROVIDER_CLIENTS, "ollama", recording(asked))
    report = run_audit(options_for(tmp_path), DATED)
    assert asked.count(f"{BIG} S") == 2
    assert asked[-1] == "explanation" and asked.count("explanation") == 1
    assert report.explanations[ADVISORY.advisory_id].model == BIG


def test_without_an_escalation_model_the_council_s_first_member_explains(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    monkeypatch.setitem(providers.PROVIDER_CLIENTS, "ollama", recording([]))
    report = run_audit(options_for(tmp_path), DATED)
    assert report.explanations[ADVISORY.advisory_id].model == "small"


def test_nothing_reads_the_explanation_back_into_a_score_or_a_ruling(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    monkeypatch.setitem(providers.PROVIDER_CLIENTS, "ollama", recording([]))
    answers = written_answers(tmp_path)
    explained = run_audit(options_for(tmp_path, answers=answers), DATED)
    explaining_nothing(monkeypatch)
    unexplained = run_audit(options_for(tmp_path, answers=answers), DATED)
    assert isinstance(explained.explanations[ADVISORY.advisory_id], SourcesExplained)
    assert unexplained.explanations == {}
    assert explained.risk == unexplained.risk
    assert explained.council == unexplained.council


def test_a_run_with_no_council_asks_no_model_why_and_says_so(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setitem(providers.PROVIDER_CLIENTS, "ollama", recording(asked))
    _, out, _ = run_command_line(["--format", "json"], monkeypatch, tmp_path)
    record = json.loads(out)
    assert asked == []
    assert record["findings"][0]["llm_explanation"] == {
        "assessed": False, "because": NO_EXPLAINER_ASKED, "dropped_items": [],
    }
    assert {"what": EXPLANATION, "because": NO_EXPLAINER_ASKED} in record["not_assessed"]
