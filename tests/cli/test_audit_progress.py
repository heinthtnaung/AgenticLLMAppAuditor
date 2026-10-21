"""Guards on progress reaching the error stream through run_audit: the bar's phases, and --debug.

These drive the whole command so that `--debug` and the per-phase `finish()` are
exercised where they are wired, not only on a progress object built by hand.
"""

import io
import json

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from cli.progress_bar import BAR_WIDTH, FILLED, RETURN
from cli_samples import (
    ADVISORY,
    DATED,
    LEGAL,
    QUOTATION,
    FakeTerminal,
    advisory_like,
    scanners_answering,
)

BIG = "big:27b"
# A second advisory on the same component, its sources disagreeing like the first's,
# so both findings are put to the council and both are explained.
SECOND = advisory_like("GHSA-abcd-efgh-ijkl", vectors=ADVISORY.vectors)
FULL_BAR = f"[{FILLED * BAR_WIDTH}]"


def answering_but_s(member, prompt) -> str:
    """Answer every metric, leaving S open for all but the escalation model, so escalation runs."""
    if prompt.metric == "S" and member.name != BIG:
        return json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
    return json.dumps({"value": LEGAL[prompt.metric], "evidence": QUOTATION, "confidence": "high"})


def explaining_c(member, prompt) -> str:
    """Explain C, quoting the advisory so the explanation verifies and is kept."""
    return json.dumps({"items": [{"metric": "C", "why": "it says so", "quotation": QUOTATION}]})


def progress_of(monkeypatch, tmp_path, out, debug: bool) -> str:
    """Run one audit over two disputed findings through stand-in clients; give what it said."""
    real_assessments, real_explanations = audit_module.assessments, audit_module.explanations
    scanners_answering(monkeypatch, advisories={ADVISORY.purl: (ADVISORY, SECOND)})
    monkeypatch.setattr(audit_module, "escalation_model", lambda: BIG)
    monkeypatch.setattr(
        audit_module, "assessments",
        lambda findings, roster, **named: real_assessments(
            findings, roster, **{**named, "clients": {"ollama": answering_but_s}}),
    )
    monkeypatch.setattr(
        audit_module, "explanations",
        lambda findings, explainer, **named: real_explanations(
            findings, explainer, **{**named, "clients": {"ollama": explaining_c}}),
    )
    run_audit(Options(tmp_path, TEXT_FORMAT, council_models=("small",), debug=debug), DATED, out)
    return out.getvalue()


def first_frame(line: str) -> str:
    """Give the first in-place frame drawn on one phase's line."""
    return line.split(RETURN)[1].rstrip()


def last_frame(line: str) -> str:
    """Give the frame left standing on one phase's line when the phase ended."""
    return line.split(RETURN)[-1].rstrip()


def test_a_terminal_draws_each_phase_as_its_own_closed_line(monkeypatch, tmp_path):
    written = progress_of(monkeypatch, tmp_path, FakeTerminal(), debug=False)
    lines = written.split("\n")
    # Every phase ends with a newline, so the stream ends with one and splits into three.
    assert lines[-1] == ""
    council, escalation, explanation = lines[:-1]
    assert first_frame(council).endswith("1/32  3%  finding 1/2")
    assert last_frame(council).endswith("32/32  100%  finding 2/2")
    assert first_frame(escalation) == "escalation 1  finding 1/2 CVE-2021-23337"
    assert last_frame(escalation) == "escalation 4  finding 2/2 GHSA-abcd-efgh-ijkl"
    assert first_frame(explanation).endswith("1/2  50%  finding CVE-2021-23337")
    expected = f"explanation {FULL_BAR} 2/2  100%  finding GHSA-abcd-efgh-ijkl"
    assert last_frame(explanation) == expected


def test_debug_at_a_terminal_gives_the_lines_a_redirected_run_gives(monkeypatch, tmp_path):
    at_terminal = progress_of(monkeypatch, tmp_path, FakeTerminal(), debug=True)
    redirected = progress_of(monkeypatch, tmp_path, io.StringIO(), debug=False)
    assert at_terminal == redirected
    assert RETURN not in at_terminal
