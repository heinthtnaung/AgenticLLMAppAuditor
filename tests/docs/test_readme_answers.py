"""What a marker may change in the answer file, and the refusal when no such question exists.

The CLI would refuse the derived file too, but it would refuse it as "a question
is missing" -- which points the reader at `answers.example.json` and the
approved library, rather than at the marker that actually carries the typo. So
the mismatch is caught here, where the marker can be named.

Page parsing only -- no corpus, no scanners, no network -- so it runs in the
ordinary suite. Like the rest of `tests/docs`, it tests the guard and not the
page: green here says a marker naming an unanswered question is refused, not
that the README is true.
"""

import pytest

from organisation.answers import ANSWERS_FIELD

from docs_samples import marker_changed, run_changing_an_answer
from readme_answers import answer_file, answers_for
from readme_markers import read_readme
from readme_runs import printed_runs

UNANSWERED_QUESTION = "XYZ-9"
NOT_ANSWERED = "does not answer"


def test_a_change_naming_a_question_the_answer_file_lacks_is_refused():
    """A marker changing a question nobody answers is the marker's mistake, and is named as one."""
    page = read_readme()
    # Without this the test could pass while changing a question that is answered,
    # which would prove nothing at all.
    assert UNANSWERED_QUESTION not in answer_file(page)[ANSWERS_FIELD]
    run = run_changing_an_answer(page)
    question = next(iter(run.edits))
    damaged = marker_changed(page, run, f"{question}=", f"{UNANSWERED_QUESTION}=")
    altered = [one for one in printed_runs(damaged) if UNANSWERED_QUESTION in one.edits]
    assert altered
    with pytest.raises(ValueError, match=NOT_ANSWERED):
        answers_for(altered[0], damaged)
