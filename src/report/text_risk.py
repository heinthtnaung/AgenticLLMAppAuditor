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

A vector a council settled goes on the line under its finding, on the CVSS scale
and saying the risk score does not use it: beside the range, never in it.
"""

from organisation.risk import FindingRisk
from report.council_beside import NOT_IN_THE_SCORE, CouncilFigure, council_figure, figure_label
from report.record import Report
from report.risk_order import bands_contested_first
from report.text_layout import INDENT, SOURCE_SEPARATOR, section
from scoring.risk_score import RiskScore

PROVISIONAL = "provisional"
WEIGHTING_LABEL = "weighted"
COLUMN_GAP = "  "


def risk_block(report: Report) -> str:
    """Score every finding this environment was asked about, the contested bands first."""
    if not report.risk:
        return ""
    weighed = bands_contested_first(report.risk.values())
    width = id_width(report)
    entries = [risk_entry(one, width, council_figure(report, one.advisory_id)) for one in weighed]
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


def risk_entry(weighed: FindingRisk, width: int, figure: CouncilFigure | None) -> str:
    """Give one finding's score or range, its bands, its flag, and any council figure beside it."""
    flag = f"{SOURCE_SEPARATOR}{PROVISIONAL}" if weighed.is_provisional else ""
    bands = " and ".join(weighed.bands)
    scored = f"{INDENT}{weighed.advisory_id.ljust(width)}{COLUMN_GAP}{spread(weighed):<28}{bands}"
    return f"{scored}{flag}{beside(figure, width)}"


def beside(figure: CouncilFigure | None, width: int) -> str:
    """Put a council's figure under the score it sits beside, saying the score does not use it."""
    if figure is None:
        return ""
    # On a line of its own, under the score column: on the same line it would
    # push the bands out of line with every other finding's, and read as a term.
    margin = " " * (len(INDENT) + width + len(COLUMN_GAP))
    return f"\n{margin}{figure_label(figure)}{SOURCE_SEPARATOR}{NOT_IN_THE_SCORE}"


def spread(weighed: FindingRisk) -> str:
    """Give the one score, or the range with the source at each end of it named."""
    # Named on a range and not on a single score: where the band moves, which
    # source sits at which end is the reader's immediate next question, and a
    # range with no attribution invites them to guess. On a single score there
    # is nothing to attribute between, so the name would only be noise.
    ends = sorted(weighed.scores, key=lambda one: one.score)
    if ends[0].score == ends[-1].score:
        return f"{ends[0].score:.1f}"
    return f"{labelled(ends[0])} to {labelled(ends[-1])}"


def labelled(scored: RiskScore) -> str:
    """Name one end of a range by the source that put it there."""
    named = getattr(scored.technical, "source", "")
    return f"{named} {scored.score:.1f}" if named else f"{scored.score:.1f}"


def id_width(report: Report) -> int:
    """Widen the id column to the longest advisory id scored, rather than guessing one."""
    return max(len(advisory_id) for advisory_id in report.risk)
