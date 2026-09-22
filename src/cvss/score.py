"""The CVSS Base score: the weights and equations of the v3.1 specification, section 7.1.

Deterministic and total: the same vector gives the same number on every machine,
with no model, no clock and no network in the path. Somebody has to be able to
re-derive a published score by hand from the record.
"""

import math

from cvss.metrics import (
    ATTACK_COMPLEXITY,
    ATTACK_VECTOR,
    IMPACT_METRICS,
    PRIVILEGES_REQUIRED,
    SCOPE,
    SCOPE_CHANGED,
    USER_INTERACTION,
)
from cvss.vector import CvssVector

ATTACK_VECTOR_WEIGHTS = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
ATTACK_COMPLEXITY_WEIGHTS = {"L": 0.77, "H": 0.44}
USER_INTERACTION_WEIGHTS = {"N": 0.85, "R": 0.62}
IMPACT_WEIGHTS = {"H": 0.56, "L": 0.22, "N": 0.0}

# Privileges Required is worth more when Scope changed: the same privilege buys
# the attacker more. This is the one weight table that depends on another metric.
PRIVILEGES_REQUIRED_WEIGHTS_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
PRIVILEGES_REQUIRED_WEIGHTS_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.50}

EXPLOITABILITY_COEFFICIENT = 8.22
IMPACT_COEFFICIENT_UNCHANGED = 6.42
IMPACT_COEFFICIENT_CHANGED = 7.52
IMPACT_OFFSET_CHANGED = 0.029
IMPACT_PENALTY_COEFFICIENT = 3.25
IMPACT_PENALTY_OFFSET = 0.02
IMPACT_PENALTY_EXPONENT = 15
SCOPE_CHANGED_MULTIPLIER = 1.08

MINIMUM_SCORE = 0.0
MAXIMUM_SCORE = 10.0

# The specification's integer roundup works at 1/100000 and then steps in
# 1/10000 units, which is one tenth of a point at that magnitude.
ROUNDUP_SCALE = 100000
ROUNDUP_STEP = 10000
TENTHS_PER_POINT = 10.0

# Descending, so the first threshold a score reaches is its band. The 0.0 floor
# means every score on the scale lands somewhere.
SEVERITY_BANDS = (
    (9.0, "Critical"),
    (7.0, "High"),
    (4.0, "Medium"),
    (0.1, "Low"),
    (0.0, "None"),
)


def base_score(vector: CvssVector) -> float:
    """Compute the CVSS Base score for a parsed vector, rounded to one decimal."""
    impact = impact_score(vector)
    # Zero impact is zero score however reachable the weakness is, and the check
    # happens before rounding: an unrounded negative impact must not round up.
    if impact <= MINIMUM_SCORE:
        return MINIMUM_SCORE
    total = impact + exploitability_score(vector)
    if is_scope_changed(vector):
        total *= SCOPE_CHANGED_MULTIPLIER
    return roundup(min(total, MAXIMUM_SCORE))


def impact_score(vector: CvssVector) -> float:
    """The Impact sub-score, which takes a different equation when Scope changed."""
    lost = impact_sub_score_base(vector)
    if not is_scope_changed(vector):
        return IMPACT_COEFFICIENT_UNCHANGED * lost
    penalty = IMPACT_PENALTY_COEFFICIENT * (lost - IMPACT_PENALTY_OFFSET) ** IMPACT_PENALTY_EXPONENT
    return IMPACT_COEFFICIENT_CHANGED * (lost - IMPACT_OFFSET_CHANGED) - penalty


def impact_sub_score_base(vector: CvssVector) -> float:
    """ISCBase: how much of confidentiality, integrity and availability is lost."""
    retained = [1 - IMPACT_WEIGHTS[vector.value(metric)] for metric in IMPACT_METRICS]
    return 1 - math.prod(retained)


def exploitability_score(vector: CvssVector) -> float:
    """How readily the weakness can be reached and triggered."""
    return (
        EXPLOITABILITY_COEFFICIENT
        * ATTACK_VECTOR_WEIGHTS[vector.value(ATTACK_VECTOR)]
        * ATTACK_COMPLEXITY_WEIGHTS[vector.value(ATTACK_COMPLEXITY)]
        * privileges_required_weight(vector)
        * USER_INTERACTION_WEIGHTS[vector.value(USER_INTERACTION)]
    )


def privileges_required_weight(vector: CvssVector) -> float:
    """Pick the Privileges Required weight for this vector's Scope."""
    if is_scope_changed(vector):
        return PRIVILEGES_REQUIRED_WEIGHTS_CHANGED[vector.value(PRIVILEGES_REQUIRED)]
    return PRIVILEGES_REQUIRED_WEIGHTS_UNCHANGED[vector.value(PRIVILEGES_REQUIRED)]


def is_scope_changed(vector: CvssVector) -> bool:
    """Say whether exploiting this weakness affects resources beyond its own scope."""
    return vector.value(SCOPE) == SCOPE_CHANGED


def roundup(value: float) -> float:
    """Round up to one decimal by the specification's integer method (v3.1, 7.1).

    Not `math.ceil(value * 10) / 10`. The specification warns against that form by
    name: binary floating point makes it turn 8.6 into 8.7 for some inputs, and a
    score wrong in the first decimal can be wrong in its severity band.
    """
    # Half-up, matching the reference calculator; Python's round() is half-to-even.
    scaled = math.floor(value * ROUNDUP_SCALE + 0.5)
    if scaled % ROUNDUP_STEP == 0:
        return scaled / ROUNDUP_SCALE
    return (scaled // ROUNDUP_STEP + 1) / TENTHS_PER_POINT


def severity_band(score: float) -> str:
    """Name the CVSS severity band for a base score, refusing a number off the scale."""
    if not math.isfinite(score) or score < MINIMUM_SCORE or score > MAXIMUM_SCORE:
        raise ValueError(f"{score!r} is not a CVSS score; the scale runs 0.0 to 10.0")
    return next(name for threshold, name in SEVERITY_BANDS if score >= threshold)
