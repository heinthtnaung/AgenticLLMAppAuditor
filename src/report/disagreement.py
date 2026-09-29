"""How far apart a finding's sources are, which is the question a reader brings to it.

Eighteen findings with up to five sources each is more rows than anyone reads.
What a reader wants is *where the sources disagree and how badly*, so that is
what the record is measured by and what the text rendering leads with.

**Disagreement is about metrics, not scores.** On the repository under test,
`CVE-2026-2950` has GHSA and Red Hat both at 6.5 while reading Privileges
Required, Integrity and Availability differently. Measured by score alone those
two agree; they do not, and that is the most deceptive shape a disagreement
takes. So `sources_disagree` asks the vectors.

**How badly is measured by what it would change.** A spread inside one severity
band is a number moving; a spread across a boundary is the response time moving,
which is a decision. So a finding whose sources put it in different bands sorts
above one with a wider spread inside a single band.
"""

from cvss.score import SEVERITY_BANDS, severity_band
from findings.finding import Finding

# Worst first, read off the bands themselves so this cannot drift from them.
BAND_ORDER: tuple[str, ...] = tuple(name for _, name in SEVERITY_BANDS)

SCORE_DECIMALS = 1


def sources_disagree(finding: Finding) -> bool:
    """Say whether the readable sources differ on any metric, whatever their scores came to."""
    return bool(finding.disputed_metrics())


def carries_a_refused_source(finding: Finding) -> bool:
    """Say whether any source's vector was refused, which leaves its reading unknown."""
    return bool(finding.unreadable)


def sources_agree(finding: Finding) -> bool:
    """Say whether every source was read and the readings match on every metric."""
    # A refused vector is an opinion nobody could read, so a finding carrying one
    # is never counted as agreeing, whatever the sources that were read say.
    return finding.is_scored and not finding.unreadable and not sources_disagree(finding)


def agreement_unchecked(finding: Finding) -> bool:
    """Say whether the readable sources match beside a source whose vector was refused."""
    return finding.is_scored and bool(finding.unreadable) and not sources_disagree(finding)


def score_spread(finding: Finding) -> float:
    """Give the distance between the highest and lowest score published for a finding."""
    scores = [score.base_score for score in finding.scores]
    if len(scores) < 2:
        return 0.0
    return round(max(scores) - min(scores), SCORE_DECIMALS)


def bands_crossed(finding: Finding) -> tuple[str, ...]:
    """Name the distinct severity bands a finding's sources put it in, worst first."""
    reached = {severity_band(score.base_score) for score in finding.scores}
    return tuple(name for name in BAND_ORDER if name in reached)


def crosses_a_band(finding: Finding) -> bool:
    """Say whether the sources disagree about the response this finding deserves."""
    return len(bands_crossed(finding)) > 1


def most_contested_first(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    """Order findings by how much their disagreement could change a decision."""
    return tuple(sorted(findings, key=contest_order))


def contest_order(finding: Finding) -> tuple[int, float, int, str, str]:
    """Rank a finding by consequence, then by name so two runs order identically."""
    # Negated rather than reversed, so the tie-breaks stay in ascending order and
    # the same set of findings always prints in the same order.
    return (
        -len(bands_crossed(finding)),
        -score_spread(finding),
        -len(finding.disputed_metrics()),
        finding.advisory.advisory_id,
        finding.component.name,
    )
