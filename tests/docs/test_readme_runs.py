"""What a marker's change tokens may say, and the refusal when one cannot be read.

Everything after `run` in a marker is the command line, so a token that is
neither `--answers`, `(elided)` nor a `QUESTION=Answer` change is a typo in the
marker itself. Reading it as an argument the CLI happens not to know would put
this check's own mistake in front of a reader as a README defect, and send them
to correct a page that is right.

Page parsing only -- no corpus, no scanners, no network -- so it runs in the
ordinary suite. Like the rest of `tests/docs`, it tests the guard and not the
page: green here says a mistyped change is refused, not that the README is true.
"""

import pytest

from docs_samples import marker_changed, run_changing_an_answer
from readme_markers import read_readme
from readme_runs import printed_runs

UNREADABLE = "!"
NOT_A_CHANGE = "not a QUESTION=Answer change"


def test_a_change_token_that_cannot_be_read_is_refused():
    """A mistyped change would otherwise reach the CLI as an argument and be blamed on the page."""
    page = read_readme()
    run = run_changing_an_answer(page)
    question, answer = next(iter(run.edits.items()))
    written = f"{question}={answer}"
    damaged = marker_changed(page, run, written, f"{written}{UNREADABLE}")
    with pytest.raises(ValueError, match=NOT_A_CHANGE):
        printed_runs(damaged)
