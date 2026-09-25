"""A vector a council settled, shown beside the Organisation Risk Score and never in it.

**The score is weighed from the published sources alone.** On the 18 vulnscout
advisories the council's settled values agreed with the reference on AV 0 times
in 11, PR 0 in 9, UI 0 in 13 and S 1 in 13
(`measurements/council_eval_runs/pilot-vulnscout/README.md`), so its vector is
put beside the published range for a reader to weigh, and the score does not read it.

**The figure is the vector's own CVSS base score, never an organisation score.**
Weighing the council's vector through the engine, even only to show the result,
would put a second 0-100 number beside the real one -- the substitution refused,
arriving as a display. The same figure heads the council's own entry, so a run
with no answers, and so no risk score, still shows what a settled vector scores.

The figure and its wording live here so no rendering works either out again.
"""

from dataclasses import dataclass

from cvss.score import base_score, severity_band
from cvss.vector import parse
from report.council_record import CouncilAssessment
from report.record import Report

COUNCIL_SOURCE = "the assessor council"
NOT_IN_THE_SCORE = "the risk score does not use it"
CVSS_SCALE_NAME = "CVSS"


@dataclass(frozen=True)
class CouncilFigure:
    """The vector a council settled for one finding, and the CVSS base score it computes to."""

    vector: str
    base_score: float

    @property
    def band(self) -> str:
        """Name the CVSS severity band the base score lands in."""
        return severity_band(self.base_score)


def figure_of(settled: CouncilAssessment) -> CouncilFigure:
    """Give the vector one council settled, and the CVSS base score it computes to."""
    return CouncilFigure(settled.vector, base_score(parse(settled.vector)))


def council_figure(report: Report, advisory_id: str) -> CouncilFigure | None:
    """Give the vector a council settled for one finding, or None where it settled none."""
    settled = report.council.get(advisory_id)
    if not isinstance(settled, CouncilAssessment):
        return None
    return figure_of(settled)


def on_its_scale(figure: CouncilFigure) -> str:
    """Give the figure with the scale it is on, which a bare 9.8 beside a 0-100 score lacks."""
    return f"{CVSS_SCALE_NAME} {figure.base_score:.1f}"


def figure_label(figure: CouncilFigure) -> str:
    """Name the council's figure and its scale, so it reads as nobody's organisation score."""
    return f"{COUNCIL_SOURCE} {on_its_scale(figure)}"


def banded(figure: CouncilFigure) -> str:
    """Give the figure on its scale with its CVSS band, as the council's own entry shows it."""
    return f"{on_its_scale(figure)} {figure.band}"
