"""Guards on the reports every run writes into its folder, beside what stdout gets."""

import io
import json
from pathlib import Path

import pytest

from cli import main as entry
from cli.arguments import JSON_FORMAT, REPORT_FORMATS, TEXT_FORMAT
from cli.main import COULD_NOT_RUN, RENDERERS, main
from cli.preflight import CannotRun
from cli.report_files import SUFFIXES, WRITTEN_TO, CannotWriteReports
from cli_samples import REPORTS_FOLDER, REPOSITORY_NAME, run_command_line

EVERY_REPORT = sorted(f"{REPOSITORY_NAME}{suffix}" for suffix in SUFFIXES.values())
# What a write that fails after the scan says, as `report_files.written` words it.
FULL_DISK = "cannot write reports/vulnscout.txt: No space left on device"


def saved(tmp_path: Path, report_format: str) -> Path:
    """Give the file one format of the test repository's report is written to."""
    return tmp_path / REPORTS_FOLDER / f"{REPOSITORY_NAME}{SUFFIXES[report_format]}"


def files_in_reports(tmp_path: Path) -> list[str]:
    """Name every file in the reports folder, sorted."""
    return sorted(one.name for one in (tmp_path / REPORTS_FOLDER).iterdir())


def scan_that_must_not_start(options, database, error):
    """Fail the test, because a run that should have been refused reached the scan."""
    raise AssertionError("the scan started although the reports could not be written")


def refused_by_the_preflight(repository, cache):
    """Refuse the run the way a missing database does."""
    raise CannotRun("no database")


def test_every_format_the_command_line_offers_is_rendered_and_saved():
    assert set(REPORT_FORMATS) == set(RENDERERS) == set(SUFFIXES)


def test_every_run_writes_all_three_formats_named_after_the_repository(monkeypatch, tmp_path):
    run_command_line([], monkeypatch, tmp_path)
    assert files_in_reports(tmp_path) == EVERY_REPORT


@pytest.mark.parametrize("report_format", REPORT_FORMATS)
def test_the_file_of_the_format_printed_is_byte_identical_to_stdout(
    monkeypatch, tmp_path, report_format
):
    _, out, _ = run_command_line(["--format", report_format], monkeypatch, tmp_path)
    assert saved(tmp_path, report_format).read_bytes() == out.encode("utf-8")


def test_a_format_not_printed_is_saved_as_it_would_have_been_printed(monkeypatch, tmp_path):
    run_command_line([], monkeypatch, tmp_path)
    kept = saved(tmp_path, JSON_FORMAT).read_text(encoding="utf-8")
    _, printed, _ = run_command_line(["--format", JSON_FORMAT], monkeypatch, tmp_path)
    assert kept == printed


def test_a_second_run_of_the_same_repository_overwrites_its_three_files(monkeypatch, tmp_path):
    run_command_line([], monkeypatch, tmp_path)
    _, out, _ = run_command_line([], monkeypatch, tmp_path, components=(), advisories={})
    assert files_in_reports(tmp_path) == EVERY_REPORT
    assert saved(tmp_path, TEXT_FORMAT).read_text(encoding="utf-8") == out
    assert "0 findings" in out


def test_where_the_reports_went_is_said_on_the_error_stream_and_never_on_stdout(
    monkeypatch, tmp_path
):
    _, out, error = run_command_line(["--format", JSON_FORMAT], monkeypatch, tmp_path)
    assert all(str(saved(tmp_path, one)) in error for one in REPORT_FORMATS)
    assert WRITTEN_TO not in out
    assert json.loads(out)["run"]["finding_count"] == 1


def test_a_folder_that_cannot_take_the_reports_refuses_the_run_before_the_scan(
    monkeypatch, tmp_path
):
    (tmp_path / REPORTS_FOLDER).write_text("", encoding="utf-8")
    monkeypatch.setattr(entry, "run_audit", scan_that_must_not_start)
    code, out, error = run_command_line([], monkeypatch, tmp_path)
    assert code == COULD_NOT_RUN
    assert out == ""
    assert error.startswith("audit: ") and "is not a folder the reports can go into" in error


def test_a_run_refused_before_the_scan_leaves_no_reports_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(entry, "refuse_unrunnable", refused_by_the_preflight)
    folder = tmp_path / REPORTS_FOLDER
    given = [str(tmp_path)]
    assert main(given, out=io.StringIO(), error=io.StringIO(), reports=folder) == COULD_NOT_RUN
    assert not folder.exists()


def test_a_report_that_cannot_be_written_after_the_scan_still_leaves_the_record_on_stdout(
    monkeypatch, tmp_path
):
    def failing(renderings, paths):
        """Fail the way a disk that filled during the scan does."""
        raise CannotWriteReports(FULL_DISK)

    monkeypatch.setattr(entry, "write_reports", failing)
    code, out, error = run_command_line([], monkeypatch, tmp_path)
    assert code == COULD_NOT_RUN
    assert out.startswith("Audit of")
    assert error == f"audit: {FULL_DISK}\n"
