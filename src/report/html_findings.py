"""How one finding goes on the page, in the four shapes a reader needs.

**Every source is a row of its own, and no source has a column.** On the
repository under test NVD published a vector for 4 findings of 18, so a table
headed `nvd` is empty on 14 rows and looks right until a real repository is on
screen. What is rendered is the list the finding carries, in name order, which
is not a ranking.

A contested finding gets its spread, the bands it crosses and the metrics its
sources read differently; an agreeing one gets the same rows without them; one
whose readable sources match beside a refused vector gets those rows in a group
of its own, because a vector nobody could read is not agreement; one nobody
scored says so rather than showing a zero. A refused vector is kept on
whichever card it belongs to, marked not scored.
"""

from cvss.score import severity_band
from report.disagreement import (
    agreement_unchecked,
    bands_crossed,
    most_contested_first,
    score_spread,
    sources_agree,
    sources_disagree,
)
from report.html_layout import listing, number, scored_chip, section, separated, tag, text
from report.record import Report

CVSS_SCALE = "cvss"
NOTHING_PUBLISHED = "No source published a readable v3 vector."

CONTESTED_LEDE = (
    "Read these first. Published CVSS base scores, 0.0 to 10.0, one row per source that "
    "published a vector, in source-name order, which is not a ranking. Ordered by whether "
    "the disagreement crosses a severity band, because that is what moves the response time."
)
REFUSED_LEDE = (
    "The vectors this calculator could read match metric for metric, and another source "
    "published one it refused. Whether that source agrees is not known, so these are not "
    "counted as agreeing."
)
AGREEING_LEDE = (
    "Every source was read, and the vectors match metric for metric. Each source is still "
    "shown on its own."
)
UNSCORED_LEDE = (
    "Nobody published a vector this calculator could read. That is not a score of 0.0: "
    "nobody scored it and somebody scoring it zero are different findings."
)


def contested_section(report: Report) -> str:
    """List the findings whose sources disagree, the ones worth reading first."""
    contested = [one for one in report.findings if sources_disagree(one)]
    if not contested:
        return ""
    cards = [contested_card(one) for one in most_contested_first(tuple(contested))]
    return section(f"Sources disagree ({len(contested)})", CONTESTED_LEDE, "".join(cards))


def unchecked_section(report: Report) -> str:
    """List the findings whose readable sources match beside a vector that was refused."""
    unchecked = [one for one in report.findings if agreement_unchecked(one)]
    if not unchecked:
        return ""
    cards = [finding_card(one, source_list(one)) for one in unchecked]
    return section(f"A source was refused ({len(unchecked)})", REFUSED_LEDE, "".join(cards))


def agreeing_section(report: Report) -> str:
    """List the findings whose sources were all read and say the same thing about every metric."""
    agreed = [one for one in report.findings if sources_agree(one)]
    if not agreed:
        return ""
    cards = [finding_card(one, source_list(one)) for one in agreed]
    return section(f"Sources agree ({len(agreed)})", AGREEING_LEDE, "".join(cards))


def unscored_section(report: Report) -> str:
    """List the findings nobody published a readable vector for, which is not a zero."""
    unscored = [one for one in report.findings if not one.is_scored]
    if not unscored:
        return ""
    return section(
        f"Not scored ({len(unscored)})", UNSCORED_LEDE, "".join(map(unscored_card, unscored))
    )


def finding_card(finding, body: str) -> str:
    """Put one finding on a card: what it is, then what its group shows about it."""
    return tag("article", finding_name(finding) + body + unreadable_list(finding), "finding")


def contested_card(finding) -> str:
    """Give one contested finding: how far apart its sources are, then every one of them."""
    return finding_card(finding, spread_line(finding) + source_list(finding))


def unscored_card(finding) -> str:
    """Give one unscored finding, saying whether anything was published at all."""
    if finding.unreadable:
        return finding_card(finding, "")
    return finding_card(finding, tag("p", text(NOTHING_PUBLISHED), "spread"))


def finding_name(finding) -> str:
    """Name the advisory and the installed component it was raised against."""
    named = tag("span", text(finding.advisory.advisory_id), "advisory")
    component = f"{finding.component.name} {finding.component.version}"
    return tag("h3", named + tag("span", text(component), "component"), "finding-name")


def spread_line(finding) -> str:
    """Say how far apart the sources are, which bands that crosses, and what they read apart."""
    bands = " and ".join(bands_crossed(finding))
    metrics = ", ".join(finding.disputed_metrics())
    said = [f"{number(score_spread(finding))} apart", bands, f"differ on {metrics}"]
    return tag("p", separated([text(one) for one in said]), "spread")


def source_list(finding) -> str:
    """Put every source's own score side by side, in name order, which is not a ranking."""
    return listing([source_row(one) for one in finding.scores], "sources")


def source_row(score) -> str:
    """Give one source: its name, the score its vector comes to, and the vector itself."""
    return (
        tag("span", text(score.source), "source-name")
        + scored_chip(CVSS_SCALE, number(score.base_score), severity_band(score.base_score), "cvss")
        + tag("code", text(score.vector), "vector")
    )


def unreadable_list(finding) -> str:
    """Name every source this calculator refused, kept as not scored and never as 0.0."""
    if not finding.unreadable:
        return ""
    return listing([unreadable_row(one) for one in finding.unreadable], "sources")


def unreadable_row(source) -> str:
    """Give one refused source: what it published, and why the calculator would not read it."""
    return (
        tag("span", text(source.source), "source-name")
        + tag("span", "not scored", "not-scored")
        + tag("code", text(source.vector), "vector")
        + tag("span", text(source.refusal), "refusal")
    )
