"""Guards on the council-run recorder: it never loses a run, and it says what made one.

The command each test records is a real process, a one-line Python program, so
the streams and the exit code travel the way an audit's do and no model is asked.
Only git, Ollama and the clock are answered from fixed text, so no test reads this
checkout, a running Ollama or the time.
"""

import sys
from pathlib import Path

import pytest

# The recorder is a script beside the corpus it measures, not a package in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "measurements"))

import record_council_run as recorder  # noqa: E402
from record_council_run import COULD_NOT_RECORD, RecordingFailed, main  # noqa: E402

COMMIT = "4111b958bae74b1f4b64dca48efc5a6ecca58f77"
SOURCE_STATUS = " M src/cli/council_run.py\n"
OLLAMA_HEADER = "NAME             ID              PROCESSOR\n"
# The recorder writes the table down as printed, wherever Ollama placed the model.
ON_GPU = OLLAMA_HEADER + "gemma4:latest    c6eb396dbd59    100% GPU\n"
ON_CPU = OLLAMA_HEADER + "gemma4:latest    c6eb396dbd59    100% CPU\n"
AT = "2026-09-23T17:46:36+08:00"
# One line to each stream, then exit 1, which is how an audit that found
# something leaves.
FOUND_SOMETHING_PROGRAM = (
    "import sys; print('report'); "
    "print('call 1/8', file=sys.stderr); sys.exit(1)"
)
FOUND_SOMETHING = (sys.executable, "-c", FOUND_SOMETHING_PROGRAM)


def answer_tools(monkeypatch, ollama: str) -> None:
    """Answer git and `ollama ps` from fixed text, and the clock with one time."""
    replies = {
        recorder.GIT_COMMIT: f"{COMMIT}\n",
        recorder.GIT_SOURCE_STATUS: SOURCE_STATUS,
        recorder.OLLAMA_PS: ollama,
    }
    monkeypatch.setattr(recorder, "captured", lambda command: replies[command])
    monkeypatch.setattr(recorder, "now", lambda: AT)


@pytest.fixture
def tools(monkeypatch):
    """Answer the tools with the model on the GPU."""
    answer_tools(monkeypatch, ON_GPU)


def recorded(tmp_path: Path, command: tuple[str, ...] = FOUND_SOMETHING, name: str = "full"):
    """Record one run into a directory of its own, and give its exit code and files."""
    code = main([name, "--", *command], directory=tmp_path)
    return code, recorder.run_files(name, tmp_path)


def test_the_name_and_the_command_are_read_either_side_of_the_separator():
    read = recorder.parse_invocation(["full", "--", "audit", "repo", "--council-all-findings"])
    assert read.name == "full"
    assert read.command == ("audit", "repo", "--council-all-findings")


@pytest.mark.parametrize(
    "argv",
    [["full", "audit", "repo"], ["full", "--"], ["--", "audit"], ["a", "b", "--", "audit"]],
    ids=["no separator", "no command", "no name", "two names"],
)
def test_a_command_line_that_does_not_say_name_then_command_is_refused(argv):
    with pytest.raises(RecordingFailed, match="usage"):
        recorder.parse_invocation(argv)


@pytest.mark.parametrize("name", ["../full", "runs/full", ""])
def test_a_name_that_would_put_a_file_elsewhere_is_refused(name):
    with pytest.raises(RecordingFailed):
        recorder.parse_invocation([name, "--", "audit"])


def test_a_run_writes_each_stream_to_its_own_file(tools, tmp_path):
    _, files = recorded(tmp_path)
    assert files.report.read_text() == "report\n"
    assert files.progress.read_text() == "call 1/8\n"


def test_the_run_leaves_with_the_exit_code_the_audit_left_with(tools, tmp_path):
    code, _ = recorded(tmp_path)
    assert code == 1


@pytest.mark.parametrize("ollama", [ON_GPU, ON_CPU], ids=["on the GPU", "on the CPU"])
def test_the_provenance_says_what_the_run_came_from_and_how_it_ended(monkeypatch, tmp_path, ollama):
    answer_tools(monkeypatch, ollama)
    _, files = recorded(tmp_path)
    lines = files.provenance.read_text().splitlines()
    assert lines[0].startswith("command: ") and "import sys" in lines[0]
    assert lines[1:3] == [f"commit:  {COMMIT}", "src/ changes at launch:"]
    assert lines[3] == "   M src/cli/council_run.py"
    assert lines[4:7] == ["ollama ps at launch:", *recorder.indented(ollama)]
    assert lines[7:10] == [f"started: {AT}", f"ended:   {AT}", "exit:    1"]
    assert lines[10:] == ["ollama ps at end:", *recorder.indented(ollama)]


def test_placement_is_read_at_launch_and_at_the_end_and_nowhere_between(tools, tmp_path):
    # The accepted gap: a member loaded and evicted mid-run is in neither section.
    _, files = recorded(tmp_path)
    read = [line for line in files.provenance.read_text().splitlines() if "ollama ps" in line]
    assert read == ["ollama ps at launch:", "ollama ps at end:"]


def test_the_launch_is_on_disk_before_the_command_runs(tools, tmp_path):
    # A run killed half way has to still say what it was.
    provenance = recorder.run_files("full", tmp_path).provenance
    written = f"pathlib.Path({str(provenance)!r}).exists()"
    program = f"import pathlib, sys; sys.exit(0 if {written} else 3)"
    code, _ = recorded(tmp_path, (sys.executable, "-c", program))
    assert code == 0


def test_a_name_already_used_is_refused_and_the_run_there_is_left_alone(tools, tmp_path):
    kept = recorder.run_files("full", tmp_path).report
    kept.write_text("an hour of evidence")
    code, _ = recorded(tmp_path)
    assert code == COULD_NOT_RECORD
    assert kept.read_text() == "an hour of evidence"
    assert not recorder.run_files("full", tmp_path).provenance.exists()


def test_a_command_that_is_not_on_the_path_is_refused_before_anything_is_written(tools, tmp_path):
    code, _ = recorded(tmp_path, ("no-such-audit-command", "repo"))
    assert code == COULD_NOT_RECORD
    assert list(tmp_path.iterdir()) == []


def test_a_git_that_cannot_answer_stops_the_run_before_it_starts(monkeypatch, tmp_path):
    def failing(command):
        """Fail the way git does outside a repository."""
        raise RecordingFailed("git rev-parse HEAD exited 128: not a git repository")

    monkeypatch.setattr(recorder, "captured", failing)
    code, _ = recorded(tmp_path)
    assert code == COULD_NOT_RECORD
    assert list(tmp_path.iterdir()) == []


def test_ollama_unreadable_once_the_run_is_over_is_recorded_rather_than_raised(monkeypatch):
    # The exit code is already in hand by then, and raising would lose it.
    def failing(command):
        """Fail the way `ollama ps` does with the server down."""
        raise RecordingFailed("ollama ps exited 1: could not connect")

    monkeypatch.setattr(recorder, "captured", failing)
    assert recorder.ollama_at_end() == "unavailable: ollama ps exited 1: could not connect"
