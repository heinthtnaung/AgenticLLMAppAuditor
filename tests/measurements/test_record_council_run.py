"""Guards on the council-run recorder: it never loses a run, and it says what made one.

The command each test records is a real process, a stand-in for `audit` from
`recorder_samples`, run from a project laid out in `tmp_path`. Only git, Ollama
and the clock are answered from fixed text, so no test reads this checkout, a
running Ollama or the time.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# The recorder is a script beside the corpus it measures, not a package in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "measurements"))

import record_council_run as recorder  # noqa: E402
import run_provenance as provenance  # noqa: E402
from record_council_run import COULD_NOT_RECORD, RecordingFailed, main  # noqa: E402
from recorder_samples import (  # noqa: E402
    ANSWERS,
    AUDIT_SCRIPT,
    CANNOT_RUN,
    OPERATORS_OWN,
    PAGE,
    PROGRESS,
    RECORD,
    REPOSITORY,
    TEXT,
    audit_command,
    made_project,
)

COMMIT = "4111b958bae74b1f4b64dca48efc5a6ecca58f77"
SOURCE_STATUS = " M src/cli/council_run.py\n"
OLLAMA_HEADER = "NAME             ID              PROCESSOR\n"
# The recorder writes the table down as printed, wherever Ollama placed the model.
ON_GPU = OLLAMA_HEADER + "gemma4:latest    c6eb396dbd59    100% GPU\n"
ON_CPU = OLLAMA_HEADER + "gemma4:latest    c6eb396dbd59    100% CPU\n"
AT = "2026-09-23T17:46:36+08:00"
FOUND_SOMETHING = audit_command(1, REPOSITORY, ANSWERS)
# Exits 1, as an audit that found something does, having written no report.
REPORTS_LOST = (sys.executable, "-c", "import sys; sys.exit(1)")
# Exits 2 after printing, as an audit does when its scan ran and a report write
# failed. Printed upper-cased, because the provenance quotes the command itself.
WRITE_FAILED = (sys.executable, "-c", "import sys; print('rendering'.upper()); sys.exit(2)")


def answer_tools(monkeypatch, ollama: str) -> None:
    """Answer git and `ollama ps` from fixed text, and the clock with one time."""
    replies = {
        provenance.GIT_COMMIT: f"{COMMIT}\n",
        provenance.GIT_SOURCE_STATUS: SOURCE_STATUS,
        provenance.OLLAMA_PS: ollama,
    }
    monkeypatch.setattr(provenance, "captured", lambda command: replies[command])
    monkeypatch.setattr(provenance, "now", lambda: AT)


@pytest.fixture
def tools(monkeypatch):
    """Answer the tools with the model on the GPU."""
    answer_tools(monkeypatch, ON_GPU)


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    """Give an empty directory to record runs into."""
    made = tmp_path / "runs"
    made.mkdir()
    return made


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Give a project with a repository, an answer file, the stand-in and its own reports."""
    return made_project(tmp_path / "project")


def recorded(runs: Path, project: Path, command=FOUND_SOMETHING, name: str = "full"):
    """Record one run of `command` from `project`, and give its exit code and files."""
    code = main([name, "--", *command], directory=runs, root=project)
    return code, recorder.run_files(name, runs)


def test_the_three_renderings_and_the_progress_are_kept_byte_for_byte(tools, runs, project):
    # The relative paths resolve as written, or the stand-in would not have run.
    _, files = recorded(runs, project)
    assert (files.report.read_bytes(), files.record.read_bytes()) == (TEXT, RECORD)
    assert (files.page.read_bytes(), files.progress.read_text()) == (PAGE, PROGRESS)


def test_a_text_run_keeps_as_its_text_report_exactly_what_it_printed(tools, runs, project):
    # So the four runs recorded when stdout was the text report mean what they did.
    _, files = recorded(runs, project)
    printed = subprocess.run(FOUND_SOMETHING, cwd=project, capture_output=True).stdout
    assert files.report.read_bytes() == printed


def test_a_json_run_keeps_the_text_as_text_and_the_json_once(tools, runs, project):
    _, files = recorded(runs, project, audit_command(1, REPOSITORY, "--format", "json"))
    assert (files.report.read_bytes(), files.record.read_bytes()) == (TEXT, RECORD)


def test_the_projects_own_reports_are_neither_written_nor_replaced(tools, runs, project):
    before = sorted(path.relative_to(project) for path in project.rglob("*"))
    recorded(runs, project)
    assert sorted(path.relative_to(project) for path in project.rglob("*")) == before
    assert (project / "reports" / "vulnscout.json").read_bytes() == OPERATORS_OWN


def test_the_run_leaves_with_the_exit_code_the_audit_left_with(tools, runs, project):
    code, _ = recorded(runs, project)
    assert code == 1


def test_an_audit_that_could_not_run_is_recorded_with_no_reports_to_keep(tools, runs, project):
    code, files = recorded(runs, project, audit_command(1, "fetched/absent"))
    assert code == CANNOT_RUN
    assert [one.exists() for one in (files.report, files.record, files.page)] == [False] * 3
    assert "exit:    2" in files.provenance.read_text()


def test_an_audit_that_ran_and_left_no_json_is_not_recorded_as_whole(tools, runs, project):
    code, files = recorded(runs, project, REPORTS_LOST)
    assert code == COULD_NOT_RECORD
    assert "exit:    1" in files.provenance.read_text()


def test_the_rendering_a_failed_report_write_left_only_on_stdout_is_lost(tools, runs, project):
    # The accepted edge: stdout is not kept, so this rendering is kept nowhere.
    code, _ = recorded(runs, project, WRITE_FAILED)
    assert code == CANNOT_RUN
    assert not any(b"RENDERING" in one.read_bytes() for one in runs.iterdir())


@pytest.mark.parametrize("ollama", [ON_GPU, ON_CPU], ids=["on the GPU", "on the CPU"])
def test_the_provenance_says_what_the_run_came_from_and_how_it_ended(
    monkeypatch, runs, project, ollama
):
    answer_tools(monkeypatch, ollama)
    _, files = recorded(runs, project)
    lines = files.provenance.read_text().splitlines()
    assert lines[0].startswith("command: ")
    assert f"{AUDIT_SCRIPT} 1 {REPOSITORY} {ANSWERS}" in lines[0]
    assert lines[1:3] == [f"commit:  {COMMIT}", "src/ changes at launch:"]
    assert lines[3] == "   M src/cli/council_run.py"
    assert lines[4:7] == ["ollama ps at launch:", *provenance.indented(ollama)]
    assert lines[7:10] == [f"started: {AT}", f"ended:   {AT}", "exit:    1"]
    assert lines[10:] == ["ollama ps at end:", *provenance.indented(ollama)]


def test_placement_is_read_at_launch_and_at_the_end_and_nowhere_between(tools, runs, project):
    # The accepted gap: a member loaded and evicted mid-run is in neither section.
    _, files = recorded(runs, project)
    read = [line for line in files.provenance.read_text().splitlines() if "ollama ps" in line]
    assert read == ["ollama ps at launch:", "ollama ps at end:"]


def test_the_launch_is_on_disk_before_the_command_runs(tools, runs, project):
    # A run killed half way has to still say what it was. The program leaves with
    # 4, an exit no audit gives, so that it is asked for no reports.
    provenance_file = recorder.run_files("full", runs).provenance
    written = f"pathlib.Path({str(provenance_file)!r}).exists()"
    program = f"import pathlib, sys; sys.exit(4 if {written} else 3)"
    code, _ = recorded(runs, project, (sys.executable, "-c", program))
    assert code == 4


@pytest.mark.parametrize("kept", ["report", "record", "page", "progress", "provenance"])
def test_a_name_already_used_is_refused_and_the_run_there_is_left_alone(tools, runs, project, kept):
    taken = getattr(recorder.run_files("full", runs), kept)
    taken.write_text("an hour of evidence")
    code, _ = recorded(runs, project)
    assert code == COULD_NOT_RECORD
    assert [path.name for path in runs.iterdir()] == [taken.name]
    assert taken.read_text() == "an hour of evidence"


def test_a_command_that_is_not_on_the_path_is_refused_before_anything_is_written(
    tools, runs, project
):
    code, _ = recorded(runs, project, ("no-such-audit-command", "repo"))
    assert code == COULD_NOT_RECORD
    assert list(runs.iterdir()) == []


def test_a_git_that_cannot_answer_stops_the_run_before_it_starts(monkeypatch, runs, project):
    def failing(command):
        """Fail the way git does outside a repository."""
        raise RecordingFailed("git rev-parse HEAD exited 128: not a git repository")

    monkeypatch.setattr(provenance, "captured", failing)
    code, _ = recorded(runs, project)
    assert code == COULD_NOT_RECORD
    assert list(runs.iterdir()) == []
