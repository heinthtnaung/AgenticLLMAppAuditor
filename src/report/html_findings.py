"""The findings on the page: the contested ones on their own tab, the rest on another.

The Disagreements tab leads with the findings whose sources read a metric
differently, most consequential first, each card carrying why the sources differ
where a model explained it. The Agreements tab holds the rest in three groups a
reader must tell apart: sources that were all read and match, a match beside a
vector this calculator refused (agreement nobody could check), and findings
nobody published a readable vector for (which is not a score of 0.0).

What a card is built from is `report.html_finding_card`; this file decides which
cards a reader sees and in what order, so the two change for different reasons.
"""

from report.disagreement import (
    agreement_unchecked,
    bands_crossed,
    most_contested_first,
    score_spread,
    sources_agree,
    sources_disagree,
)
from report.explanation_words import LEDE as EXPLANATION_LEDE
from report.html_explanation import why_block
from report.html_finding_card import (
    article,
    card_head,
    card_links,
    council_flag,
    nothing_published,
    source_table,
    unreadable_table,
)
from report.html_layout import empty_note, group, number, panel_head, tag, text
from report.record import Report

NO_DISAGREEMENT = "No finding here has sources that read a metric differently."
NO_AGREEMENT = "No agreeing, refused, or unscored finding here."

CONTESTED_LEDE = (
    "Read these first. Ordered by whether the disagreement crosses a severity band, because "
    "that is what moves the response time. Each source is a row, in name order, not a ranking."
)
AGREEING_LEDE = "Every source was read, and the vectors match metric for metric."
REFUSED_LEDE = (
    "The vectors this calculator could read match, and another source published one it "
    "refused. Whether that source agrees is not known, so these are not counted as agreeing."
)
UNSCORED_LEDE = (
    "Nobody published a vector this calculator could read. That is not a score of 0.0: "
    "nobody scored it and somebody scoring it zero are different findings."
)


def disagreements_panel(report: Report) -> str:
    """Give the Disagreements tab: the contested findings, most consequential first."""
    contested = [one for one in report.findings if sources_disagree(one)]
    head = panel_head(f"Sources disagree ({len(contested)})", CONTESTED_LEDE)
    if not contested:
        return head + empty_note(NO_DISAGREEMENT)
    cards = "".join(contested_card(report, one) for one in most_contested_first(tuple(contested)))
    return head + explanation_disclosure(report, contested) + cards_wrap(cards)


def explanation_disclosure(report: Report, contested: list) -> str:
    """State once, above the cards, what a model's explanation is and is not, where one exists."""
    if not any(one.advisory.advisory_id in report.explanations for one in contested):
        return ""
    return tag("p", text(EXPLANATION_LEDE), "note")


def agreements_panel(report: Report) -> str:
    """Give the Agreements tab: the sources that agree, then the refused, then the unscored."""
    agreed = [one for one in report.findings if sources_agree(one)]
    refused = [one for one in report.findings if agreement_unchecked(one)]
    unscored = [one for one in report.findings if not one.is_scored]
    body = (
        group(f"Sources agree ({len(agreed)})", AGREEING_LEDE, cards_of(report, agreed, plain_card))
        + group(f"A source was refused ({len(refused)})", REFUSED_LEDE,
                cards_of(report, refused, plain_card))
        + group(f"Not scored ({len(unscored)})", UNSCORED_LEDE,
                cards_of(report, unscored, unscored_card))
    )
    return panel_head("Agreements and the rest") + (body or empty_note(NO_AGREEMENT))


def cards_wrap(cards: str) -> str:
    """Wrap already-rendered cards in the column the stylesheet lays them out in."""
    return tag("div", cards, "cards")


def cards_of(report: Report, findings: list, build) -> str:
    """Give a column of cards built by `build`, or nothing where there are no findings."""
    return cards_wrap("".join(build(report, one) for one in findings)) if findings else ""


def contested_card(report: Report, finding) -> str:
    """Give one contested finding: spread, sources, any refused one, and why they differ."""
    body = card_head(report, finding) + council_flag(report, finding) + facts(finding)
    body += source_table(finding) + refused_note(finding) + why_block(report, finding)
    return article(finding, "disagree", body + card_links(report, finding))


def plain_card(report: Report, finding) -> str:
    """Give one agreeing or refused finding: its sources, any refused one, and its other views."""
    body = card_head(report, finding) + source_table(finding) + refused_note(finding)
    return article(finding, "agree", body + card_links(report, finding))


def refused_note(finding) -> str:
    """Keep any refused source on the card, marked not scored, whichever group the card is in."""
    return unreadable_table(finding) if finding.unreadable else ""


def unscored_card(report: Report, finding) -> str:
    """Give one unscored finding, its refused vectors where it has them, else that none was read."""
    inner = unreadable_table(finding) if finding.unreadable else nothing_published()
    body = card_head(report, finding) + inner + card_links(report, finding)
    return article(finding, "agree", body)


def facts(finding) -> str:
    """Give the spread, the bands it crosses, and which metrics its sources read apart."""
    pairs = [
        ("Spread", f"{number(score_spread(finding))} apart"),
        ("Bands", " and ".join(bands_crossed(finding))),
        ("Differ on", ", ".join(finding.disputed_metrics())),
    ]
    return tag("dl", "".join(fact(name, value) for name, value in pairs), "facts")


def fact(name: str, value: str) -> str:
    """Give one term/value pair of a card's facts."""
    return tag("div", tag("dt", text(name)) + tag("dd", text(value)))
