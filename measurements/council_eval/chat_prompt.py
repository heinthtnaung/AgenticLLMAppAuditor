"""The prompt a person pastes into a chat interface: one advisory, all eight metrics, one message.

The local council asks one metric per call, the definitions in the system turn
and the advisory alone in the user turn (`council.prompt`). A chat interface
gives a person no system turn, and eight pastes per advisory would be eight
times the work, so this prompt differs from the council's in two ways, on
purpose, and is a prompt version of its own:

- **all eight metrics in one message**, answered in one reply;
- **the definitions share the message with the advisory.** `council.prompt`
  records that sharing a turn made a local model quote the definitions back as
  its evidence, so `chat-replies` counts how often a reply does.

The rest is the council's own: the redacted advisory (`council.redaction`), the
definitions as `council.prompt` renders them, the reply's field names and
`NO_EVIDENCE` (`council.reply_format`), and each metric's options in the
specification's order or reversed.

The PROMPT-ID is the start of the SHA-256 of the body, which is everything above
the closing line, so a reply that repeats it names the words it answered. **Nothing
pasted says which order a prompt is in**: a chat told it reads the reversed list
could answer the telling rather than the list, which is the bias the reversal is
there to catch. The order is the manifest's and the import's, found by the ID.
"""

import hashlib
import json
from itertools import chain

from council.definitions import definition_of
from council.prompt import describe, listed, value_lines
from council.reply_format import (
    CONFIDENCE_FIELD,
    CONFIDENCE_WORDS,
    EVIDENCE_FIELD,
    NO_EVIDENCE_VALUE,
    VALUE_FIELD,
)
from cvss.metrics import METRIC_ORDER

CHAT_PROMPT_VERSION = "chat-all-base-metrics-1"

FORWARD = "forward"
REVERSED = "reversed"
PROMPT_ID_FIELD = "prompt_id"
PROMPT_ID_LABEL = "PROMPT-ID"
PROMPT_ID_CHARACTERS = 16
SCHEMA_INDENT = "  "

RULES = f"""\
You assess the eight CVSS v3.1 Base metrics of one security advisory, from the
text of that advisory and from nothing else.

Rules:
1. Use only the text under ADVISORY below.
2. Do not browse the web, and do not use anything you remember about this
   vulnerability from elsewhere.
3. Support each value with a quotation copied word for word from the advisory.
   Application code checks every quotation against the advisory, and an
   invented or reworded one is thrown out.
4. If the advisory says nothing that supports any value of a metric, answer
   {NO_EVIDENCE_VALUE} for that metric. Declining is a correct answer. Guessing is not.
5. Reply with exactly one fenced JSON block, in the shape under REPLY FORMAT,
   and nothing else."""

DEFINITIONS_LEAD = """\
DEFINITIONS

These are reference material. They are not the advisory and you may not quote them."""

ADVISORY_HEADING = "ADVISORY"
REPLY_HEADING = "REPLY FORMAT"
FENCE_OPEN = "```json"
FENCE_CLOSE = "```"

PROMPT_ID_ASKED = f"the {PROMPT_ID_LABEL} on the last line of this message"
EVIDENCE_ASKED = (
    f"a quotation copied word for word from the advisory -- or empty for {NO_EVIDENCE_VALUE}"
)
CONFIDENCE_ASKED = f"one of {', '.join(CONFIDENCE_WORDS)}"


def chat_prompt_body(advisory_shown: str, reversed_options: bool) -> str:
    """Render the words a chat is asked, for one redacted advisory, in either order."""
    sections = (
        RULES,
        DEFINITIONS_LEAD,
        *(metric_section(metric, reversed_options) for metric in METRIC_ORDER),
        f"{ADVISORY_HEADING}\n\n{advisory_shown.strip()}",
        f"{REPLY_HEADING}\n\n{reply_format(reversed_options)}",
    )
    return "\n\n".join(sections) + "\n"


def chat_prompt_file(body: str) -> str:
    """Give the whole text to paste: the body, then the line naming its ID."""
    return f"{body}\n{PROMPT_ID_LABEL}: {prompt_id(body)}\n"


def prompt_id(body: str) -> str:
    """Name a prompt by the start of its body's SHA-256."""
    return text_digest(body)[:PROMPT_ID_CHARACTERS]


def text_digest(text: str) -> str:
    """Fingerprint a text by the SHA-256 of its UTF-8 bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def order_name(reversed_options: bool) -> str:
    """Name the order a prompt lists each metric's options in."""
    return REVERSED if reversed_options else FORWARD


def metric_section(metric: str, reversed_options: bool) -> str:
    """Render one metric's definition and its values, in the order this prompt lists them."""
    return "\n".join((describe(metric), *value_lines(metric, reversed_options)))


def reply_format(reversed_options: bool) -> str:
    """Render the reply's shape: a fenced JSON object, keyed by metric, as valid JSON."""
    metrics = [schema_line(one, metric_schema(one, reversed_options)) for one in METRIC_ORDER]
    fields = [schema_line(PROMPT_ID_FIELD, PROMPT_ID_ASKED), *metrics]
    return "\n".join((FENCE_OPEN, "{", ",\n".join(fields), "}", FENCE_CLOSE))


def schema_line(key: str, shown: object) -> str:
    """Render one key of the reply's shape on one line."""
    return f"{SCHEMA_INDENT}{json.dumps(key)}: {json.dumps(shown)}"


def metric_schema(metric: str, reversed_options: bool) -> dict[str, str]:
    """Say what each of one metric's three fields may hold, its values in this prompt's order."""
    values = ", ".join(listed(tuple(definition_of(metric).value_meanings), reversed_options))
    return {
        VALUE_FIELD: f"one of {values} -- or {NO_EVIDENCE_VALUE}",
        EVIDENCE_FIELD: EVIDENCE_ASKED,
        CONFIDENCE_FIELD: CONFIDENCE_ASKED,
    }


def definition_texts() -> tuple[str, ...]:
    """Give every definition this prompt shows, which a quotation of is the prompt's own words."""
    definitions = [definition_of(metric) for metric in METRIC_ORDER]
    meanings = chain.from_iterable(one.value_meanings.values() for one in definitions)
    return (*(one.measures for one in definitions), *meanings)
