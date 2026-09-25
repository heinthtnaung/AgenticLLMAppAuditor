"""A vector a council settled, shown beside the Organisation Risk Score and never in it.

**The score is weighed from the published sources alone.** On the 18 vulnscout
advisories the council's settled values agreed with the reference on AV 0 times
in 11, PR 0 in 9, UI 0 in 13 and S 1 in 13
(`measurements/council_eval_runs/pilot-vulnscout/README.md`), so its vector is
put beside the published range for a reader to weigh, and the score does not read it.

**The figure is the vector's own CVSS base score, never an organisation score.**
Weighing the council's vector through the engine, even only to show the result,
would put a second 0-100 number beside the real one -- the substitution refused,
arriving as a display.

The wording lives here so the three renderings cannot say it three ways.
"""

from dataclasses import dataclass

from cvss.score import base_score
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


def council_figure(report: Report, advisory_id: str) -> CouncilFigure | None:
    """Give the vector a council settled for one finding, or None where it settled none."""
    settled = report.council.get(advisory_id)
    if not isinstance(settled, CouncilAssessment):
        return None
    return CouncilFigure(settled.vector, base_score(parse(settled.vector)))


def figure_label(figure: CouncilFigure) -> str:
    """Name the council's figure and its scale, so it reads as nobody's organisation score."""
    return f"{COUNCIL_SOURCE} {CVSS_SCALE_NAME} {figure.base_score:.1f}"
