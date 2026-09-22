"""What a local model really answered, kept as text so that no test calls one.

The first group was captured on 2026-09-22 from `qwen2.5:7b-instruct` through
`council.ollama`, with the pinning it defaults to, over `council_samples`'s
advisory. They are quoted exactly as they came back, wrapping included.

The malformed group is hand-made and says so. Asked through Ollama's own
`format: json` flag, this model returns a JSON object every time; a member
behind a provider with no such flag does not, and those are the replies that
have to be refused loudly rather than half-read.

Note what the captures show. The model reflows the advisory's line breaks when
it quotes it, which is why `council.evidence` folds whitespace. And on a metric
the advisory is silent about it answers the value with an empty quotation
instead of declining -- `A:N` here -- which `council.reply` reads as the guess
it is, keeping the value it leaned to.
"""

# Captured. Attack Vector, answered from the sentence about a remote attacker.
ATTACK_VECTOR = (
    '{\n  "value": "N",\n  "evidence": "An unauthenticated remote attacker can send a '
    "crafted request to the management port and read arbitrary files from the host's "
    'filesystem.",\n  "confidence": "high"\n}'
)

# Captured. Privileges Required, quoting two sentences at once.
PRIVILEGES_REQUIRED = (
    '{\n  "value": "N",\n  "evidence": "A flaw was found in the web console. An '
    "unauthenticated remote attacker can send a crafted request to the management port "
    "and read arbitrary files from the host's filesystem.\",\n  \"confidence\": \"high\"\n}"
)

# Captured. Scope, read as changed: the console reaches the host's filesystem.
SCOPE = (
    '{\n  "value": "C",\n  "evidence": "An unauthenticated remote attacker can send a '
    "crafted request to the management port and read arbitrary files from the host's "
    'filesystem.",\n  "confidence": "high"\n}'
)

# Captured. Availability: the advisory says nothing, and the model answers a
# value with nothing to support it rather than declining.
SILENT_METRIC = '{\n  "value": "N",\n  "evidence": "",\n  "confidence": "low"\n}'

# The quotation two of the captures carry, reflowed off the advisory's own lines.
RECORDED_QUOTATION = (
    "An unauthenticated remote attacker can send a crafted request to the management "
    "port and read arbitrary files from the host's filesystem."
)

DECLINED = '{"value": "NO_EVIDENCE", "evidence": "", "confidence": "low"}'

# Hand-made from here down: the shapes a model without a JSON format flag returns.
PROSE_AROUND_JSON = (
    "Sure -- here is my assessment of the metric you asked about.\n\n"
    '{"value": "N", "evidence": "unauthenticated remote attacker", "confidence": "high"}\n\n'
    "Let me know if you would like me to look at any of the other metrics."
)

CODE_FENCED = (
    "```json\n"
    '{"value": "N", "evidence": "unauthenticated remote attacker", "confidence": "medium"}\n'
    "```"
)

TRUNCATED = '{"value": "N", "evidence": "unauthenticated remote atta'

NO_JSON_AT_ALL = "Attack Vector is Network, because the attacker is remote."

MISSING_CONFIDENCE = '{"value": "N", "evidence": "unauthenticated remote attacker"}'

MISSING_VALUE = '{"evidence": "unauthenticated remote attacker", "confidence": "high"}'

# Answers a metric nobody asked about, which is a different question answered.
ANSWERS_ANOTHER_METRIC = (
    '{"metric": "AC", "value": "L", "evidence": "unauthenticated remote attacker", '
    '"confidence": "high"}'
)

# 'R' is a real CVSS value, of User Interaction, and is not one of Attack Vector's.
VALUE_OF_ANOTHER_METRIC = (
    '{"value": "R", "evidence": "unauthenticated remote attacker", "confidence": "high"}'
)

INVENTED_VALUE = (
    '{"value": "REMOTE", "evidence": "unauthenticated remote attacker", "confidence": "high"}'
)

CONFIDENCE_NOT_OFFERED = (
    '{"value": "N", "evidence": "unauthenticated remote attacker", "confidence": "very high"}'
)

VALUE_IS_NOT_TEXT = '{"value": 3, "evidence": "unauthenticated remote attacker", '
VALUE_IS_NOT_TEXT += '"confidence": "high"}'

EVIDENCE_IS_NOT_TEXT = '{"value": "N", "evidence": ["remote attacker"], "confidence": "high"}'

# Parses perfectly. The quotation is simply not in the advisory, which is
# `council.evidence`'s job to catch and not this parser's.
FABRICATED_QUOTATION = (
    '{"value": "L", "evidence": "the attacker must already hold local credentials", '
    '"confidence": "high"}'
)

# The whole pair rather than the letter: the member was asked about AV and said N.
WHOLE_PAIR = '{"value": "AV:N", "evidence": "unauthenticated remote attacker", '
WHOLE_PAIR += '"confidence": "High"}'
