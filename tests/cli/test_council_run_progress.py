"""Guards on a council run's progress: its bar's line is closed even when a call raises."""

import pytest

from batch_samples import COUNCIL, ESCALATION, FINDINGS
from cli.council_run import assessments, watching
from cli_samples import FakeTerminal


def test_a_council_that_raises_still_closes_its_bar_line():
    # finish() runs in a finally, so a member that falls over still ends the bar's
    # line and a traceback starts below it rather than overwriting it.
    def exploding(member, prompt):
        """Fail as nothing the runner records a failure for would: an unexpected error."""
        raise RuntimeError("model fell over")

    out = FakeTerminal()
    progress = watching(FINDINGS, COUNCIL, out)
    with pytest.raises(RuntimeError):
        assessments(FINDINGS, COUNCIL, {"ollama": exploding}, progress, escalation=ESCALATION)
    assert "\r" in out.getvalue()
    assert out.getvalue().endswith("\n")
