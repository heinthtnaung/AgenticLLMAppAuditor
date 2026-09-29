"""The categories and the scoring shortcut the risk-score tests share."""

from scoring.category import CategoryScore, score_category
from scoring.question import Answer, Category, Question
from scoring.risk_score import RiskScore, organisation_risk_score
from scoring.technical import TechnicalSeverity, UnknownTechnicalSeverity
from scoring_samples import BUSINESS_QUESTIONS, EXPOSURE_QUESTIONS, THREAT_QUESTIONS, all_answered

NOTHING_EXPOSED = score_category(Category.EXPOSURE, all_answered(EXPOSURE_QUESTIONS, Answer.NO))
NO_BUSINESS_IMPACT = score_category(Category.BUSINESS, all_answered(BUSINESS_QUESTIONS, Answer.NO))
NO_THREAT = score_category(Category.THREAT, all_answered(THREAT_QUESTIONS, Answer.NO))
BUSINESS_CRITICAL_ASSET = score_category(
    Category.BUSINESS, all_answered(BUSINESS_QUESTIONS, Answer.YES)
)


def no_except(category: Category, questions: tuple[Question, ...],
              changed: dict[Question, Answer]) -> CategoryScore:
    """Score one category with every question answered No except the ones given."""
    return score_category(category, {**all_answered(questions, Answer.NO), **changed})


def scored(
    technical: TechnicalSeverity | UnknownTechnicalSeverity,
    exposure: CategoryScore = NOTHING_EXPOSED,
    business: CategoryScore = NO_BUSINESS_IMPACT,
    threat: CategoryScore = NO_THREAT,
) -> RiskScore:
    """Score one assessment, defaulting every category a test is not about to nothing."""
    return organisation_risk_score(
        technical=technical, exposure=exposure, business=business, threat=threat
    )
