"""The 0-100 scale a category score is measured on.

Both a `CategoryScore` and a `TechnicalSeverity` are bounded by it, and
`scoring.risk_score.weighted_total` adds them together -- so two definitions
could drift and leave the engine summing two scales while looking as though it
summed one. They cannot legitimately differ, so there is one of them.

Here rather than in `category.py` because a technical severity is **not** a
`CategoryScore`: the caller supplies it, no question produces it, and the shape
of this engine depends on that staying visible. Sharing a scale is all the two
have in common, and this module is that and nothing else.
"""

MINIMUM_CATEGORY_SCORE = 0.0
MAXIMUM_CATEGORY_SCORE = 100.0
