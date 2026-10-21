"""Guards on asking the approved questions at the terminal when no answer file was given.

The terminals are faked by `cli_samples.FakeTerminal`, whose `isatty` returns
True, so the suite asks nothing of a real keyboard and no test can hang: pytest's
own stdin is not a terminal, and every other run here writes to a plain
`StringIO`. The end-to-end runs through `main` live in `test_main_answers.py`.
"""

import io
import json
import os
from pathlib import Path

import pytest

from cli.arguments import Options
from cli.interactive_answers import (
    ANSWERS_SUFFIX,
    PROMPT_HINT,
    PROMPT_SUFFIX,
    answers_document,
    answers_entered,
    ask_one,
    prompt_for_answers,
    save_answers,
    should_prompt,
)
from cli.organisation_run import weigh_findings
from cli.report_files import CannotWriteReports
from cli_samples import (
    A_MIX,
    ADVISORY,
    LODASH,
    NO_TO_EVERYTHING,
    REPORTS_FOLDER,
    REPOSITORY_NAME,
    FakeTerminal,
    feed,
)
from findings.finding import build_finding
from organisation.answers import OrganisationAnswers, read_answers
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

FINDING = build_finding(LODASH, ADVISORY)
FIRST = APPROVED_QUESTIONS[0]
READ_ONLY = 0o400
NEEDS_PERMISSIONS = pytest.mark.skipif(
    os.geteuid() == 0, reason="root writes anywhere, so no permission refusal can be provoked"
)


def test_the_answers_suffix_is_the_literal_the_docs_quote():
    # The docs tell a reader to rerun with --answers <name>.answers.json, so it is pinned here.
    assert ANSWERS_SUFFIX == ".answers.json"


@pytest.mark.parametrize(
    "reply,expected",
    [
        ("y", Answer.YES), ("yes", Answer.YES), ("Y", Answer.YES),
        ("n", Answer.NO), ("no", Answer.NO), ("NO", Answer.NO),
        ("u", Answer.UNKNOWN), ("unknown", Answer.UNKNOWN),
    ],
)
def test_each_answer_form_is_understood(reply, expected):
    assert ask_one(FIRST, feed([reply]), FakeTerminal()) is expected


def test_a_bare_enter_is_unknown():
    # A person who presses Enter has said nobody knows, not No.
    assert ask_one(FIRST, feed([""]), FakeTerminal()) is Answer.UNKNOWN


def test_a_reply_nobody_offered_is_re_asked_with_a_hint():
    error = FakeTerminal()
    assert ask_one(FIRST, feed(["maybe", "y"]), error) is Answer.YES
    assert PROMPT_HINT in error.getvalue()
    # Asked again rather than scored: the prompt appears twice, the hint once.
    assert error.getvalue().count(PROMPT_SUFFIX) == 2


def test_not_applicable_is_file_only_so_na_at_the_prompt_is_re_asked():
    # N/A is a valid answer in a file; the prompt offers only y/n/U, so it re-asks.
    error = FakeTerminal()
    assert ask_one(FIRST, feed(["n/a", "n"]), error) is Answer.NO
    assert PROMPT_HINT in error.getvalue()


def test_end_of_input_on_one_question_stops_the_run_loudly():
    error = FakeTerminal()
    with pytest.raises(ValueError, match="input ended before"):
        ask_one(FIRST, feed([]), error)
    # The dangling prompt line is ended, so the refusal does not print after it.
    assert error.getvalue().endswith(f"{PROMPT_SUFFIX} \n")


def test_the_input_ending_before_the_questions_are_done_stops_the_run():
    with pytest.raises(ValueError, match="input ended before"):
        prompt_for_answers(feed(["y", "n"]), FakeTerminal())


def test_every_question_is_asked_once_in_the_library_order():
    error = FakeTerminal()
    answered = prompt_for_answers(feed(NO_TO_EVERYTHING), error)
    assert list(answered) == [asked.question_id for asked in APPROVED_QUESTIONS]
    for asked in APPROVED_QUESTIONS:
        assert f"{asked.question_id} {asked.text}" in error.getvalue()


def test_a_terminal_with_no_answer_file_is_asked():
    assert should_prompt(None, FakeTerminal(), FakeTerminal()) is True


@pytest.mark.parametrize(
    "answers,stdin,error",
    [
        (Path("answers.json"), FakeTerminal(), FakeTerminal()),
        (None, None, FakeTerminal()),
        (None, io.StringIO(), FakeTerminal()),
        (None, FakeTerminal(), io.StringIO()),
    ],
    ids=["file given", "stdin closed", "stdin piped", "error piped"],
)
def test_nothing_is_asked_without_both_terminals_and_no_file(answers, stdin, error):
    assert should_prompt(answers, stdin, error) is False


def test_a_file_that_cannot_be_saved_stops_the_run_before_asking(tmp_path):
    reports = tmp_path / REPORTS_FOLDER
    reports.mkdir()
    # A directory where the answers file would go cannot be overwritten with one.
    (reports / f"{REPOSITORY_NAME}{ANSWERS_SUFFIX}").mkdir()
    options = Options(tmp_path / REPOSITORY_NAME, "json", ())
    stdin = feed(NO_TO_EVERYTHING)
    with pytest.raises(CannotWriteReports, match=f"{REPOSITORY_NAME}{ANSWERS_SUFFIX} is a folder"):
        answers_entered(options, reports, stdin, FakeTerminal())
    assert stdin.tell() == 0


@NEEDS_PERMISSIONS
def test_an_answers_file_this_run_could_not_replace_stops_it_before_asking(tmp_path):
    reports = tmp_path / REPORTS_FOLDER
    reports.mkdir()
    left = reports / f"{REPOSITORY_NAME}{ANSWERS_SUFFIX}"
    left.write_text("{}", encoding="utf-8")
    left.chmod(READ_ONLY)
    stdin = feed(NO_TO_EVERYTHING)
    options = Options(tmp_path / REPOSITORY_NAME, "json", ())
    with pytest.raises(CannotWriteReports, match=f"{left.name} is not writable"):
        answers_entered(options, reports, stdin, FakeTerminal())
    assert stdin.tell() == 0


def test_the_saved_file_round_trips_through_read_answers_to_the_same_score(tmp_path):
    replies = prompt_for_answers(feed(A_MIX), FakeTerminal())
    saved = save_answers(replies, tmp_path / f"x{ANSWERS_SUFFIX}")
    read = read_answers(saved)
    assert read.everywhere == replies
    assert weigh_findings((FINDING,), read) == weigh_findings(
        (FINDING,), OrganisationAnswers(everywhere=replies)
    )


def test_the_saved_file_has_the_whole_shape_a_reader_needs(tmp_path):
    replies = prompt_for_answers(feed(A_MIX), FakeTerminal())
    saved = save_answers(replies, tmp_path / f"x{ANSWERS_SUFFIX}")
    expected = {
        "_questions": {asked.question_id: asked.text for asked in APPROVED_QUESTIONS},
        "answers": {question_id: answer.value for question_id, answer in replies.items()},
        "by_advisory": {},
        "approval": {},
    }
    assert answers_document(replies) == expected
    # A literal two-space indent and a trailing newline, like the example file an
    # operator edits; hardcoded so changing the indent in code turns this red.
    assert saved.read_text() == json.dumps(expected, indent=2) + "\n"
    assert saved.read_text().endswith("}\n")
