"""Guards on the whole run when it asks the questions at the prompt, driven through `main`.

The unit-level prompt tests are in `test_interactive_answers.py`; these drive the
entry point end to end, with both streams faked as terminals so the run prompts.
"""

import io
import json

from cli import main as entry
from cli.interactive_answers import ANSWERS_SUFFIX, PROMPT_SUFFIX, TYPED_AND_SAVED
from cli.main import FOUND_SOMETHING, main
from cli_samples import (
    A_MIX,
    DATED,
    NO_TO_EVERYTHING,
    REPORTS_FOLDER,
    REPOSITORY_NAME,
    FakeTerminal,
    feed,
    run_command_line,
    scanners_answering,
    written_answers,
)
from report.absences import NO_ANSWERS_GIVEN
from scoring.library import APPROVED_QUESTIONS

JSON = ["--format", "json"]


def run_interactive(argv, monkeypatch, tmp_path, replies):
    """Run the command line with both streams a terminal, scanners answered, reports in tmp_path."""
    scanners_answering(monkeypatch)
    monkeypatch.setattr(entry, "refuse_unrunnable", lambda repository, cache: DATED)
    out, error, stdin = io.StringIO(), FakeTerminal(), feed(replies)
    repository = tmp_path / REPOSITORY_NAME
    repository.mkdir(exist_ok=True)
    reports = tmp_path / REPORTS_FOLDER
    code = main([str(repository), *argv], out=out, error=error, reports=reports, stdin=stdin)
    return code, out.getvalue(), error.getvalue(), reports


def test_the_prompts_go_to_the_error_stream_and_never_to_stdout(monkeypatch, tmp_path):
    code, out, error, _ = run_interactive(JSON, monkeypatch, tmp_path, NO_TO_EVERYTHING)
    assert code == FOUND_SOMETHING
    # The prompt is marked by its [y/n/U] suffix; the question text alone also
    # appears in the JSON risk derivation, so the suffix is what tells a prompt apart.
    for asked in APPROVED_QUESTIONS:
        assert f"{asked.question_id} {asked.text} {PROMPT_SUFFIX}" in error
    assert PROMPT_SUFFIX not in out
    assert json.loads(out)["run"]["finding_count"] == 1


def test_the_record_says_the_answers_were_typed_and_where_they_were_saved(monkeypatch, tmp_path):
    _, out, _, reports = run_interactive(JSON, monkeypatch, tmp_path, NO_TO_EVERYTHING)
    saved = reports / f"{REPOSITORY_NAME}{ANSWERS_SUFFIX}"
    assert saved.exists()
    assert json.loads(out)["run"]["answers_source"] == TYPED_AND_SAVED.format(path=saved)
    assert json.loads(out)["run"]["answers_source"].endswith(f"saved to {saved}")


def test_without_a_terminal_nothing_is_asked_and_no_score_is_computed(monkeypatch, tmp_path):
    code, out, error = run_command_line([], monkeypatch, tmp_path)
    assert code == FOUND_SOMETHING
    assert NO_ANSWERS_GIVEN in out
    assert PROMPT_SUFFIX not in error
    assert not (tmp_path / REPORTS_FOLDER / f"{REPOSITORY_NAME}{ANSWERS_SUFFIX}").exists()


def test_a_closed_stdin_does_not_crash_the_run(monkeypatch, tmp_path):
    # `audit repo <&-` leaves sys.stdin None; the run must complete, not fall over
    # on an AttributeError that a pipeline would read as findings.
    monkeypatch.setattr("sys.stdin", None)
    code, out, _ = run_command_line([], monkeypatch, tmp_path)
    assert code == FOUND_SOMETHING
    assert "CVE-2021-23337" in out


def test_with_an_answer_file_the_prompt_is_never_shown(monkeypatch, tmp_path):
    answers = written_answers(tmp_path)
    given = ["--answers", str(answers)]
    _, _, error, reports = run_interactive(given, monkeypatch, tmp_path, NO_TO_EVERYTHING)
    assert PROMPT_SUFFIX not in error
    # No prompt means no saved prompt file: the stdin replies were never read.
    assert not (reports / f"{REPOSITORY_NAME}{ANSWERS_SUFFIX}").exists()


def test_rerunning_with_the_saved_file_gives_the_same_score(monkeypatch, tmp_path):
    _, typed_out, _, reports = run_interactive(JSON, monkeypatch, tmp_path, A_MIX)
    saved = reports / f"{REPOSITORY_NAME}{ANSWERS_SUFFIX}"
    given = ["--format", "json", "--answers", str(saved)]
    _, file_out, _ = run_command_line(given, monkeypatch, tmp_path)
    typed, on_file = json.loads(typed_out), json.loads(file_out)
    typed_risk = [one["organisation_risk"] for one in typed["findings"]]
    assert typed_risk == [one["organisation_risk"] for one in on_file["findings"]]
    assert typed_risk[0] is not None
    # The only difference a typed run leaves in the record: where the answers came from.
    assert "answers_source" in typed["run"]
    assert "answers_source" not in on_file["run"]


def test_a_run_given_no_stdin_reads_the_real_one(monkeypatch, tmp_path):
    # The `audit` command calls main() with no streams, so the prompt reads sys.stdin.
    monkeypatch.setattr("sys.stdin", feed(NO_TO_EVERYTHING))
    scanners_answering(monkeypatch)
    monkeypatch.setattr(entry, "refuse_unrunnable", lambda repository, cache: DATED)
    repository = tmp_path / REPOSITORY_NAME
    repository.mkdir()
    out, error = io.StringIO(), FakeTerminal()
    main([str(repository), *JSON], out=out, error=error, reports=tmp_path / REPORTS_FOLDER)
    assert "answers_source" in json.loads(out.getvalue())["run"]
