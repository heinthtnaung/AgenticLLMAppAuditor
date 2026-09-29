"""Guards on the scoring rules' version: no rule moves without it moving.

The fingerprint covers the rules as data -- every approved question, its text
and weight, the category weights, the clamp, the CVSS scale onto it, the band
thresholds, the rounding and the floors -- and what the engine makes of a fixed
set of answers, score, bands, floors and whether it is provisional, so a change
to how the rules are applied, or to what marks a score provisional, moves it too.
"""

import json
from hashlib import sha256
from itertools import product

from scoring.bands import RISK_BANDS
from scoring.category import score_category
from scoring.floors import SEVERITY_FLOORS
from scoring.library import ANSWERED_CATEGORIES, APPROVED_QUESTIONS, answers_for
from scoring.question import Answer, Category
from scoring.risk_score import CATEGORY_WEIGHTS, SCORE_DECIMALS, organisation_risk_score
from scoring.scale import MAXIMUM_CATEGORY_SCORE, MINIMUM_CATEGORY_SCORE
from scoring.technical import (
    CVSS_TO_CATEGORY_SCALE, UnknownTechnicalSeverity, from_cvss_base_score,
)
from scoring.version import SCORING_RULES_VERSION

# The rules, fingerprinted. A weight, a threshold, a question or a floor that
# moves without `SCORING_RULES_VERSION` moving leaves two reports claiming one
# scoring that used two, so that failure is caught here.
RULES_FINGERPRINTS = {
    "ors-1": "85c9143d3907929ab55357d41927a94110f9eb71b03d58f0ebc0bc10a01aee29",
}
BUMP = (
    "The scoring rules changed: bump SCORING_RULES_VERSION in src/scoring/version.py, "
    "then record the new fingerprint here under it"
)

EVERY_ID = tuple(asked.question_id for asked in APPROVED_QUESTIONS)
TECHNICAL = (
    from_cvss_base_score(0.0, "fixed"),
    from_cvss_base_score(5.0, "fixed"),
    from_cvss_base_score(9.8, "fixed"),
    UnknownTechnicalSeverity(reason="fixed"),
)


def rules() -> dict:
    """Give every rule that decides a score or a band, as plain data in a fixed order."""
    return {
        "questions": [
            [one.question_id, one.text, one.category.value, one.yes_weight]
            for one in APPROVED_QUESTIONS
        ],
        "category_weights": [[one.value, weight] for one, weight in CATEGORY_WEIGHTS.items()],
        "clamp": [MINIMUM_CATEGORY_SCORE, MAXIMUM_CATEGORY_SCORE],
        "cvss_scale": CVSS_TO_CATEGORY_SCALE,
        "score_decimals": SCORE_DECIMALS,
        "bands": [list(one) for one in RISK_BANDS],
        "floors": [
            [one.rule_id, list(one.answered_yes), one.floor_band] for one in SEVERITY_FLOORS
        ],
    }


def answered_everywhere(answer: Answer) -> dict[str, Answer]:
    """Answer every approved question the same way."""
    return {one: answer for one in EVERY_ID}


def yes_to(identifiers: tuple[str, ...]) -> dict[str, Answer]:
    """Answer the questions named Yes and every other one No."""
    return {**answered_everywhere(Answer.NO), **dict.fromkeys(identifiers, Answer.YES)}


def answer_sets() -> list[dict[str, Answer]]:
    """Give a fixed set of environments: each answer everywhere, each Yes alone, each floor."""
    alike = [answered_everywhere(answer) for answer in Answer]
    alone = [yes_to((one,)) for one in EVERY_ID]
    floors = [yes_to(rule.answered_yes) for rule in SEVERITY_FLOORS]
    return [*alike, *alone, *floors]


def outcome(technical, answers: dict[str, Answer]) -> list:
    """Give what the engine makes of one technical severity in one environment."""
    categories = {
        category: score_category(category, answers_for(category, answers))
        for category in ANSWERED_CATEGORIES
    }
    scored = organisation_risk_score(
        technical=technical,
        exposure=categories[Category.EXPOSURE],
        business=categories[Category.BUSINESS],
        threat=categories[Category.THREAT],
    )
    floors = [one.rule_id for one in scored.floors]
    return [scored.score, scored.score_band, scored.band, floors, scored.is_provisional]


def outcomes() -> list:
    """Give the engine's answer for every technical severity in every fixed environment."""
    pairs = product(answer_sets(), TECHNICAL)
    return [outcome(technical, answers) for answers, technical in pairs]


def fingerprint() -> str:
    """Fingerprint the rules and what the engine makes of them."""
    held = json.dumps({"rules": rules(), "outcomes": outcomes()}, sort_keys=True)
    return sha256(held.encode("utf-8")).hexdigest()


def test_no_scoring_rule_has_moved_without_the_version_moving():
    assert SCORING_RULES_VERSION in RULES_FINGERPRINTS, BUMP
    assert fingerprint() == RULES_FINGERPRINTS[SCORING_RULES_VERSION], BUMP
