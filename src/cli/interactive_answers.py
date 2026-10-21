"""Ask the approved questions at the terminal when no answer file was given.

**Only when stdin and the error stream are both a terminal, and only before the
scan.** A pipe, CI or the test suite is asked nothing -- a question there would
hang a script -- so the run computes no Organisation Risk Score, exactly as a run
given no answer file. When a person is at the keyboard the twelve questions are
asked before the scan, so a council run that takes an hour is never interrupted
partway to ask one.

**The prompt is on the error stream, never on stdout.** `input()` writes its
prompt to stdout, which would land in a piped `--format json` record, so the
prompt is written to the error stream and a line is read from stdin by hand.

**The replies are saved beside the report, in the example file's shape.** So a
rerun with `--answers <that file>` reproduces the same Organisation Risk Score,
and the record says the answers were typed rather than read from a file.
"""

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Mapping, TextIO

from cli.arguments import Options
from cli.report_files import CannotWriteReports, repository_name, written
from organisation.answers import ANSWERS_FIELD, APPROVAL_FIELD, BY_ADVISORY_FIELD
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer, Question

# Named after the report and ending in the format it is, so it reads as an answer
# file and `--answers <name>.answers.json` is the obvious rerun.
ANSWERS_SUFFIX = ".answers.json"
# The example file carries each question's text under this key; the reader ignores
# it, so this writer keeps it, for an operator who later edits the file.
QUESTIONS_FIELD = "_questions"
JSON_INDENT = 2

PROMPT_SUFFIX = "[y/n/U]"
PROMPT_HINT = "answer y, n or u, or press Enter for Unknown"
# At end of input before the twelve are answered: loud, and before the scan.
NO_ANSWER_AT_PROMPT = (
    "the input ended before the questions were answered; rerun with --answers FILE, "
    "or answer every question at the prompt"
)
# What the record says the answers were: typed at a prompt, then saved here, where
# a later terminal run may overwrite them.
TYPED_AND_SAVED = "typed at the prompt and saved to {path}"

# A bare Enter is Unknown, so the empty string maps there beside the spelt words.
# N/A is deliberately absent: it is a file-only answer, re-asked at the prompt.
ANSWER_BY_REPLY: Mapping[str, Answer] = {
    "": Answer.UNKNOWN,
    "y": Answer.YES,
    "yes": Answer.YES,
    "n": Answer.NO,
    "no": Answer.NO,
    "u": Answer.UNKNOWN,
    "unknown": Answer.UNKNOWN,
}


def should_prompt(answers: Path | None, stdin: TextIO | None, error: TextIO) -> bool:
    """Say whether to ask: no file given, and stdin and the error stream are both a terminal."""
    return answers is None and stdin is not None and stdin.isatty() and error.isatty()


def answers_entered(
    options: Options, reports_directory: Path, stdin: TextIO | None, error: TextIO
) -> tuple[Options, str]:
    """Ask the questions when interactive and unanswered, saving the replies beside the report."""
    if not should_prompt(options.answers, stdin, error):
        return options, ""
    path = answers_path(options.repository, reports_directory)
    # Checked before the human is asked twelve questions, so a file that cannot be
    # saved stops the run now rather than after the typing is done.
    refuse_unsavable(path)
    saved = save_answers(prompt_for_answers(stdin, error), path)
    return replace(options, answers=saved), TYPED_AND_SAVED.format(path=saved)


def prompt_for_answers(stdin: TextIO, error: TextIO) -> dict[str, Answer]:
    """Ask every approved question in order, giving the id-to-answer map the file is built from."""
    return {asked.question_id: ask_one(asked, stdin, error) for asked in APPROVED_QUESTIONS}


def ask_one(asked: Question, stdin: TextIO, error: TextIO) -> Answer:
    """Ask one question on the error stream until the reply is one we understand."""
    while True:
        error.write(f"{asked.question_id} {asked.text} {PROMPT_SUFFIX} ")
        error.flush()
        answer = ANSWER_BY_REPLY.get(read_reply(stdin, error).strip().lower())
        if answer is not None:
            return answer
        error.write(f"{PROMPT_HINT}\n")


def read_reply(stdin: TextIO, error: TextIO) -> str:
    """Read one reply, ending the prompt line and stopping the run loudly at end of input."""
    # readline gives "" only at end of input; a bare Enter gives "\n", which is Unknown.
    line = stdin.readline()
    if line == "":
        # End the dangling prompt line so the refusal does not print after it.
        error.write("\n")
        raise ValueError(NO_ANSWER_AT_PROMPT)
    return line


def answers_path(repository: Path, reports_directory: Path) -> Path:
    """Name the file the typed answers are saved to, beside the report and named for it."""
    return reports_directory / f"{repository_name(repository)}{ANSWERS_SUFFIX}"


def refuse_unsavable(path: Path) -> None:
    """Refuse an answers file this run could not save, naming it, before anyone is asked."""
    if path.is_dir():
        raise CannotWriteReports(f"{path} is a folder, so the typed answers cannot be saved there")
    if path.exists() and not os.access(path, os.W_OK):
        raise CannotWriteReports(f"{path} is not writable, so the typed answers cannot replace it")


def save_answers(replies: Mapping[str, Answer], path: Path) -> Path:
    """Write the typed answers in the example file's shape, overwriting the last run's."""
    return written(path, json.dumps(answers_document(replies), indent=JSON_INDENT) + "\n")


def answers_document(replies: Mapping[str, Answer]) -> dict:
    """Build the answer file the reader round-trips: the questions, answers and empty blocks."""
    return {
        QUESTIONS_FIELD: {asked.question_id: asked.text for asked in APPROVED_QUESTIONS},
        ANSWERS_FIELD: {question_id: answer.value for question_id, answer in replies.items()},
        BY_ADVISORY_FIELD: {},
        APPROVAL_FIELD: {},
    }
