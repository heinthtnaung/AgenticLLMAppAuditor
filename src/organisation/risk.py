"""What this environment's answers make of one finding -- once for every source.

**Scored once per source, because choosing one source would be the precedence
`docs/SCORING_MODEL.md` leaves open.** Taking NVD would be the merge it forbids,
and NVD carries a vector for 4 of the 18 findings on the repository under test.
So a finding with GHSA at 6.5 and Red Hat at 8.2 gets two organisation scores,
and the question that matters is whether they land in different **bands**.

That question is worth asking because it has both answers. The environment terms
are the same for every source, so an organisation score is
`0.30 x technical + 0.70 x the rest` -- and against the 25/50/75 boundaries a
CVSS disagreement can stop mattering (6.5 against 8.2, Medium against High,
comes out Low and Low in an unexposed environment) or start mattering (7.3
against 8.2, both High, comes out Medium against High in an ordinary one).
Neither is visible from the published scores alone.

When a council has settled a vector there is one agreed technical severity and
one score. When nobody scored a finding at all there is still one score, with
technical contributing nothing and the whole thing flagged provisional.
"""

from dataclasses import dataclass

from cvss.score import base_score
from cvss.vector import parse
from findings.finding import Finding
from scoring.bands import RISK_BANDS
from scoring.category import CategoryScore, score_category
from scoring.library import ANSWERED_CATEGORIES, answers_for, refuse_incomplete
from scoring.question import Answer, Category
from scoring.risk_score import RiskScore, organisation_risk_score
from scoring.technical import TechnicalInput, UnknownTechnicalSeverity, from_cvss_base_score

BAND_ORDER: tuple[str, ...] = tuple(name for _, name in RISK_BANDS)

COUNCIL_SOURCE = "the assessor council"
NOTHING_PUBLISHED = "no source published a readable v3 vector"


@dataclass(frozen=True)
class FindingRisk:
    """Every organisation score one finding carries, one per technical severity offered."""

    advisory_id: str
    scores: tuple[RiskScore, ...]

    @property
    def bands(self) -> tuple[str, ...]:
        """Name the distinct bands this finding lands in, worst first."""
        reached = {one.band for one in self.scores}
        return tuple(name for name in BAND_ORDER if name in reached)

    @property
    def band_depends_on_the_source(self) -> bool:
        """Say whether which source you believe changes what this organisation should do."""
        return len(self.bands) > 1

    @property
    def is_provisional(self) -> bool:
        """Say whether anything here was answered Unknown, or nobody scored the finding."""
        return any(one.is_provisional for one in self.scores)


def assess(
    finding: Finding, answers_by_id: dict[str, Answer], technical: tuple[TechnicalInput, ...]
) -> FindingRisk:
    """Score one finding once for each technical severity it was offered."""
    if not technical:
        raise ValueError(f"{finding.advisory.advisory_id} was offered no technical severity")
    # Held on the type that scores rather than only where a file is read: an
    # unanswered question scored as a No, and no caller may reach that again.
    refuse_incomplete(answers_by_id)
    categories = category_scores(answers_by_id)
    return FindingRisk(
        advisory_id=finding.advisory.advisory_id,
        scores=tuple(weigh(one, categories) for one in technical),
    )


def weigh(technical: TechnicalInput, categories: dict[Category, CategoryScore]) -> RiskScore:
    """Put one technical severity through the engine with this environment's categories."""
    return organisation_risk_score(
        technical=technical,
        exposure=categories[Category.EXPOSURE],
        business=categories[Category.BUSINESS],
        threat=categories[Category.THREAT],
    )


def category_scores(answers_by_id: dict[str, Answer]) -> dict[Category, CategoryScore]:
    """Score every category an organisation is asked about, from answers given by id."""
    return {
        category: score_category(category, answers_for(category, answers_by_id))
        for category in ANSWERED_CATEGORIES
    }


def per_source(finding: Finding) -> tuple[TechnicalInput, ...]:
    """Give one technical severity per source that scored the finding, each naming its source."""
    if not finding.scores:
        return (UnknownTechnicalSeverity(reason=NOTHING_PUBLISHED),)
    return tuple(from_cvss_base_score(one.base_score, one.source) for one in finding.scores)


def from_council(vector: str) -> tuple[TechnicalInput, ...]:
    """Give the one technical severity a council settled, which needs no choosing between."""
    return (from_cvss_base_score(base_score(parse(vector)), COUNCIL_SOURCE),)
