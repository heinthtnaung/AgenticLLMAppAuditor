"""The measures as text: every rate beside its sample, its interval, and the baseline it must beat.

Nothing is computed here but formatting. A rate is never printed without the
count it came from, and a rate over nothing is printed as `NO_RATE`, not as 0.
"""

from itertools import chain
from typing import Any, Iterable, Mapping, Sequence

from report.council_record import CouncilAssessment, CouncilOutcome

from council_eval.contests import ContestMeasure
from council_eval.measures import (
    NOT_IN_ADVISORY,
    VERIFIED,
    MemberMeasure,
    MetricMeasure,
    outcome_totals,
    wilson,
)
from council_eval.vectors import VectorMeasure, reference_band

NO_RATE = "-"
GAP = "  "
REPLY_KINDS = (VERIFIED, NOT_IN_ADVISORY, "guessed", "declined", "failed")
HEADER_FIELDS = (
    "model", "digest", "ollama", "prompt_version", "temperature", "seed", "num_ctx",
    "think", "turn_start", "dataset_sha256", "commit", "started",
)
METRIC_COLUMNS = (
    "metric", "settled", "contested", "unresolved", "R1 items", "scored", "agreed",
    "rate [95% CI]", "commonest", "its rate", "lift", "settled, no R1", "values settled",
)
MEMBER_COLUMNS = ("member", "metric", *REPLY_KINDS, "values named")
CONTEST_COLUMNS = (
    "metric", "settled", "settled by one quotation alone", "contested", "contested, R1 judges",
    "R1 among the verified",
)
VECTOR_COLUMNS = (
    "finding", "council vector", "score", "band", "R1 band", "R1 metrics", "departs on",
    "published", "inside range",
)


def table(columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> list[str]:
    """Lay rows out under their column names, each column as wide as its widest cell."""
    cells = [list(columns), *[as_text(row) for row in rows]]
    widths = [column_width(cells, index) for index in range(len(columns))]
    return [laid_out(row, widths) for row in cells]


def as_text(row: Sequence[Any]) -> list[str]:
    """Give every cell of a row as text."""
    return [str(cell) for cell in row]


def column_width(cells: list[list[str]], index: int) -> int:
    """Give the width of a column's widest cell."""
    return max(len(row[index]) for row in cells)


def laid_out(row: list[str], widths: list[int]) -> str:
    """Pad each cell of a row to its column's width."""
    return GAP.join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()


def header_lines(headers: Iterable[Mapping[str, Any]]) -> list[str]:
    """Say what produced each pass, field by field, and what it left uncommitted."""
    return list(chain.from_iterable(pass_lines(header) for header in headers))


def pass_lines(header: Mapping[str, Any]) -> list[str]:
    """Say what produced one pass."""
    changes = header.get("changes", [])
    said = [f"  {name}: {header.get(name)}" for name in HEADER_FIELDS]
    return [f"pass {header['model']}", *said, f"  uncommitted at launch: {len(changes)} paths"]


def rate(hits: int, sample: int) -> str:
    """Give a rate with its 95% interval, or `NO_RATE` over an empty sample."""
    if sample == 0:
        return NO_RATE
    low, high = wilson(hits, sample)
    return f"{hits / sample:.2f} [{low:.2f}, {high:.2f}]"


def plain_rate(hits: int, sample: int) -> str:
    """Give a rate alone, or `NO_RATE` over an empty sample."""
    return f"{hits / sample:.2f}" if sample else NO_RATE


def lift(measure: MetricMeasure) -> str:
    """Give the rate minus the commonest-value baseline on the same items."""
    if measure.scored == 0:
        return NO_RATE
    return f"{(measure.agreed - measure.majority_hits) / measure.scored:+.2f}"


def metric_row(measure: MetricMeasure) -> list[Any]:
    """Give one metric's row: outcomes, agreement with R1, the baseline, and what was settled."""
    baseline = plain_rate(measure.majority_hits, measure.scored)
    return [
        measure.metric, measure.settled, measure.contested, measure.unresolved,
        measure.reference_items, measure.scored, measure.agreed,
        rate(measure.agreed, measure.scored), measure.majority_value or NO_RATE, baseline,
        lift(measure), measure.unreferenced, ",".join(measure.values_used) or NO_RATE,
    ]


def metric_table(measures: Iterable[MetricMeasure]) -> list[str]:
    """Lay out one roster's metrics, one row each."""
    return table(METRIC_COLUMNS, [metric_row(one) for one in measures])


def member_table(measures: Iterable[MemberMeasure]) -> list[str]:
    """Lay out what each member did on each metric, and every value it named."""
    return table(MEMBER_COLUMNS, [member_row(one) for one in measures])


def member_row(measure: MemberMeasure) -> list[Any]:
    """Give one member's row on one metric: how often it did each thing, and what it named."""
    counts = [measure.kinds.get(kind, 0) for kind in REPLY_KINDS]
    return [measure.member, measure.metric, *counts, ",".join(measure.values_used) or NO_RATE]


def contest_table(measures: Iterable[ContestMeasure]) -> list[str]:
    """Lay out each metric's cross-check: lone settlements, and the contests R1 can judge."""
    rows = [
        [one.metric, one.settled, one.sole, one.contested, one.contested_referenced, one.caught]
        for one in measures
    ]
    return table(CONTEST_COLUMNS, rows)


def vector_row(measure: VectorMeasure) -> list[Any]:
    """Give one reached vector's row."""
    published = " ".join(f"{source} {score}" for source, score in measure.published.items())
    return [
        measure.key, measure.vector, measure.score, measure.band,
        reference_band(measure) or NO_RATE, measure.referenced,
        ",".join(measure.departs_on) or NO_RATE, published or NO_RATE,
        "yes" if measure.inside_published_range else "no",
    ]


def vector_table(measures: Iterable[VectorMeasure]) -> list[str]:
    """Lay out every vector a roster reached."""
    return table(VECTOR_COLUMNS, [vector_row(one) for one in measures])


def totals_lines(outcomes: tuple[CouncilOutcome, ...]) -> list[str]:
    """Count every metric by outcome, and name every vector reached."""
    totals = outcome_totals(outcomes)
    reached = [one for one in outcomes if isinstance(one, CouncilAssessment)]
    vectors = [f"  {one.advisory_id}  {one.vector}" for one in reached]
    counted = ", ".join(f"{totals[kind]} {kind}" for kind in ("settled", "contested", "unresolved"))
    return [f"{sum(totals.values())} metrics: {counted}; {len(vectors)} vectors", *vectors]
