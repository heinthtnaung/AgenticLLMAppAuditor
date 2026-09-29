"""The Council column of the overview table: the settled vector, or the metrics left open.

Its own file so `report.html_overview` stays under the size limit and about the
table as a whole. The band and the open metrics are read off the record's council
outcome, never worked out here.
"""

from report.council_beside import council_figure
from report.council_record import CouncilNotAsked, council_left_open
from report.html_layout import CVSS_SCALE, badge, cell, jump, mini_chip, number, tag, text
from report.record import Report

DASH = "—"


def council_cell(report: Report, advisory_id: str) -> str:
    """Give the Council cell: the settled vector and its band, or the metrics it left open."""
    figure = council_figure(report, advisory_id)
    if figure is not None:
        chip = mini_chip("council", number(figure.base_score), figure.band, CVSS_SCALE)
        return council_link(advisory_id, badge("Settled", "ok") + chip)
    outcome = report.council.get(advisory_id)
    if outcome is None:
        return cell("Council", DASH)
    if isinstance(outcome, CouncilNotAsked):
        return council_link(advisory_id, badge("not asked", "muted"))
    return council_link(advisory_id, badge("No vector", "muted") + open_metrics_line(outcome))


def council_link(advisory_id: str, inner: str) -> str:
    """Wrap the council cell's stacked badge and chip in a link to the ruling."""
    linked = jump(f"council/{advisory_id}", tag("div", inner, "stack"), "goto cell-link")
    return cell("Council", linked)


def open_metrics_line(outcome) -> str:
    """Name the metrics the council left open, read off the record, never worked out here."""
    opened = [ruling.metric for ruling in outcome.rulings if council_left_open(ruling)]
    return tag("span", text(f"open: {', '.join(opened)}"), "sub") if opened else ""
