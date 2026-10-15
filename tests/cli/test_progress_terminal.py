"""Guards on the display choice: a bar at a terminal, the full log off one or under --debug."""

import io

from cli.progress import COUNCIL_LINE, CouncilProgress, ExplanationProgress
from cli_samples import FakeTerminal


def driving_council(watching: CouncilProgress) -> None:
    """Drive one council through a start, both orders, an escalation, and the closing finish."""
    watching.starting("CVE-1")
    watching.asking("AV", "qwen")
    watching.asking("AV", "qwen", reversed_options=True)
    watching.returning_to(1, "CVE-1")
    watching.escalating("S", "big")
    watching.finish()


def driving_explanations(watching: ExplanationProgress) -> None:
    """Drive the explainer over two findings and the closing finish."""
    watching.explaining("CVE-1", "big:27b")
    watching.explaining("CVE-2", "big:27b")
    watching.finish()


def test_a_terminal_redraws_one_line_in_place_rather_than_one_per_call():
    # Watched at a terminal, progress is a single line rewritten, not a growing log.
    terminal = FakeTerminal()
    watching = CouncilProgress(findings=1, members=1, out=terminal)
    watching.starting("CVE-1")
    watching.asking("AV", "qwen")
    watching.asking("AC", "qwen")
    written = terminal.getvalue()
    assert "\r" in written
    assert COUNCIL_LINE in written
    # Nothing has closed the council phase, so no line has ended yet.
    assert "\n" not in written


def test_a_redirected_stream_gets_the_full_per_call_log_by_default():
    # The default off a terminal is the detailed log, so a saved run keeps every member.
    written = io.StringIO()
    watching = CouncilProgress(findings=1, members=1, out=written)
    watching.starting("CVE-1")
    watching.asking("AV", "qwen2.5:7b")
    assert written.getvalue() == "council 1/8  finding 1/1 CVE-1  AV  qwen2.5:7b\n"


def test_debug_at_a_terminal_gives_the_very_lines_a_redirected_stream_gives():
    # `--debug` keeps the log even at a terminal, byte for byte with a redirected run.
    terminal, redirected = FakeTerminal(), io.StringIO()
    driving_council(CouncilProgress(findings=1, members=1, out=terminal, debug=True))
    driving_council(CouncilProgress(findings=1, members=1, out=redirected))
    assert terminal.getvalue() == redirected.getvalue()
    assert "\r" not in terminal.getvalue()


def test_finishing_a_watched_run_closes_the_bar_line():
    terminal = FakeTerminal()
    watching = CouncilProgress(findings=1, members=1, out=terminal)
    watching.starting("CVE-1")
    watching.asking("AV", "qwen")
    watching.finish()
    assert terminal.getvalue().endswith("\n")


def test_finishing_a_logged_run_writes_nothing_more():
    written = io.StringIO()
    watching = CouncilProgress(findings=1, members=1, out=written)
    watching.starting("CVE-1")
    watching.asking("AV", "qwen")
    before = written.getvalue()
    watching.finish()
    assert written.getvalue() == before


def test_the_explainer_redraws_its_own_bar_at_a_terminal():
    terminal = FakeTerminal()
    ExplanationProgress(2, terminal).explaining("CVE-1", "big:27b")
    written = terminal.getvalue()
    assert "\r" in written
    assert written.strip().startswith("explanation")


def test_the_explainer_under_debug_gives_the_very_lines_a_redirected_stream_gives():
    terminal, redirected = FakeTerminal(), io.StringIO()
    driving_explanations(ExplanationProgress(2, terminal, debug=True))
    driving_explanations(ExplanationProgress(2, redirected))
    assert terminal.getvalue() == redirected.getvalue()
    assert "\r" not in terminal.getvalue()
