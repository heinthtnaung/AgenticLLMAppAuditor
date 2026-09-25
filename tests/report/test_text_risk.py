"""Guards on the organisation score on the page: the contested bands first, flags visible."""

from dataclasses import replace

from council_runs import council_ran
from full_runs import ADVISORY_ID, fully_assessed
from organisation.risk import FindingRisk, assess, per_source
from report.council_beside import COUNCIL_SOURCE, NOT_IN_THE_SCORE
from report.record import build_report
from report.text_risk import risk_block
from report_samples import PROVENANCE, catalogue, component, finding
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


DJANGO = component()
PYYAML = component("pyyaml", "5.1")

# Internet-facing but disabled: exposure 40 - 30 = 10, nothing else answered Yes.
ON_THE_BOUNDARY = all_answers({"EXP-1": Answer.YES, "EXP-5": Answer.YES})
SETTLED = all_answers({"EXP-1": Answer.YES})
UNSURE = all_answers({"EXP-1": Answer.UNKNOWN})

HIGH_LOW = "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:L/A:L"  # 7.0
HIGH_HIGH = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"  # 7.5
TOTAL_LOSS = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"  # 9.8


def block(*weighed, findings=(), council=()):
    """Render the risk block of a report carrying these scores."""
    return risk_block(build_report(PROVENANCE, catalogue(DJANGO), findings, {}, council, weighed))


def weighed(one, answers):
    """Score one finding against an environment."""
    return assess(one, answers, per_source(one))


def test_a_run_nobody_answered_for_shows_no_risk_block():
    assert block() == ""


def test_the_weighting_that_combined_the_categories_heads_the_block():
    # The category scores were re-derivable and the total was not: the 30/25/25/20
    # weighting lived only in `docs/SCORING_MODEL.md`.
    one = finding(DJANGO, advisory_id="CVE-1", vectors={"ghsa": HIGH_HIGH})
    rendered = block(weighed(one, SETTLED))
    assert "weighted Technical severity 0.3, Exposure and reachability 0.25," in rendered
    assert "Business impact 0.25, Threat and exploitation 0.2" in rendered


def test_a_finding_all_its_sources_agree_on_shows_one_score():
    one = finding(DJANGO, advisory_id="CVE-1", vectors={"ghsa": HIGH_HIGH})
    rendered = block(weighed(one, SETTLED))
    assert "CVE-1" in rendered
    assert " to " not in rendered


def test_a_finding_its_sources_disagree_on_shows_the_range_with_each_end_named():
    # Where the band moves, which source sits at which end is the reader's
    # immediate next question, and an unattributed range invites a guess.
    one = finding(DJANGO, advisory_id="CVE-1", vectors={"a": HIGH_LOW, "b": HIGH_HIGH})
    assert "a 23.5 to b 25.0" in block(weighed(one, ON_THE_BOUNDARY))


def test_a_single_score_is_not_attributed_because_there_is_nothing_to_attribute():
    one = finding(DJANGO, advisory_id="CVE-1", vectors={"ghsa": HIGH_HIGH})
    rendered = block(weighed(one, SETTLED))
    assert "ghsa" not in rendered
    assert " to " not in rendered


def test_a_finding_whose_band_the_source_changes_says_both_bands():
    one = finding(DJANGO, advisory_id="CVE-1", vectors={"a": HIGH_LOW, "b": HIGH_HIGH})
    rendered = block(weighed(one, ON_THE_BOUNDARY))
    assert "Medium and Low" in rendered
    assert "the source changes the band on 1" in rendered


def test_the_findings_whose_band_depends_on_the_source_come_first():
    # The question this can newly answer, so it is what the block leads with --
    # ahead of a finding that scores higher. Ordering by score alone would put
    # the settled 31.9 above the contested 23.5-to-25.0, and the contested one
    # is the one a reader has a decision to make about.
    contested = finding(
        DJANGO, advisory_id="CVE-CONTESTED", vectors={"a": HIGH_LOW, "b": HIGH_HIGH}
    )
    settled = finding(PYYAML, advisory_id="CVE-SETTLED", vectors={"a": TOTAL_LOSS})
    weighed_settled = weighed(settled, ON_THE_BOUNDARY)
    assert weighed_settled.scores[0].score > 25.0
    rendered = block(
        weighed_settled,
        weighed(contested, ON_THE_BOUNDARY),
        findings=(contested, settled),
    )
    assert rendered.index("CVE-CONTESTED") < rendered.index("CVE-SETTLED")


def test_nothing_says_the_source_changes_a_band_when_none_does():
    one = finding(DJANGO, advisory_id="CVE-1", vectors={"ghsa": HIGH_HIGH})
    assert "changes the band" not in block(weighed(one, SETTLED))


def test_a_provisional_score_is_marked_on_its_own_line_not_footnoted():
    # An Unknown answer produces a number that is calculated and flagged, and a
    # flag a reader can miss is the same as no flag.
    one = finding(DJANGO, advisory_id="CVE-1", vectors={"ghsa": HIGH_HIGH})
    assert "provisional" in block(weighed(one, UNSURE))


def test_a_settled_score_is_not_marked_provisional():
    one = finding(DJANGO, advisory_id="CVE-1", vectors={"ghsa": HIGH_HIGH})
    assert "provisional" not in block(weighed(one, SETTLED))


def test_a_finding_nobody_scored_is_weighed_and_comes_out_provisional():
    one = finding(DJANGO, advisory_id="CVE-1", vectors={})
    rendered = block(weighed(one, SETTLED))
    assert "CVE-1" in rendered
    assert "provisional" in rendered


def test_a_councils_settled_vector_is_shown_under_its_finding_and_said_to_be_unused():
    # Its members settled 9.8 on a finding ghsa put at 7.5. The ruling: beside
    # the published score, on the CVSS scale, and never weighed into it.
    lines = risk_block(fully_assessed()).split("\n")
    scored = next(at for at, one in enumerate(lines) if ADVISORY_ID in one)
    assert lines[scored + 1].strip() == f"{COUNCIL_SOURCE} CVSS 9.8  ·  {NOT_IN_THE_SCORE}"


def test_the_score_lines_are_the_same_with_a_council_beside_them_as_without():
    # Anything reading the council's vector into the score moves this line.
    beside = risk_block(fully_assessed()).split("\n")
    alone = risk_block(replace(fully_assessed(), council={}))
    assert [one for one in beside if COUNCIL_SOURCE not in one] == alone.split("\n")
    assert COUNCIL_SOURCE not in alone


def test_the_councils_figure_keeps_the_bands_column_in_line_with_a_range():
    settled = fully_assessed().risk[ADVISORY_ID]
    ranged = finding(PYYAML, advisory_id="CVE-2", vectors={"a": HIGH_LOW, "b": TOTAL_LOSS})
    scored = (settled, weighed(ranged, SETTLED))
    lines = block(*scored, council=(council_ran(ADVISORY_ID),)).split("\n")
    columns = {bands_column(lines, one) for one in scored}
    assert len(columns) == 1


def bands_column(lines: list[str], weighed_one: FindingRisk) -> int:
    """Give where one finding's bands start on its line of the block."""
    line = next(one for one in lines if one.strip().startswith(weighed_one.advisory_id))
    return line.index(" and ".join(weighed_one.bands), len(weighed_one.advisory_id))
