"""Guards on where a recorded audit runs, and on what is kept of what it wrote there."""

import sys
from pathlib import Path

import pytest

# The recorder is a script beside the corpus it measures, not a package in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "measurements"))

from run_directory import keep_reports, link_project  # noqa: E402
from run_provenance import RecordingFailed  # noqa: E402
from recorder_samples import OPERATORS_OWN, PAGE, RECORD, TEXT, made_project  # noqa: E402

RAN = 1
COULD_NOT_RUN = 2


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Give an empty directory for an audit to run in."""
    made = tmp_path / "working"
    made.mkdir()
    return made


def written(working: Path, **reports: bytes) -> None:
    """Write reports into `working/reports/` as an audit would, by suffix."""
    (working / "reports").mkdir()
    for suffix, content in reports.items():
        (working / "reports" / f"vulnscout.{suffix}").write_bytes(content)


def test_every_entry_of_the_project_is_linked_but_its_reports(tmp_path, working):
    project = made_project(tmp_path / "project")
    link_project(project, working)
    linked = sorted(path.name for path in working.iterdir())
    assert linked == sorted(path.name for path in project.iterdir() if path.name != "reports")
    assert all((working / name).resolve() == (project / name).resolve() for name in linked)


def test_the_audits_reports_never_reach_the_projects_through_a_link(tmp_path, working):
    project = made_project(tmp_path / "project")
    link_project(project, working)
    written(working, json=RECORD)
    assert (project / "reports" / "vulnscout.json").read_bytes() == OPERATORS_OWN


def kept_in(tmp_path: Path) -> dict[str, Path]:
    """Name the three files a run called `full` keeps its renderings in."""
    return {
        "text": tmp_path / "full.report.txt",
        "record": tmp_path / "full.report.json",
        "page": tmp_path / "full.report.html",
    }


def test_all_three_renderings_are_copied_byte_for_byte(tmp_path, working):
    written(working, txt=TEXT, json=RECORD, html=PAGE)
    kept = kept_in(tmp_path)
    keep_reports(working, **kept, exit_code=RAN)
    assert [path.read_bytes() for path in kept.values()] == [TEXT, RECORD, PAGE]


def test_an_audit_that_ran_and_wrote_no_json_is_refused_by_name(tmp_path, working):
    written(working, txt=TEXT, html=PAGE)
    kept = kept_in(tmp_path)
    with pytest.raises(RecordingFailed, match="exited 1 but wrote no .json report"):
        keep_reports(working, **kept, exit_code=RAN)
    assert (kept["text"].read_bytes(), kept["page"].read_bytes()) == (TEXT, PAGE)


def test_an_audit_that_could_not_run_is_asked_for_no_reports(tmp_path, working):
    keep_reports(working, **kept_in(tmp_path), exit_code=COULD_NOT_RUN)
    assert list(tmp_path.glob("full.*")) == []


def test_two_reports_of_one_kind_are_refused_rather_than_one_guessed(tmp_path, working):
    written(working, json=RECORD)
    (working / "reports" / "other.json").write_bytes(RECORD)
    with pytest.raises(RecordingFailed, match="more than one report of a kind"):
        keep_reports(working, **kept_in(tmp_path), exit_code=RAN)
