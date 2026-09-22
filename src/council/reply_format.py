"""The shape a member's reply has to take, stated once for both halves.

`council.prompt` asks for exactly this and `council.reply` reads exactly this,
so the question and the parser cannot drift apart: a field renamed here moves
both at the same time.
"""

from council.answer import Confidence

VALUE_FIELD = "value"
EVIDENCE_FIELD = "evidence"
CONFIDENCE_FIELD = "confidence"

REQUIRED_FIELDS: tuple[str, ...] = (VALUE_FIELD, EVIDENCE_FIELD, CONFIDENCE_FIELD)

# Not asked for. Models add it anyway, and a reply that names a metric other
# than the one asked about answered a different question.
METRIC_FIELD = "metric"

# A word, not a letter, so it can never collide with a legal value of any Base
# metric -- every one of those is a single uppercase letter. A test holds that.
NO_EVIDENCE_VALUE = "NO_EVIDENCE"

CONFIDENCE_BY_WORD: dict[str, Confidence] = {level.value: level for level in Confidence}

CONFIDENCE_WORDS: tuple[str, ...] = tuple(CONFIDENCE_BY_WORD)
