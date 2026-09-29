"""The answer file a page prints, and the copies its markers derive from it.

A page that hands its runs an answer file prints that file itself, so each run
is derived from the file on its own page and never from another's. The README
runs its file as printed; the usage guide runs its own with two answers changed.
The derivation belongs with the marker that describes it rather than in prose
beside the block, so that **the test derives the varied file the same way the
page claims it is derived** -- which is the half a reader cannot check by eye
and the half that was wrong once already.

`organisation.answers` owns the field name, so this reads it from there. A
marker that changes a question the answer file does not answer is refused: the
CLI would refuse the file too, but it would refuse it as "a question is
missing", which points at the wrong document.
"""

import json

from organisation.answers import ANSWERS_FIELD

from doc_markers import ANSWERS_DIRECTIVE, marked_blocks
from doc_pages import Page
from doc_runs import PrintedRun


def answer_file(page: Page) -> dict:
    """Give the answer file a page prints, refusing a page carrying none or several."""
    bodies = [body for directive, body, _ in marked_blocks(page) if directive == ANSWERS_DIRECTIVE]
    if len(bodies) != 1:
        raise ValueError(
            f"{page.document.path} marks {len(bodies)} '{ANSWERS_DIRECTIVE}' blocks; this check "
            "needs exactly one to run the documented commands with"
        )
    document = json.loads(bodies[0])
    if isinstance(document, dict) and isinstance(document.get(ANSWERS_FIELD), dict):
        return document
    raise ValueError(
        f"the '{ANSWERS_DIRECTIVE}' block in {page.document.path} is not an object with an "
        f"'{ANSWERS_FIELD}' block, so no run can be given it"
    )


def answers_for(run: PrintedRun, page: Page) -> dict:
    """Give the answer file one run is handed, with the changes its marker names applied."""
    document = answer_file(page)
    answered = document[ANSWERS_FIELD]
    unanswered = sorted(set(run.edits) - set(answered))
    if unanswered:
        raise ValueError(
            f"marker '{run.directive}' changes {', '.join(unanswered)}, which the "
            f"'{ANSWERS_DIRECTIVE}' block in {page.document.path} does not answer"
        )
    return {**document, ANSWERS_FIELD: {**answered, **run.edits}}
