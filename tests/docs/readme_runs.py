"""One marker read into the run it describes and the lines that run has to print.

The marker is the command: everything after `run` is the CLI's own arguments,
`--answers` hands the run the answer file the page prints, and any trailing
`QUESTION=Answer` token changes one answer in a copy of it first.

`(elided)` says the block is a selection of the run's output rather than the
whole of it, and it is the marker's job to say so rather than this file's to
guess: the way a test guesses is to try the strict comparison and fall back to
the loose one, which quietly downgrades every block on the day it drifts.

A token that is neither raises. Reading it as an argument the CLI happens not to
know would put the check's own typo in front of a reader as a README defect.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from readme_markers import (
    README_PATH,
    RUN_DIRECTIVE,
    marked_blocks,
    refuse_stray_markers,
    refuse_wrong_count,
)

ANSWERS_FLAG = "--answers"
ELIDED_TOKEN = "(elided)"
# The repository every documented run audits, spelled as the page spells it.
FETCHED = "fetched"
REPOSITORY = f"{FETCHED}/vulnscout"

EDIT = re.compile(r"(?P<question>[A-Z]+-\d+)=(?P<answer>[A-Za-z/]+)")


@dataclass(frozen=True)
class PrintedRun:
    """One block of CLI output in the README, and the command line that must reproduce it."""

    directive: str
    line_number: int
    printed: tuple[str, ...]
    wants_answers: bool
    edits: Mapping[str, str]
    # A selection of the output rather than the whole of it, so it can only be
    # asked to appear in order, not to appear entire. See `readme_drift`.
    elided: bool


def printed_runs(page: str) -> tuple[PrintedRun, ...]:
    """Give every block of CLI output the README prints, refusing a page that lost a marker."""
    refuse_stray_markers(page)
    runs = tuple(
        read_run(directive, body, line)
        for directive, body, line in marked_blocks(page)
        if directive.split()[0] == RUN_DIRECTIVE
    )
    refuse_wrong_count(len(runs), page)
    return runs


def arguments_of(run: PrintedRun, answer_file: Path) -> list[str]:
    """Give the arguments the CLI is run with for one block, the answer file only if asked for."""
    if not run.wants_answers:
        return [REPOSITORY]
    return [REPOSITORY, ANSWERS_FLAG, str(answer_file)]


def read_run(directive: str, body: str, line_number: int) -> PrintedRun:
    """Read one marker into the run it describes and the lines that run has to print."""
    _, *arguments = directive.split()
    named = [one for one in arguments if one not in (ANSWERS_FLAG, ELIDED_TOKEN)]
    printed = tuple(line.rstrip() for line in body.splitlines())
    if not any(line.strip() for line in printed):
        raise ValueError(f"the '{directive}' block at {README_PATH}:{line_number} prints nothing")
    return PrintedRun(
        directive=directive,
        line_number=line_number,
        printed=trimmed(printed),
        wants_answers=ANSWERS_FLAG in arguments,
        edits=read_edits(named, directive),
        elided=ELIDED_TOKEN in arguments,
    )


def trimmed(printed: tuple[str, ...]) -> tuple[str, ...]:
    """Drop the blank lines a fence leaves at either end, keeping the ones inside the block."""
    kept = list(printed)
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    return tuple(kept)


def read_edits(tokens: list[str], directive: str) -> dict[str, str]:
    """Read the `QUESTION=Answer` changes one marker makes to the README's answer file."""
    edits = {token: EDIT.fullmatch(token) for token in tokens}
    unreadable = sorted(token for token, match in edits.items() if not match)
    if unreadable:
        raise ValueError(
            f"{', '.join(unreadable)} in marker '{directive}' is not a QUESTION=Answer change"
        )
    return {match.group("question"): match.group("answer") for match in edits.values()}
