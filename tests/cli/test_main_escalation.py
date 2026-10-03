"""Guards on an escalation model already on the council: exit 2 saying why, and nothing scanned."""

import io

from cli import audit
from cli import main as entry
from cli.arguments import PROGRAM
from cli.main import COULD_NOT_RUN
from cli_samples import DATED, REPORTS_FOLDER, scanners_answering

ON_THE_COUNCIL = (
    "small is on the council, so it cannot also be the model the council's open metrics escalate to"
)


def scanned(*given) -> None:
    """Fail the test: no scanner may start once the escalation model is refused."""
    raise AssertionError(f"a scanner started, given {given}")


def test_an_escalation_model_on_the_council_exits_two_saying_why_before_any_scan(
    monkeypatch, tmp_path
):
    scanners_answering(monkeypatch)
    monkeypatch.setattr(audit.syft_runner, "scan_directory", scanned)
    monkeypatch.setattr(audit.trivy_runner, "scan_directory", scanned)
    monkeypatch.setattr(entry, "refuse_unrunnable", lambda repository, cache: DATED)
    monkeypatch.setenv("AUDITOR_ESCALATION_MODEL", "small")
    out, error = io.StringIO(), io.StringIO()
    given = [str(tmp_path), "--council-member", "small"]
    code = entry.main(given, out=out, error=error, reports=tmp_path / REPORTS_FOLDER)
    assert code == COULD_NOT_RUN
    assert error.getvalue() == f"{PROGRAM}: {ON_THE_COUNCIL}\n"
    assert out.getvalue() == ""
