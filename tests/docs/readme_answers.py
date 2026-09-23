"""The answer file the README prints, and the copies its markers derive from it.

The page shows one answer file and runs it three ways: unanswered, as printed,
and with two answers changed. The derivation belongs with the marker that
describes it rather than in prose beside the block, so that **the test derives
the varied file the same way the page claims it is derived** -- which is the
half a reader cannot check by eye and the half that was wrong once already.

`organisation.answers` owns the field name, so this reads it from there. A
marker that changes a question the answer file does not answer is refused: the
CLI would refuse the file too, but it would refuse it as "a question is
missing", which points at the wrong document.
"""

import json

from organisation.answers import ANSWERS_FIELD

from readme_markers import ANSWERS_DIRECTIVE, README_PATH, marked_blocks
from readme_runs import PrintedRun


def answer_file(page: str) -> dict:
    """Give the answer file the README prints, refusing a page carrying none or several."""
    bodies = [body for directive, body, _ in marked_blocks(page) if directive == ANSWERS_DIRECTIVE]
    if len(bodies) != 1:
        raise ValueError(
            f"{README_PATH} marks {len(bodies)} '{ANSWERS_DIRECTIVE}' blocks; this check needs "
            "exactly one to run the documented commands with"
        )
    document = json.loads(bodies[0])
    if isinstance(document, dict) and isinstance(document.get(ANSWERS_FIELD), dict):
        return document
    raise ValueError(
        f"the '{ANSWERS_DIRECTIVE}' block in {README_PATH} is not an object with an "
        f"'{ANSWERS_FIELD}' block, so no run can be given it"
    )


def answers_for(run: PrintedRun, page: str) -> dict:
    """Give the answer file one run is handed, with the changes its marker names applied."""
    document = answer_file(page)
    answered = document[ANSWERS_FIELD]
    unanswered = sorted(set(run.edits) - set(answered))
    if unanswered:
        raise ValueError(
            f"marker '{run.directive}' changes {', '.join(unanswered)}, which the README's "
            f"'{ANSWERS_DIRECTIVE}' block does not answer"
        )
    return {**document, ANSWERS_FIELD: {**answered, **run.edits}}
