"""Guards on the entry point: three outcomes a pipeline can tell apart."""

import io
import json

import pytest

from cli import audit as audit_module
from cli import main as entry
from cli.main import COULD_NOT_RUN, FOUND_NOTHING, FOUND_SOMETHING, main
from cli.preflight import CannotRun
from cli.report_files import WRITTEN_TO
from cli_samples import REPORTS_FOLDER, TRIVY_VERSION, run_command_line, written_answers
from deps.scanner import ScannerFailed, ScannerUnavailable
from deps.trivy_database import CACHE_VARIABLE, XDG_CACHE_VARIABLE
from report.absences import (
    NOTHING_ABSENT,
    NOTHING_TO_PUT,
    NOTHING_TO_WEIGH,
    NO_ANSWERS_GIVEN,
    NO_COUNCIL_RUN,
)

FOUND_NOTHING_AT_ALL = {"components": (), "advisories": {}}
MEMBER = ["--council-member", "qwen2.5:7b-instruct"]


def test_a_run_that_found_something_exits_one(monkeypatch, tmp_path):
    code, out, _ = run_command_line([], monkeypatch, tmp_path)
    assert code == FOUND_SOMETHING
    assert "CVE-2021-23337" in out


def test_a_run_that_found_nothing_exits_zero(monkeypatch, tmp_path):
    code, out, _ = run_command_line([], monkeypatch, tmp_path, components=(), advisories={})
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
    def refuse(repository, cache):
        """Refuse the run with the fault under test."""
        raise fault

    monkeypatch.setattr(entry, "refuse_unrunnable", refuse)
    out, error = io.StringIO(), io.StringIO()
    reports = tmp_path / REPORTS_FOLDER
    assert main([str(tmp_path)], out=out, error=error, reports=reports) == COULD_NOT_RUN
    assert out.getvalue() == ""
    assert str(fault) in error.getvalue()


def test_the_three_outcomes_are_three_different_codes():
    assert len({FOUND_NOTHING, FOUND_SOMETHING, COULD_NOT_RUN}) == 3


def test_a_bad_command_line_also_leaves_by_the_could_not_run_door():
    # argparse exits 2 of its own accord, which is the code this tool uses too.
    with pytest.raises(SystemExit) as leaving:
        main(["--format", "yaml", "somewhere"])
    assert leaving.value.code == COULD_NOT_RUN


def test_the_trivy_cache_the_environment_names_is_the_one_the_preflight_dates(
    monkeypatch, tmp_path
):
    # Resolved once from the environment and handed on, so the database dated is
    # the database scanned; `tests/cli/test_audit.py` holds the scan to it.
    named = tmp_path / "trivy-cache"
    monkeypatch.setenv(CACHE_VARIABLE, str(named))
    handed = []

    def recording(repository, cache):
        """Record the cache the run was handed, then stop it before any scan."""
        handed.append(cache)
        raise CannotRun("stopped once the cache was seen")

    monkeypatch.setattr(entry, "refuse_unrunnable", recording)
    main([str(tmp_path)], out=io.StringIO(), error=io.StringIO(), reports=tmp_path / REPORTS_FOLDER)
    assert handed == [named]


def test_a_relative_xdg_cache_home_stops_the_run_and_says_why(monkeypatch, tmp_path):
    # Trivy keeps its cache in a temporary directory then, so there is no one
    # database to date and scan with.
    monkeypatch.delenv(CACHE_VARIABLE, raising=False)
    monkeypatch.setenv(XDG_CACHE_VARIABLE, "relative")
    error = io.StringIO()
    reports = tmp_path / REPORTS_FOLDER
    assert main([str(tmp_path)], out=io.StringIO(), error=error, reports=reports) == COULD_NOT_RUN
    assert "which is relative" in error.getvalue()


def test_the_terminal_rendering_is_what_a_run_prints_by_default(monkeypatch, tmp_path):
    _, out, _ = run_command_line([], monkeypatch, tmp_path)
    assert out.startswith("Audit of")


def test_the_audit_record_is_valid_json_when_asked_for(monkeypatch, tmp_path):
    _, out, _ = run_command_line(["--format", "json"], monkeypatch, tmp_path)
    record = json.loads(out)
    assert record["run"]["trivy_version"] == TRIVY_VERSION
    assert [entry_["source"] for entry_ in record["findings"][0]["scores"]] == ["ghsa", "nvd"]


def test_what_was_not_assessed_is_printed_rather_than_left_out(monkeypatch, tmp_path):
    _, out, _ = run_command_line([], monkeypatch, tmp_path)
    assert "Organisation Risk Score" in out
    assert "Approval record" in out


def test_a_run_that_worked_says_only_where_its_reports_went(monkeypatch, tmp_path):
    # A scan with no council takes about a second and needs no progress at all.
    _, _, error = run_command_line([], monkeypatch, tmp_path)
    assert error.startswith(WRITTEN_TO)
    assert error.count("\n") == 1


def reporting_council(findings, roster, clients=None, progress=None, every_finding=False):
    """Stand in for a council run, saying what it is doing through the progress it was given."""
    progress.starting("CVE-2021-23337")
    progress.asking("AV", "qwen2.5:7b-instruct")
    return ()


def test_progress_is_said_on_the_error_stream_and_never_on_stdout(monkeypatch, tmp_path):
    # The whole constraint: `--format json` writes the record to stdout and it
    # has to stay pipeable, so progress and the record share a process and
    # nothing else.
    monkeypatch.setattr(audit_module, "assessments", reporting_council)
    given = ["--council-member", "qwen2.5:7b-instruct"]
    _, out, error = run_command_line(given, monkeypatch, tmp_path)
    assert error.strip()
    assert error.strip() not in out
    assert out.startswith("Audit of")


def test_the_audit_record_stays_parseable_while_progress_is_being_said(monkeypatch, tmp_path):
    monkeypatch.setattr(audit_module, "assessments", reporting_council)
    given = ["--council-member", "qwen2.5:7b-instruct", "--format", "json"]
    _, out, error = run_command_line(given, monkeypatch, tmp_path)
    assert error.strip()
    assert json.loads(out)["run"]["finding_count"] == 1


def test_progress_locates_the_run_by_finding_metric_and_member(monkeypatch, tmp_path):
    monkeypatch.setattr(audit_module, "assessments", reporting_council)
    given = ["--council-member", "qwen2.5:7b-instruct"]
    _, _, error = run_command_line(given, monkeypatch, tmp_path)
    assert "CVE-2021-23337" in error
    assert "AV" in error
    assert "qwen2.5:7b-instruct" in error


def absent_from(out: str) -> dict[str, str]:
    """Read what a JSON record names as not assessed, and why."""
    return {one["what"]: one["because"] for one in json.loads(out)["not_assessed"]}


def test_answers_with_no_finding_to_weigh_are_not_reported_as_never_given(monkeypatch, tmp_path):
    # Found in acceptance testing: the answer file's approval was printed just
    # above "no organisation answers were supplied".
    given = ["--answers", str(written_answers(tmp_path)), "--format", "json"]
    _, out, _ = run_command_line(given, monkeypatch, tmp_path, **FOUND_NOTHING_AT_ALL)
    absent = absent_from(out)
    assert absent["Organisation Risk Score"] == NOTHING_TO_WEIGH
    assert "Approval record" not in absent


def test_a_council_with_no_finding_to_put_to_it_is_not_reported_as_never_run(monkeypatch, tmp_path):
    given = [*MEMBER, "--format", "json"]
    _, out, _ = run_command_line(given, monkeypatch, tmp_path, **FOUND_NOTHING_AT_ALL)
    assert absent_from(out)["Council ruling"] == NOTHING_TO_PUT


def test_a_run_that_asked_for_nothing_and_found_nothing_still_says_so(monkeypatch, tmp_path):
    given = ["--format", "json"]
    _, out, _ = run_command_line(given, monkeypatch, tmp_path, **FOUND_NOTHING_AT_ALL)
    absent = absent_from(out)
    assert absent["Organisation Risk Score"] == NO_ANSWERS_GIVEN
    assert absent["Council ruling"] == NO_COUNCIL_RUN


def test_a_run_with_nothing_to_weigh_or_put_is_never_told_nothing_is_absent(monkeypatch, tmp_path):
    given = ["--answers", str(written_answers(tmp_path)), *MEMBER]
    _, out, _ = run_command_line(given, monkeypatch, tmp_path, **FOUND_NOTHING_AT_ALL)
    assert NOTHING_TO_WEIGH in out and NOTHING_TO_PUT in out
    assert NOTHING_ABSENT not in out
