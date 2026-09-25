"""The Organisation Risk Score on the page: this system's own claim, kept apart.

**It never shares a badge or a chip with a published CVSS score.** They are two
different claims on two different scales about one finding, and
`docs/SCORING_MODEL.md` refuses to merge them: a CVE that is CVSS Critical and
organisation Low is the normal case, not an error to smooth over. So the scale
is written on every badge and the shape differs from a CVSS chip's.

A finding is scored **once per published source**, because choosing one source
would be the precedence the design leaves open. Every one of those scores is
shown with the source behind it rather than collapsed into a range, so the
reader's next question -- which source sits at which end -- is already answered.

The findings whose band depends on the source come first: that is the question
this section can newly answer, and it has both answers.

A vector a council settled is shown under the scores on its own CVSS chip,
saying the risk score does not use it: beside the scores, never one of them.
"""

from organisation.risk import FindingRisk
from report.council_beside import COUNCIL_SOURCE, NOT_IN_THE_SCORE, CouncilFigure, council_figure
from report.html_answers import derivation
from report.html_layout import figure_chip, listing, number, scored_chip, section, tag, text
from report.record import Report
from report.risk_order import bands_contested_first

RISK_SCALE = "org"
PROVISIONAL = "provisional"
BAND_MOVES = "the source changes the band"

RISK_LEDE = (
    "0 to 100, computed by this system from the answers this organisation gave. It is not "
    "a CVSS score and does not compare with one. A finding is scored once per published "
    "source, because choosing one source would be the precedence the design leaves open."
)


def risk_section(report: Report) -> str:
    """Score every finding this environment was asked about, the contested bands first."""
    if not report.risk:
        return ""
    weighed = bands_contested_first(report.risk.values())
    entries = "".join(risk_entry(one, council_figure(report, one.advisory_id)) for one in weighed)
    return section(f"Organisation risk ({len(weighed)})", RISK_LEDE, headline(report) + entries)


def headline(report: Report) -> str:
    """Say how many findings the choice of source would change the response to."""
    contested = [one for one in report.risk.values() if one.band_depends_on_the_source]
    if not contested:
        return ""
    return tag("p", text(f"The source changes the band on {len(contested)}."), "note")


def risk_entry(weighed: FindingRisk, figure: CouncilFigure | None) -> str:
    """Give one finding's scores, one per source, the council's figure, and what is behind them."""
    named = tag("span", text(weighed.advisory_id), "advisory") + flags(weighed)
    scores = risk_scores(weighed) + council_row(figure)
    body = tag("h3", named, "finding-name") + scores + derivation(weighed)
    return tag("article", body, "risk-entry")


def council_row(figure: CouncilFigure | None) -> str:
    """Show a council's settled vector on the CVSS scale, saying the risk score does not use it."""
    if figure is None:
        return ""
    said = (
        tag("span", text(COUNCIL_SOURCE), "source-name")
        + figure_chip(figure)
        + tag("code", text(figure.vector), "vector")
        + tag("span", text(NOT_IN_THE_SCORE), "not-scored")
    )
    return listing([said], "sources")


def flags(weighed: FindingRisk) -> str:
    """Mark a finding the source moves a band on, and one an Unknown answer left provisional."""
    # A flag a reader can miss is the same as no flag, so both sit on the heading
    # rather than in a footnote.
    marked = []
    if weighed.band_depends_on_the_source:
        marked.append(BAND_MOVES)
    if weighed.is_provisional:
        marked.append(PROVISIONAL)
    return "".join(tag("span", text(one), "flag") for one in marked)


def risk_scores(weighed: FindingRisk) -> str:
    """Show every organisation score this finding carries, each named by its source."""
    return listing([risk_row(one) for one in weighed.scores], "risk-scores")


def risk_row(scored) -> str:
    """Give one organisation score and the source whose technical severity produced it."""
    return (
        tag("span", text(source_of(scored)), "source-name")
        + scored_chip(RISK_SCALE, number(scored.score), scored.band, "risk")
        + unknown_answers(scored)
    )


def source_of(scored) -> str:
    """Name the source behind one score, or say plainly that nobody published one."""
    # Absent on an unknown technical severity, which is a finding nobody scored
    # rather than one scored zero, so the row says which it is.
    return getattr(scored.technical, "source", "") or "no source scored this"


def unknown_answers(scored) -> str:
    """Name the questions answered Unknown, which is why a score reads provisional."""
    if not scored.unknown_questions:
        return ""
    named = ", ".join(scored.unknown_questions)
    return tag("span", text(f"unknown: {named}"), "refusal")
