"""What the chairman decided about one metric, and what it decided it from.

Three outcomes, three types, because they are not three shapes of one thing. A
settled metric has a value the evidence supports; a contested one has no value
yet and is the escalation policy's problem; an unresolved one has no member
evidence at all and falls back to a published vector. One record with the value
left out would let a reader take a contested metric for a settled one, and the
whole point of the council is that a reader can tell.
"""

from dataclasses import dataclass
from enum import Enum

from cvss.metrics import METRIC_ORDER, refuse_illegal_pair
from council.answer import Confidence, MemberAnswer


class Basis(Enum):
    """What settled a metric: one quotation alone, several without a dissent, or the verified one.

    All three range over the members that **offered a quotation**, whether or
    not it turned out to be in the advisory. A member that quoted nothing -- one
    that declined, one that guessed, one whose call failed -- took no part in the
    disagreement and cannot create one, so a dissenting guess does not make the
    basis EVIDENCE. Nor does it make it AGREED: beside one quotation and nothing
    else, the basis is SOLE, because agreement needs a second member to agree.
    These strings go into a record a human reads, so they name the set rather
    than leaving "answered" to be worked out.
    """

    SOLE = "one member offered a quotation, and no other member offered one"
    AGREED = "every member that offered a quotation supported this value"
    EVIDENCE = "members offering quotations disagreed, and the verified one settled it"


@dataclass(frozen=True)
class PublishedFallback:
    """A metric value taken from a published vector because no member's quotation verified."""

    value: str
    source: str

    def __post_init__(self) -> None:
        """Refuse a fallback that does not say which published source it came from."""
        if not self.source:
            raise ValueError("A fallback must name the published source it was taken from")
        if not self.value:
            raise ValueError(f"The fallback from {self.source!r} carries no value")


@dataclass(frozen=True)
class NoFallbackPublished:
    """No member's quotation verified and no published vector offers a value either."""

    reason: str

    def __post_init__(self) -> None:
        """Refuse an unexplained absence, which reads on a report as an oversight."""
        if not self.reason:
            raise ValueError("An absent fallback must say why nothing was published")


Fallback = PublishedFallback | NoFallbackPublished


@dataclass(frozen=True)
class SettledMetric:
    """A metric the evidence settled, with the verified answers it rests on.

    `supporting` holds the answers whose quotation was found in the advisory, not
    every answer that happened to name this value: an unverified one supports
    nothing here, the same way it counts for nothing anywhere else.
    """

    metric: str
    value: str
    confidence: Confidence
    basis: Basis
    supporting: tuple[MemberAnswer, ...]

    def __post_init__(self) -> None:
        """Refuse a ruling that rests on nothing, or on a value the metric forbids."""
        refuse_illegal_pair(self.metric, self.value)
        if not self.supporting:
            raise ValueError(f"{self.metric} cannot be settled by no answer at all")
        dissenting = sorted({answer.value for answer in self.supporting} - {self.value})
        if dissenting:
            raise ValueError(
                f"{self.metric} was settled on {self.value} by answers supporting "
                f"{', '.join(dissenting)}"
            )


@dataclass(frozen=True)
class ContestedMetric:
    """A metric more than one verified quotation pulls in different directions."""

    metric: str
    candidates: tuple[MemberAnswer, ...]

    def __post_init__(self) -> None:
        """Refuse a contest that is not one: verified answers that agree settled it."""
        refuse_unknown_metric(self.metric)
        if len({answer.value for answer in self.candidates}) < 2:
            raise ValueError(
                f"{self.metric} is not contested; its verified answers support one value"
            )


@dataclass(frozen=True)
class UnresolvedMetric:
    """A metric no member's quotation could settle, and where its value came from instead.

    Two different things arrive here and the record has to keep them apart, so
    this does not claim either: every member may have declined, in which case the
    advisory really is silent on the metric, or members may have answered and not
    one quotation was in the text, in which case the advisory may say plenty and
    the readers failed. The round's replies say which happened.
    """

    metric: str
    fallback: Fallback

    def __post_init__(self) -> None:
        """Refuse an unresolved ruling whose fallback is not a value this metric allows."""
        refuse_unknown_metric(self.metric)
        if isinstance(self.fallback, PublishedFallback):
            refuse_illegal_pair(self.metric, self.fallback.value)
            return
        if not isinstance(self.fallback, NoFallbackPublished):
            raise TypeError(
                f"{self.metric} needs a PublishedFallback or a NoFallbackPublished, "
                f"not {type(self.fallback).__name__}"
            )


MetricRuling = SettledMetric | ContestedMetric | UnresolvedMetric


def refuse_unknown_metric(metric: str) -> None:
    """Refuse a ruling about a metric the specification does not have."""
    if metric in METRIC_ORDER:
        return
    raise ValueError(
        f"{metric!r} is not a CVSS Base metric; the eight are {', '.join(METRIC_ORDER)}"
    )
