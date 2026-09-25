"""Guards on reading the recorder's command line: one plain name, then the command."""

import sys
from pathlib import Path

import pytest

# The recorder is a script beside the corpus it measures, not a package in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "measurements"))

import record_council_run as recorder  # noqa: E402
from record_council_run import RecordingFailed  # noqa: E402


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
