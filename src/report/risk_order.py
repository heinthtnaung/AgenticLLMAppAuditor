"""The order the organisation scores are read in, shared by every rendering.

Here rather than inside one renderer, because the order is a claim about what
matters -- **whether which source you believe changes what this organisation
should do** -- and two copies of that claim drift apart the first time one of
them is tuned. A finding whose band moves with the source sorts above one that
scores higher and is settled, because the second needs no decision.
"""

from typing import Iterable

from organisation.risk import FindingRisk


def bands_contested_first(weighed: Iterable[FindingRisk]) -> tuple[FindingRisk, ...]:
    """Order the scored findings by how much the choice of source would change."""
    return tuple(sorted(weighed, key=risk_order))


def risk_order(weighed: FindingRisk) -> tuple[int, float, str]:
    """Put the findings whose band depends on the source first, then the worst score."""
    return (
        0 if weighed.band_depends_on_the_source else 1,
        -max(one.score for one in weighed.scores),
        weighed.advisory_id,
    )
