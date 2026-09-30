"""The Organisation Risk Score on the page: this system's own claim, kept apart.

**It never shares a badge or a chip with a published CVSS score.** They are two
different claims on two different scales about one finding, and
`docs/SCORING_MODEL.md` refuses to merge them: a CVE that is CVSS Critical and
organisation Low is the normal case, not an error to smooth over. So the scale
is written on every badge and the shape differs from a CVSS chip's.

A finding is scored **once per published source**, because choosing one source
would be the precedence the design leaves open. Every one of those scores is
shown with the source behind it, and the findings whose band depends on the
source come first: that is the question this tab can newly answer.

A severity floor that raised a band is named beside the score it raised. A vector
a council settled is shown under the scores on its own CVSS chip, saying the risk
score does not use it: beside the scores, never one of them.
"""

from organisation.risk import FindingRisk
from report.council_beside import COUNCIL_SOURCE, NOT_IN_THE_SCORE, CouncilFigure, council_figure
from report.html_answers import derivation
from report.html_layout import (
    empty_note, figure_chip, listing, number, panel_head, scored_chip, tag, text,
)
from report.html_vector import vector_markup
from report.record import Report
from report.risk_order import bands_contested_first

RISK_SCALE = "org"
NO_SOURCE = "no source scored this"
PROVISIONAL = "provisional"
BAND_MOVES = "the source changes the band"
FLOORED_BY = "floored by"
NO_RISK = "No finding was scored: this run recorded no organisation answers."

RISK_LEDE = (
    "0 to 100, computed by this system from the answers this organisation gave. It is not "
    "a CVSS score and does not compare with one. A finding is scored once per published "
    "source, because choosing one source would be the precedence the design leaves open."
)


def risk_panel(report: Report) -> str:
    """Give the Org risk tab: every finding this environment was asked about, contested first."""
    if not report.risk:
        return panel_head("Organisation risk", RISK_LEDE) + empty_note(NO_RISK)
    weighed = bands_contested_first(report.risk.values())
    head = panel_head(f"Organisation risk ({len(weighed)})", RISK_LEDE)
    entries = "".join(risk_entry(one, council_figure(report, one.advisory_id)) for one in weighed)
    return head + headline(report) + tag("div", entries, "cards")



def headline(report: Report) -> str:
    """Say how many findings the choice of source would change the response to."""
    contested = [one for one in report.risk.values() if one.band_depends_on_the_source]
    if not contested:
        return ""
    return tag("p", text(f"The source changes the band on {len(contested)}."), "note")


def risk_entry(weighed: FindingRisk, figure: CouncilFigure | None) -> str:
    """Give one finding's scores, one per source, the council's figure, and what is behind them."""
    named = tag("span", text(weighed.advisory_id), "adv") + flags(weighed)
    head = tag("header", tag("div", named, "title"), "card-head")
    body = head + risk_scores(weighed) + council_row(figure) + derivation(weighed)
    ident = text(weighed.advisory_id)
    return f'<article class="card risk-entry" id="risk-{ident}">{body}</article>'


def council_row(figure: CouncilFigure | None) -> str:
    """Show a council's settled vector on the CVSS scale, saying the risk score does not use it."""
    if figure is None:
        return ""
    said = (
        tag("span", text(COUNCIL_SOURCE), "source-name")
        + figure_chip(figure)
        + vector_markup(figure.vector)
        + tag("span", text(NOT_IN_THE_SCORE), "not-scored")
    )
    return listing([said], "sources")


def flags(weighed: FindingRisk) -> str:
    """Mark a finding the source moves a band on, and one an Unknown answer left provisional."""
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
        + floors_note(scored)
        + unknown_answers(scored)
    )


def floors_note(scored) -> str:
    """Name each floor that raised this score's band, from the band before to the band after."""
    if not scored.floors:
        return ""
    steps = [f"{one.rule_id}: {one.band_before} to {one.band_after}" for one in scored.floors]
    return tag("span", text(f"{FLOORED_BY} {', '.join(steps)}"), "floor-note")


def source_of(scored) -> str:
    """Name the source behind one score, or say plainly that nobody published one."""
    return getattr(scored.technical, "source", "") or NO_SOURCE


def unknown_answers(scored) -> str:
    """Name the questions answered Unknown, which is why a score reads provisional."""
    if not scored.unknown_questions:
        return ""
    named = ", ".join(scored.unknown_questions)
    return tag("span", text(f"unknown: {named}"), "refusal")
