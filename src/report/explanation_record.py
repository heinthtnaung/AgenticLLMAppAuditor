"""Why a finding's published sources differ, as a model wrote it, in terms the report holds.

A projection of `council.explanation`, because `src/report/` does not import the
council. **The `why` is the model's own prose and nothing checked it**; the
quotation beside it is the one part held to the advisory, and only items whose
quotation was found there are kept. The record says so on every item rather
than leaving a reader to assume an explanation was verified.

**Nothing reads this back.** No score, band or council vector is computed from
it: the Organisation Risk Score and the council's rulings are fixed before it is
asked for (`cli.explanation_run`).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExplainedMetric:
    """One disputed metric the model spoke to: its prose, and the quotation in the advisory."""

    metric: str
    why: str
    evidence: str
    evidence_verified: bool


@dataclass(frozen=True)
class SourcesExplained:
    """A model's account of why one finding's sources differ, kept item by item.

    `dropped` counts the items not kept: a quotation not in the advisory, an item
    about a metric the sources agree on, or a second one on a metric.
    """

    advisory_id: str
    model: str
    prompt_version: str
    items: tuple[ExplainedMetric, ...]
    dropped: int

    def __post_init__(self) -> None:
        """Refuse an explanation with no item kept, which is not an explanation at all."""
        if not self.items:
            raise ValueError(f"{self.advisory_id} kept no item, so it was not explained")


@dataclass(frozen=True)
class SourcesNotExplained:
    """A finding with no explanation of its sources, and why there is none."""

    advisory_id: str
    because: str

    def __post_init__(self) -> None:
        """Refuse an unexplained absence, which reads on a report as an oversight."""
        if not self.because:
            raise ValueError(f"{self.advisory_id} has no explanation and no reason why")


ExplanationRecord = SourcesExplained | SourcesNotExplained
