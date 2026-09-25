"""Guards on the Organisation Risk Score on the page: this system's claim, kept apart.

`docs/SCORING_MODEL.md` refuses to merge the two claims a page carries, so a
published CVSS score and an organisation score never share a chip, a shape or a
scale -- and the scale is written on every badge because two bare numbers in two
bands read as one number somebody got wrong.

A finding is scored once per published source, and which source sits at which
end is the reader's next question, so every score names its own.
"""

import re
from dataclasses import replace

from full_runs import fully_assessed
from organisation.risk import assess, per_source
from report.council_beside import COUNCIL_SOURCE, NOT_IN_THE_SCORE
from report.html_risk import risk_section
from report.record import build_report
from report_samples import PROVENANCE, TOTAL_LOSS, catalogue, component, finding
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

DJANGO = component()

GHSA_HIGH = "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:L/A:L"  # 7.0
NVD_CRITICAL = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"  # 9.8


def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


EXPOSED = all_answers({"EXP-1": Answer.YES, "BUS-1": Answer.YES, "BUS-2": Answer.YES})
UNSURE = all_answers({"EXP-1": Answer.UNKNOWN})
# The one list of sources in the risk section, which is the council's row.
COUNCIL_ROW = re.compile(r'<ul class="sources">.*?</ul>')


def page_of(one, answers) -> str:
    """Render the risk section for one finding scored against one environment."""
    weighed = assess(one, answers, per_source(one))
    return risk_section(build_report(PROVENANCE, catalogue(DJANGO), (one,), {}, (), (weighed,)))


def test_a_run_nobody_answered_for_shows_no_risk_section():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert risk_section(report) == ""


def test_an_organisation_score_is_never_written_on_a_cvss_chip():
    # Two different claims on two different scales about one finding. A CVE that
    # is CVSS Critical and organisation Low is the normal case, not an error.
    page = page_of(finding(DJANGO), EXPOSED)
    assert '<span class="scale">org</span>' in page
    assert '<span class="scale">cvss</span>' not in page


def test_the_scale_is_on_every_badge_and_not_only_in_the_heading():
    page = page_of(finding(DJANGO), EXPOSED)
    assert page.count('<span class="scale">org</span>') == page.count('class="risk band-')


def test_a_finding_is_scored_once_per_source_and_each_score_names_its_own():
    two = finding(DJANGO, vectors={"ghsa": GHSA_HIGH, "nvd": NVD_CRITICAL})
    page = page_of(two, EXPOSED)
    assert '<span class="source-name">ghsa</span>' in page
    assert '<span class="source-name">nvd</span>' in page


def test_a_finding_whose_band_moves_with_the_source_is_flagged_on_its_heading():
    # The question this section can newly answer, and it has both answers.
    two = finding(DJANGO, vectors={"ghsa": GHSA_HIGH, "nvd": NVD_CRITICAL})
    page = page_of(two, EXPOSED)
    assert "the source changes the band" in page


def test_an_unknown_answer_leaves_the_score_provisional_and_says_which_question():
    page = page_of(finding(DJANGO), UNSURE)
    assert '<span class="flag">provisional</span>' in page
    assert "unknown: EXP-1" in page


def test_a_finding_nobody_published_a_vector_for_says_so_rather_than_naming_a_source():
    page = page_of(finding(DJANGO, vectors={}), EXPOSED)
    assert "no source scored this" in page


def test_the_derivation_travels_with_the_score_it_explains():
    # A score nobody can re-derive is not a score.
    page = page_of(finding(DJANGO), EXPOSED)
    assert "How this number was reached" in page
    assert page.index("class=\"risk-scores\"") < page.index("How this number was reached")


def test_a_councils_settled_vector_is_shown_beside_the_scores_on_a_cvss_chip():
    # Its members settled 9.8 on a finding ghsa put at 7.5. The ruling: beside
    # the published score, on the CVSS scale, and never weighed into it.
    row = COUNCIL_ROW.search(risk_section(fully_assessed())).group(0)
    assert f'<span class="source-name">{COUNCIL_SOURCE}</span>' in row
    assert '<span class="scale">cvss</span><span class="value">9.8</span>' in row
    assert TOTAL_LOSS in row
    assert NOT_IN_THE_SCORE in row


def test_the_organisation_scores_are_the_same_with_a_council_beside_them_as_without():
    # Anything reading the council's vector into a score moves the section.
    beside = risk_section(fully_assessed())
    alone = risk_section(replace(fully_assessed(), council={}))
    assert COUNCIL_ROW.sub("", beside) == alone
    assert COUNCIL_SOURCE not in alone
