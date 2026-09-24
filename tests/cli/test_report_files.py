"""Guards on where the reports go: one folder, three files, named after the repository."""

import os
from pathlib import Path
from typing import Iterator

import pytest

from cli.arguments import HTML_FORMAT, JSON_FORMAT, TEXT_FORMAT
from cli.report_files import (
    REPORTS_DIRECTORY,
    CannotWriteReports,
    planned_reports,
    report_paths,
    repository_name,
    where_written,
    write_reports,
)

RENDERINGS = {
    TEXT_FORMAT: "Audit of fetched/vulnscout\n",
    JSON_FORMAT: '{"run": {"finding_count": 0}}\n',
    HTML_FORMAT: "<!doctype html>\n<title>Audit — vulnscout</title>\n",
}
LAST_RUN = {one: f"the last run's {one}\n" for one in RENDERINGS}
# Read and search, but no write; read and write, but no search; a file read only.
NO_WRITE = 0o500
NO_SEARCH = 0o600
READ_ONLY = 0o400
OWNER_ALL = 0o700
NEEDS_PERMISSIONS = pytest.mark.skipif(
    os.geteuid() == 0, reason="root writes anywhere, so no permission refusal can be provoked"
)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Make a repository directory where a fetched one would be."""
    made = tmp_path / "fetched" / "vulnscout"
    made.mkdir(parents=True)
    return made


@pytest.fixture
def reports(tmp_path: Path) -> Iterator[Path]:
    """Give an empty reports folder, left removable however a test locked it."""
    folder = tmp_path / "reports"
    folder.mkdir()
    yield folder
    folder.chmod(OWNER_ALL)


def contents(paths: dict[str, Path]) -> dict[str, str]:
    """Read each format's file back."""
    return {one: path.read_text(encoding="utf-8") for one, path in paths.items()}


def test_the_reports_go_where_the_command_was_run():
    assert REPORTS_DIRECTORY == Path("reports")


def test_each_format_is_one_file_named_after_the_repository(repository, reports):
    names = {one: path.name for one, path in report_paths(repository, reports).items()}
    assert names == {
        TEXT_FORMAT: "vulnscout.txt", JSON_FORMAT: "vulnscout.json", HTML_FORMAT: "vulnscout.html",
    }


def test_the_current_directory_is_called_by_its_own_name(repository, monkeypatch):
    monkeypatch.chdir(repository)
    assert repository_name(Path(".")) == "vulnscout"


def test_a_symlinked_repository_keeps_the_name_it_was_given(repository, tmp_path):
    given = tmp_path / "given"
    given.symlink_to(repository, target_is_directory=True)
    assert repository_name(given) == "given"


def test_a_repository_with_no_directory_name_is_refused():
    with pytest.raises(CannotWriteReports, match="no directory name"):
        repository_name(Path("/"))


def test_two_repositories_with_one_name_share_their_report_files(tmp_path, reports):
    # Accepted: the name is the directory's, so `a/app` and `b/app` overwrite
    # each other's reports.
    first = report_paths(tmp_path / "a" / "app", reports)
    assert first == report_paths(tmp_path / "b" / "app", reports)


def test_a_missing_folder_is_made_and_nothing_is_written_into_it(repository, tmp_path):
    folder = tmp_path / "out" / "reports"
    planned_reports(repository, folder)
    assert list(folder.iterdir()) == []


def test_a_file_where_the_folder_should_be_is_refused(repository, tmp_path):
    folder = tmp_path / "reports"
    folder.write_text("", encoding="utf-8")
    with pytest.raises(CannotWriteReports, match="is not a folder the reports can go into"):
        planned_reports(repository, folder)


@NEEDS_PERMISSIONS
@pytest.mark.parametrize("mode", [NO_WRITE, NO_SEARCH], ids=["no write", "no search"])
def test_a_folder_no_file_can_be_made_in_is_refused(repository, reports, mode):
    reports.chmod(mode)
    with pytest.raises(CannotWriteReports, match="is not writable"):
        planned_reports(repository, reports)


def test_a_folder_where_a_report_should_be_is_refused(repository, reports):
    (reports / "vulnscout.json").mkdir()
    with pytest.raises(CannotWriteReports, match="vulnscout.json is a folder"):
        planned_reports(repository, reports)


@NEEDS_PERMISSIONS
def test_a_report_this_run_could_not_replace_is_refused(repository, reports):
    left = reports / "vulnscout.html"
    left.write_text("", encoding="utf-8")
    left.chmod(READ_ONLY)
    with pytest.raises(CannotWriteReports, match="vulnscout.html is not writable"):
        planned_reports(repository, reports)


def test_each_rendering_is_written_to_its_own_file(repository, reports):
    paths = planned_reports(repository, reports)
    assert write_reports(RENDERINGS, paths) == tuple(paths.values())
    assert contents(paths) == RENDERINGS


def test_a_second_run_replaces_the_first_runs_files(repository, reports):
    # No clock in `src/`, so no time in a name: the same repository reuses its files.
    paths = planned_reports(repository, reports)
    write_reports(LAST_RUN, paths)
    write_reports(RENDERINGS, paths)
    assert contents(paths) == RENDERINGS
    assert len(list(reports.iterdir())) == len(RENDERINGS)


def test_a_write_failing_part_way_leaves_this_runs_files_beside_the_last_runs(
    repository, reports
):
    # Accepted: the three are written one after another, not all or none, so a
    # failure on the second leaves the first from this run and the third from the last.
    paths = planned_reports(repository, reports)
    write_reports(LAST_RUN, paths)
    first, second, third = paths
    failing = {**paths, second: reports / "gone" / paths[second].name}
    with pytest.raises(CannotWriteReports, match=paths[second].name):
        write_reports(RENDERINGS, failing)
    assert paths[first].read_text(encoding="utf-8") == RENDERINGS[first]
    assert paths[third].read_text(encoding="utf-8") == LAST_RUN[third]


def test_a_file_that_cannot_be_written_is_named(tmp_path):
    missing = tmp_path / "gone" / "vulnscout.txt"
    with pytest.raises(CannotWriteReports, match="cannot write .*vulnscout.txt"):
        write_reports(RENDERINGS, {TEXT_FORMAT: missing})


def test_where_the_reports_went_is_one_line_naming_every_file(repository, reports):
    paths = tuple(report_paths(repository, reports).values())
    said = where_written(paths)
    assert said.count("\n") == 1 and said.endswith("\n")
    assert [str(path) in said for path in paths] == [True, True, True]
