"""Why a finding's published sources differ, as a model wrote it, in terms the report holds.

A projection of `council.explanation`, because `src/report/` does not import the
council. **The `why` is the model's own prose and nothing checked it**; the
quotation beside it is the one part held to the advisory, and only items whose
quotation was found there are kept. The record says so on every item rather
than leaving a reader to assume an explanation was verified. **What was not kept
is recorded too**, each with why, as the council records an unverified
quotation: it is how a finding nothing was kept for can be read afterwards.

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
class DroppedMetric:
    """An item the model offered and nothing kept: what it said, and why it was not kept.

    `reason` is one of `council.explanation`'s: not a disputed metric, empty why,
    unverified quotation, or repeat. `evidence_verified` is the quotation check's
    own answer, since a repeat can quote the advisory exactly.
    """

    metric: str
    why: str
    evidence: str
    evidence_verified: bool
    reason: str


@dataclass(frozen=True)
class SourcesExplained:
    """A model's account of why one finding's sources differ, kept item by item.

    `dropped_items` are the items not kept, each with its reason.
    """

    advisory_id: str
    model: str
    prompt_version: str
    items: tuple[ExplainedMetric, ...]
    dropped_items: tuple[DroppedMetric, ...] = ()

    @property
    def dropped(self) -> int:
        """Count the items not kept."""
        return len(self.dropped_items)

    def __post_init__(self) -> None:
        """Refuse an explanation with no item kept, which is not an explanation at all."""
        if not self.items:
            raise ValueError(f"{self.advisory_id} kept no item, so it was not explained")


@dataclass(frozen=True)
class SourcesNotExplained:
    """A finding with no explanation of its sources, why there is none, and what was not kept.

    `model` and `prompt_version` name the explainer and its prompt where a model
    was asked, as `SourcesExplained` does, and are both empty where none was: the
    sources agree, or there is no text to read.
    """

    advisory_id: str
    because: str
    dropped_items: tuple[DroppedMetric, ...] = ()
    model: str = ""
    prompt_version: str = ""

    @property
    def asked(self) -> bool:
        """Say whether a model was asked, and so whether the record names one."""
        return bool(self.model)

    def __post_init__(self) -> None:
        """Refuse an unexplained absence, or model output that does not name what produced it."""
        if not self.because:
            raise ValueError(f"{self.advisory_id} has no explanation and no reason why")
        if bool(self.model) != bool(self.prompt_version):
            raise ValueError(f"{self.advisory_id} names a model or a prompt version, not both")
        if self.dropped_items and not self.asked:
            raise ValueError(f"{self.advisory_id} holds dropped items and names no model")


ExplanationRecord = SourcesExplained | SourcesNotExplained
