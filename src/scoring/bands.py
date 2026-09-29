"""The organisation bands: what a 0-100 score is called.

**These are not the CVSS bands.** `src/cvss/score.py` has those; they run 0.0 to
10.0, they are named differently, and they answer a different question -- how
severe the flaw is in general, rather than what it is worth in this environment.
A CVE can be CVSS Critical and organisation Medium, and reusing one function for
both scales would quietly make that impossible to say.
"""

import math

MINIMUM_SCORE = 0.0
MAXIMUM_SCORE = 100.0

# Descending, so the first threshold a score reaches is its band. The 0 floor
# means every score on the scale lands somewhere.
RISK_BANDS = ((75.0, "Critical"), (50.0, "High"), (25.0, "Medium"), (0.0, "Low"))


def risk_band(score: float) -> str:
    """Name the organisation band for a 0-100 score, refusing a number off the scale."""
    if not math.isfinite(score) or score < MINIMUM_SCORE or score > MAXIMUM_SCORE:
        raise ValueError(f"{score!r} is not an Organisation Risk Score; the scale runs 0 to 100")
    return next(name for threshold, name in RISK_BANDS if score >= threshold)
