"""Guards on the derivation behind a score: four answers, and no figure off the engine.

**Four answers, never two.** Yes, No, Unknown and N/A all reach the page as the
organisation gave them, and Unknown is marked because it is the one that makes a
score provisional. A page offering two would turn a guess into evidence.

**Nothing here is read off the scoring engine.** Every figure in a derivation
is the record's own, the four category weights included, which is what makes the
number re-derivable rather than restated.
"""

import re

from organisation.risk import assess, per_source
from report.html_answers import derivation
from report_samples import component, finding
from scoring.library import APPROVED_QUESTIONS, question
from scoring.question import Answer

DJANGO = component()

WEIGHTING = re.compile(r'<p class="weighting">([^<]*)</p>')
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


FOUR_ANSWERS = all_answers({
    "EXP-1": Answer.YES,
    "EXP-4": Answer.NOT_APPLICABLE,
    "THR-1": Answer.UNKNOWN,
})
CONTROLLED = all_answers({"EXP-4": Answer.YES, "EXP-5": Answer.YES})


def page_of(answers) -> str:
    """Render the derivation of one finding scored against one environment."""
    one = finding(DJANGO)
    return derivation(assess(one, answers, per_source(one)))


def test_the_weighting_that_combined_the_categories_is_on_the_page():
    # Without it the total cannot be re-derived from the page, and a reader has
    # to open `docs/SCORING_MODEL.md` to finish arithmetic everything else here
    # supports.
    page = page_of(FOUR_ANSWERS)
    assert "Weighted Technical severity 0.3" in page
    assert "Exposure and reachability 0.25" in page
    assert "Business impact 0.25" in page
    assert "Threat and exploitation 0.2." in page


def test_all_four_answers_reach_the_page_as_the_organisation_gave_them():
    page = page_of(FOUR_ANSWERS)
    assert ">Yes</span>" in page
    assert ">No</span>" in page
    assert ">Unknown</span>" in page
    assert ">N/A</span>" in page


def test_an_unknown_answer_is_marked_because_it_is_what_makes_a_score_provisional():
    page = page_of(FOUR_ANSWERS)
    assert '<span class="answer-value flag">Unknown</span>' in page
    assert '<span class="answer-value">No</span>' in page


def test_every_question_is_named_by_its_id_and_its_text():
    page = page_of(FOUR_ANSWERS)
    assert ">EXP-1</span>" in page
    assert question("EXP-1").text in page


def test_an_answer_carries_what_a_yes_was_worth_and_what_it_contributed():
    page = page_of(FOUR_ANSWERS)
    assert "yes 40, contributed 40" in page
    assert "yes 50, contributed 0.0" in page


def test_a_clamped_category_says_so_because_the_clamp_is_invisible_in_the_score():
    page = page_of(CONTROLLED)
    assert "raw total -45" in page
    assert "clamped" in page


def test_every_weight_on_the_page_is_the_records_own_in_the_records_order():
    # It was read off `scoring.risk_score.CATEGORY_WEIGHTS` once, which made the
    # page a second place a weight was stated and a second place one could
    # differ. Ordered and exact, because 0.25 and 0.2 are also question weights:
    # a wrongly restated weighting could still land on a figure held elsewhere.
    one = finding(DJANGO)
    weighed = assess(one, FOUR_ANSWERS, per_source(one))
    carried = [str(term.weight) for term in weighed.scores[0].weights]
    said = WEIGHTING.search(derivation(weighed)).group(1)
    assert NUMBER.findall(said) == carried


def test_the_derivation_is_collapsed_because_eighteen_by_twelve_is_not_a_page():
    page = page_of(FOUR_ANSWERS)
    assert page.startswith("<details>")
    assert "<summary>How this number was reached</summary>" in page


def test_the_technical_term_is_given_once_per_source_and_the_rest_once():
    # The environment does not change with who published a vector; only the
    # technical term does, which is why a finding is scored per source at all.
    one = finding(DJANGO, vectors={
        "ghsa": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:L/A:L",
        "nvd": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    })
    page = derivation(assess(one, FOUR_ANSWERS, per_source(one)))
    assert page.count(">technical</span>") == 2
    assert page.count(">EXP-1</span>") == 1
