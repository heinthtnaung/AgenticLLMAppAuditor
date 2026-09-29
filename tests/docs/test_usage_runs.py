"""What a marker's change tokens may say, and that no run in the usage guide asks for a council.

Everything after `run` in a marker is the command line, so a token that is
neither `--answers`, `(elided)` nor a `QUESTION=Answer` change is a typo in the
marker itself. Reading it as an argument the CLI happens not to know would put
this check's own mistake in front of a reader as a defect in the page, and send
them to correct a page that is right. The usage guide carries the one marker
that changes answers, so the refusal is tested on it.

Page parsing only -- no corpus, no scanners, no network -- so it runs in the
ordinary suite. Like the rest of `tests/docs`, it tests the guard and not the
page: green here says a mistyped change is refused, not that the guide is true.
"""

import pytest

from doc_pages import USAGE, read
from doc_runs import councils_asked_for, printed_runs
from docs_samples import marker_changed, run_changing_an_answer

UNREADABLE = "!"
NOT_A_CHANGE = "not a QUESTION=Answer change"


def test_a_change_token_that_cannot_be_read_is_refused():
    """A mistyped change would otherwise reach the CLI as an argument and be blamed on the page."""
    page = read(USAGE)
    run = run_changing_an_answer(page)
    question, answer = next(iter(run.edits.items()))
    written = f"{question}={answer}"
    damaged = marker_changed(page, run, written, f"{written}{UNREADABLE}")
    with pytest.raises(ValueError, match=NOT_A_CHANGE):
        printed_runs(damaged)


def test_no_documented_run_asks_for_a_council_so_none_reads_the_operator_s_settings():
    """The live check runs each block in a child process, which reads `.env` for a council run."""
    # `tests/conftest.py` keeps the operator's settings out of this process only,
    # and `cli.audit` reads them for a run asking for a council either way.
    assert councils_asked_for(read(USAGE)) == []
