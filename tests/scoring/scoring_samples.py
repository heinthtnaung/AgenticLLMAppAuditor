"""The questions and answers the scoring tests weigh, built by hand.

The exposure table is the one in `docs/SCORING_MODEL.md`, quoted weight for
weight, because the worked example turns on it. The business and threat
questions are **this file's own**: the design gives exposure "for example" and
leaves the rest to an approved template library that is not built. Their weights
are chosen to make the worked example's business impact of 80 visible as three
answers rather than one magic number, and they are not a proposed library.

Named `scoring_samples` and not `samples`: pytest puts each test directory on
the path and imports by basename, so a second `samples.py` would be shadowed by
`tests/deps/samples.py`.
"""

from scoring.question import Answer, Category, Question

# docs/SCORING_MODEL.md, "Turning answers into a category score".
INTERNET_FACING = Question(
    "EXP-1", "Is the affected service internet-facing?", Category.EXPOSURE, 40
)
UNTRUSTED_NETWORK = Question(
    "EXP-2", "Is it reachable from an untrusted network?", Category.EXPOSURE, 25
)
PORT_EXPOSED = Question("EXP-3", "Is the vulnerable port or API exposed?", Category.EXPOSURE, 20)
SEGMENTED = Question("EXP-4", "Is the asset isolated or segmented?", Category.EXPOSURE, -15)
DISABLED = Question("EXP-5", "Is the component disabled?", Category.EXPOSURE, -30)

EXPOSURE_QUESTIONS = (INTERNET_FACING, UNTRUSTED_NETWORK, PORT_EXPOSED, SEGMENTED, DISABLED)

# This file's own, summing to the 80 the worked example prints.
BUSINESS_CRITICAL = Question("BUS-1", "Is the asset business-critical?", Category.BUSINESS, 40)
IN_PRODUCTION = Question("BUS-2", "Is it in production?", Category.BUSINESS, 20)
SENSITIVE_DATA = Question("BUS-3", "Does it hold sensitive data?", Category.BUSINESS, 20)

BUSINESS_QUESTIONS = (BUSINESS_CRITICAL, IN_PRODUCTION, SENSITIVE_DATA)

EXPLOITED = Question("THR-1", "Is this CVE being exploited in the wild?", Category.THREAT, 50)
PUBLIC_EXPLOIT = Question("THR-2", "Is a public exploit available?", Category.THREAT, 30)
AUTOMATED = Question("THR-3", "Is exploitation automated?", Category.THREAT, 20)

THREAT_QUESTIONS = (EXPLOITED, PUBLIC_EXPLOIT, AUTOMATED)


ALL_QUESTIONS = EXPOSURE_QUESTIONS + BUSINESS_QUESTIONS + THREAT_QUESTIONS


def all_answered(questions: tuple[Question, ...], answer: Answer) -> dict[Question, Answer]:
    """Answer every question of a category the same way."""
    return {question: answer for question in questions}
