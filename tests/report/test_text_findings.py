"""Guards on how a finding is written: contested first, one line when they agree."""

from report.record import build_report
from report.text_report import as_text
from report_samples import (
    BOTTOM_OF_HIGH,
    CONFIDENTIALITY_ONLY,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    REFUSED_DISSENT,
    TOP_OF_MEDIUM,
    TEMPORAL_VECTOR,
    TOTAL_LOSS,
    VERSION_2_VECTOR,
    WIDE_WITHIN_MEDIUM,
    catalogue,
    component,
    finding,
)

DJANGO = component()
PYYAML = component("pyyaml", "5.1")


def rendered(findings=(), components=(DJANGO,)):
    """Render one report from whatever a test is about."""
    return as_text(build_report(PROVENANCE, catalogue(*components), findings, {}))


def lines_under(heading: str, text: str) -> list[str]:
    """Give the indented lines of one section, so a test can read its order."""
    after = text.split(heading)[1].split("\n\n")[0]
    return [line for line in after.split("\n") if line.startswith("  ")]

def test_the_contested_findings_come_before_the_agreeing_ones():
    # A reader's question is where the sources disagree, so that is what the
    # page leads with rather than the record's own order.
    text = rendered((
        finding(DJANGO, advisory_id="CVE-2", vectors={"a": CONFIDENTIALITY_ONLY}),
        finding(PYYAML, advisory_id="CVE-1", vectors={"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY}),
    ))
    assert text.index("SOURCES DISAGREE") < text.index("SOURCES AGREE")


def test_a_band_crossing_disagreement_is_listed_above_a_wider_one_inside_a_band():
    text = rendered((
        finding(
            PYYAML, advisory_id="CVE-WIDE", vectors={"a": WIDE_WITHIN_MEDIUM, "b": TOP_OF_MEDIUM}
        ),
        finding(DJANGO, advisory_id="CVE-BAND", vectors={"a": TOP_OF_MEDIUM, "b": BOTTOM_OF_HIGH}),
    ))
    assert text.index("CVE-BAND") < text.index("CVE-WIDE")


def test_a_contested_finding_shows_the_spread_the_bands_and_the_metrics():
    text = rendered((finding(DJANGO, vectors={"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY}),))
    assert "4.5 apart" in text
    assert "Critical and Medium" in text
    assert "differ on C, I, A" in text


def test_every_source_is_shown_side_by_side_with_no_winner_marked():
    text = rendered((finding(DJANGO, vectors={"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY}),))
    assert "a 9.8  ·  b 5.3" in text
    assert "wins" not in text and "authoritative" not in text


def test_sources_that_agree_on_a_number_and_not_on_the_reading_are_still_contested():
    # 6.5 and 6.5, three metrics apart. Filed by score it would read as settled.
    same = {"ghsa": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N",
            "nvd": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:L"}
    text = rendered((finding(DJANGO, vectors=same),))
    assert "SOURCES DISAGREE (1)" in text
    assert "0.0 apart" in text and "differ on I, A" in text


def test_an_agreeing_finding_takes_one_line():
    text = rendered((finding(DJANGO, vectors={"a": TOTAL_LOSS, "b": TOTAL_LOSS}),))
    assert len(lines_under("SOURCES AGREE (1)", text)) == 1
    assert "9.8  Critical  2 sources" in text


def test_a_finding_nobody_scored_gets_its_own_group_and_not_a_zero():
    text = rendered((finding(DJANGO, vectors={}),))
    assert "NOT SCORED (1)" in text
    assert "no source published a v3 vector" in text
    assert "0.0" not in text


def test_a_finding_whose_only_source_was_refused_says_which():
    text = rendered((finding(DJANGO, vectors={"nvd": VERSION_2_VECTOR}),))
    assert "no readable vector; refused nvd" in text


def test_sources_that_match_beside_a_refused_one_are_not_filed_as_agreeing():
    # A heading is a claim, and a vector nobody could read may disagree with every
    # one that was, as ghsa's does on CVE-2020-11023.
    text = rendered((finding(DJANGO, vectors=REFUSED_DISSENT),))
    assert "SOURCES AGREE" not in text
    assert len(lines_under("A SOURCE WAS REFUSED (1)", text)) == 1
    assert "6.1  Medium    3 sources read  ·  refused ghsa" in text


def test_a_disputed_finding_names_its_refused_source_beside_the_ones_it_read():
    # As the web page's card does: a refused vector stays on the page, and no
    # corpus finding carries one beside a dispute, so ghsa's real one is put there.
    read = {"ghsa": TEMPORAL_VECTOR, "nvd": TOTAL_LOSS, "redhat": LOW_CONFIDENTIALITY}
    text = rendered((finding(DJANGO, vectors=read),))
    assert "nvd 9.8  ·  redhat 5.3  ·  refused ghsa" in text


def test_the_findings_with_a_refused_source_come_before_the_agreeing_ones():
    text = rendered((
        finding(DJANGO, advisory_id="CVE-2", vectors={"a": TOTAL_LOSS}),
        finding(PYYAML, advisory_id="CVE-1", vectors={"a": TOTAL_LOSS, "b": TEMPORAL_VECTOR}),
    ))
    assert text.index("A SOURCE WAS REFUSED") < text.index("SOURCES AGREE")
