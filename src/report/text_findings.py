"""How one finding is written on the page, in the four shapes a reader needs.

A contested finding gets three lines -- what it is, how far apart the sources
are and which metrics they read differently, then every source side by side. An
agreeing one gets a line, because there is nothing to compare. One whose readable
sources match beside a vector that was refused gets that line and the refused
source's name, in a group of its own: a vector nobody could read is not
agreement. One nobody scored gets its own group rather than a zero.

**No winner is printed anywhere.** The sources are listed in name order, which
is not a ranking, and the spread is stated without a verdict on which end of it
is right.
"""

from report.disagreement import (
    agreement_unchecked,
    bands_crossed,
    most_contested_first,
    score_spread,
    sources_agree,
    sources_disagree,
)
from report.record import Report
from report.text_layout import INDENT, SOURCE_SEPARATOR, id_width, identified, named, section

def contested_block(report: Report) -> str:
    """List the findings whose sources disagree, the ones worth reading first."""
    contested = [one for one in report.findings if sources_disagree(one)]
    if not contested:
        return ""
    ordered = most_contested_first(tuple(contested))
    entries = [contested_entry(one, id_width(ordered)) for one in ordered]
    return section(f"SOURCES DISAGREE ({len(contested)})", entries)


def contested_entry(finding, width: int) -> str:
    """Give one contested finding: what it is, how far apart, and every source."""
    spread = score_spread(finding)
    bands = " and ".join(bands_crossed(finding))
    metrics = ", ".join(finding.disputed_metrics())
    return "\n".join([
        f"{INDENT}{identified(finding, width)}  {named(finding)}",
        f"{INDENT}{INDENT}{spread:.1f} apart{SOURCE_SEPARATOR}{bands}"
        f"{SOURCE_SEPARATOR}differ on {metrics}",
        f"{INDENT}{INDENT}{sources_line(finding)}",
    ])


def unchecked_block(report: Report) -> str:
    """List the findings whose readable sources match beside a vector that was refused."""
    unchecked = [one for one in report.findings if agreement_unchecked(one)]
    if not unchecked:
        return ""
    width = id_width(tuple(unchecked))
    entries = [
        f"{matching_entry(one, width)} read{SOURCE_SEPARATOR}refused {refused(one)}"
        for one in unchecked
    ]
    return section(f"A SOURCE WAS REFUSED ({len(unchecked)})", entries)


def agreeing_block(report: Report) -> str:
    """List the findings whose sources say the same thing, one line each."""
    agreed = [one for one in report.findings if sources_agree(one)]
    if not agreed:
        return ""
    entries = [matching_entry(one, id_width(tuple(agreed))) for one in agreed]
    return section(f"SOURCES AGREE ({len(agreed)})", entries)


def matching_entry(finding, width: int) -> str:
    """Give a finding whose readable sources match on a line: score, band, and how many."""
    score = finding.scores[0].base_score
    count = len(finding.scores)
    return (
        f"{INDENT}{identified(finding, width)}  {named(finding)}"
        f"{score:>5.1f}  {bands_crossed(finding)[0]:<10}"
        f"{count} source{'' if count == 1 else 's'}"
    )


def unscored_block(report: Report) -> str:
    """List the findings nobody published a readable vector for, which is not a zero."""
    unscored = [one for one in report.findings if not one.is_scored]
    if not unscored:
        return ""
    width = id_width(tuple(unscored))
    entries = [
        f"{INDENT}{identified(one, width)}  {named(one)}{unscored_reason(one)}"
        for one in unscored
    ]
    return section(f"NOT SCORED ({len(unscored)})", entries)


def unscored_reason(finding) -> str:
    """Say why a finding has no score: nothing published, or nothing readable."""
    if not finding.unreadable:
        return "no source published a v3 vector"
    return f"no readable vector; refused {refused(finding)}"


def refused(finding) -> str:
    """Name every source whose vector the calculator would not read."""
    return ", ".join(source.source for source in finding.unreadable)


def sources_line(finding) -> str:
    """Put every source's score side by side, in name order, which is not a ranking."""
    return SOURCE_SEPARATOR.join(
        f"{score.source} {score.base_score:.1f}" for score in finding.scores
    )
