"""Guards on the entry point: three outcomes a pipeline can tell apart."""

import io
import json

import pytest

from cli import main as entry
from cli.main import COULD_NOT_RUN, FOUND_NOTHING, FOUND_SOMETHING, main
from cli.preflight import CannotRun
from cli_samples import BUILT_AT, TRIVY_VERSION, scanners_answering
from deps.scanner import ScannerFailed, ScannerUnavailable


def run(argv, monkeypatch, tmp_path, **scan):
    """Run the command line with the scanners answered and a database in place."""
    scanners_answering(monkeypatch, **scan)
    monkeypatch.setattr(entry, "refuse_unrunnable", lambda repository: BUILT_AT)
    out, error = io.StringIO(), io.StringIO()
    code = main([str(tmp_path), *argv], out=out, error=error)
    return code, out.getvalue(), error.getvalue()


def test_a_run_that_found_something_exits_one(monkeypatch, tmp_path):
    code, out, _ = run([], monkeypatch, tmp_path)
    assert code == FOUND_SOMETHING
    assert "CVE-2021-23337" in out


def test_a_run_that_found_nothing_exits_zero(monkeypatch, tmp_path):
    code, out, _ = run([], monkeypatch, tmp_path, components=(), advisories={})
    assert code == FOUND_NOTHING
    assert "0 findings" in out


@pytest.mark.parametrize(
    "fault",
    [CannotRun("no database"), ScannerFailed("trivy exited 1"), ScannerUnavailable("no syft")],
    ids=["cannot run", "scanner failed", "scanner absent"],
)
def test_a_run_that_could_not_happen_exits_two_and_says_why(monkeypatch, tmp_path, fault):
    # Never 0: a broken scan sharing an exit code with a clean repository is how
    # a pipeline goes green on a scan that never ran.
    def refuse(repository):
        raise fault

    monkeypatch.setattr(entry, "refuse_unrunnable", refuse)
    out, error = io.StringIO(), io.StringIO()
    assert main([str(tmp_path)], out=out, error=error) == COULD_NOT_RUN
    assert out.getvalue() == ""
    assert str(fault) in error.getvalue()


def test_the_three_outcomes_are_three_different_codes():
    assert len({FOUND_NOTHING, FOUND_SOMETHING, COULD_NOT_RUN}) == 3


def test_a_bad_command_line_also_leaves_by_the_could_not_run_door():
    # argparse exits 2 of its own accord, which is the code this tool uses too.
    with pytest.raises(SystemExit) as leaving:
        main(["--format", "html", "somewhere"])
    assert leaving.value.code == COULD_NOT_RUN


def test_the_terminal_rendering_is_what_a_run_prints_by_default(monkeypatch, tmp_path):
    _, out, _ = run([], monkeypatch, tmp_path)
    assert out.startswith("Audit of")


def test_the_audit_record_is_valid_json_when_asked_for(monkeypatch, tmp_path):
    _, out, _ = run(["--format", "json"], monkeypatch, tmp_path)
    record = json.loads(out)
    assert record["run"]["trivy_version"] == TRIVY_VERSION
    assert [entry_["source"] for entry_ in record["findings"][0]["scores"]] == ["ghsa", "nvd"]


def test_what_was_not_assessed_is_printed_rather_than_left_out(monkeypatch, tmp_path):
    _, out, _ = run([], monkeypatch, tmp_path)
    assert "Organisation Risk Score" in out
    assert "Approval record" in out


def test_nothing_is_written_to_the_error_stream_by_a_run_that_worked(monkeypatch, tmp_path):
    _, _, error = run([], monkeypatch, tmp_path)
    assert error == ""
