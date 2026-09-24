"""The organisation's own score on the page, led by the question it can newly answer.

A finding is scored once per source, so most carry a range rather than a number.
The reader's new question is **whether which source you believe changes the
band** -- because the answer is sometimes yes and sometimes no, and neither is
visible from the published scores. Those findings come first.

A provisional score is marked on its own line rather than footnoted. An
`Unknown` answer produces a number that is calculated and flagged, never a
silent `No`, and a flag a reader can miss is the same as no flag.

The weighting that combined the categories heads the block, because it is the
one term of the arithmetic a reader would otherwise have to fetch from
`docs/SCORING_MODEL.md`. It comes off the record, never off the engine.
"""

from organisation.risk import FindingRisk
from report.record import Report
from report.risk_order import bands_contested_first
from report.text_layout import INDENT, SOURCE_SEPARATOR, section

PROVISIONAL = "provisional"
WEIGHTING_LABEL = "weighted"


def risk_block(report: Report) -> str:
    """Score every finding this environment was asked about, the contested bands first."""
    if not report.risk:
        return ""
    weighed = bands_contested_first(report.risk.values())
    entries = [risk_entry(one, id_width(report)) for one in weighed]
    titled = f"ORGANISATION RISK ({len(weighed)}){headline(report)}"
    return section(titled, [weighting(weighed[0]), *entries])


def weighting(weighed: FindingRisk) -> str:
    """Give the weighting that combined the categories, so the total re-derives on the page."""
    # Off the first score: the weighting is the same on every one of them, and
    # the same for every finding, so it is said once at the top of the block.
    named = ", ".join(f"{one.category} {one.weight:g}" for one in weighed.scores[0].weights)
    return f"{INDENT}{WEIGHTING_LABEL} {named}"


def headline(report: Report) -> str:
    """Say how many findings the choice of source would change the response to."""
    contested = [one for one in report.risk.values() if one.band_depends_on_the_source]
    if not contested:
        return ""
    return f"{SOURCE_SEPARATOR}the source changes the band on {len(contested)}"


def risk_entry(weighed, width: int) -> str:
    """Give one finding's score or range, its bands, and whether it is settled."""
    flag = f"{SOURCE_SEPARATOR}{PROVISIONAL}" if weighed.is_provisional else ""
    bands = " and ".join(weighed.bands)
    return f"{INDENT}{weighed.advisory_id.ljust(width)}  {spread(weighed):<28}{bands}{flag}"


def spread(weighed) -> str:
    """Give the one score, or the range with the source at each end of it named."""
    # Named on a range and not on a single score: where the band moves, which
    # source sits at which end is the reader's immediate next question, and a
    # range with no attribution invites them to guess. On a single score there
    # is nothing to attribute between, so the name would only be noise.
    ends = sorted(weighed.scores, key=lambda one: one.score)
    if ends[0].score == ends[-1].score:
        return f"{ends[0].score:.1f}"
    return f"{labelled(ends[0])} to {labelled(ends[-1])}"


def labelled(scored) -> str:
    """Name one end of a range by the source that put it there."""
    named = getattr(scored.technical, "source", "")
    return f"{named} {scored.score:.1f}" if named else f"{scored.score:.1f}"


def id_width(report: Report) -> int:
    """Widen the id column to the longest advisory id scored, rather than guessing one."""
    return max(len(advisory_id) for advisory_id in report.risk)
