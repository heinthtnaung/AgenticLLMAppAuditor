"""The version of the rules behind an Organisation Risk Score, its band and its provisional flag.

Two scores are only comparable if the same rules produced them, and every one of
these can move a score, a band or the provisional flag: the approved questions,
their text and what a Yes to each is worth; the category weights; the 0-100
clamp and the CVSS scale onto it; the band thresholds; the severity floors; and
what marks a score provisional. `SCORING_RULES_VERSION` names that set, and
every report carries it in its provenance.

**Bump it whenever any of them changes.** A test fingerprints the rules and what
the engine makes of a fixed set of answers against the version, so a rule that
moves without the version moving fails the suite rather than leaving two
reports that claim one scoring and used two.
"""

SCORING_RULES_VERSION = "ors-1"
