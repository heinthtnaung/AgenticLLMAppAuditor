"""What one member is asked about one metric, and the version of the asking.

Three properties of this prompt are measurement decisions from
`docs/COUNCIL.md`, not preferences:

- **One metric at a time**, with that metric's definition in the prompt. There
  is no retrieval layer and none is needed; the definitions are a constant.
- **The advisory text only.** Not the other members' answers, not the published
  scores, not the CVE id. `council.redaction` takes the last two out of the text
  before it gets here, because a sentence in a prompt cannot unsee an id.
- **A verbatim quotation**, asked for explicitly, with declining named as the
  better answer than inventing one. `council.evidence` then checks it.

**Why the definitions are in the system turn and the advisory alone in the
user turn.** Over 144 replies -- 18 real advisories by 8 metrics -- 24 of the 77
quotations offered did not verify, and **20 of those 24 were the model quoting
this prompt's own value definitions back as its evidence**, 16 of them on
Attack Complexity. Version 2 tried to fix that by fencing the advisory between
markers and saying in the instruction that the definitions are not evidence. It
made it worse: on Attack Complexity, verified quotations went 2 -> 0 and
definition-quoting 16 -> 18. Naming the definitions appears to prime them.
Version 3 separates the two turns instead, and on the same 18 advisories with
the same seed it took Attack Complexity to **10 verified of 18** against
version 1's 2. Structure beat instruction; both were measured rather than
argued.

**Measured, and not fixed by wording.** On one advisory, asked about the two
metrics that advisory is silent on, qwen2.5:7b-instruct answered the value it
believed with an empty quotation -- `A:N` and `UI:N` -- rather than declining.
An extra instruction forbidding an empty quotation changed neither case, so the
prompt does not carry one and `council.reply` records an unquoted value for
what it is. That is where this project puts guarantees: in code, not in a line
of a prompt. **Two metrics, one model, one advisory**: enough to have changed
the design, not enough to be a property of local models. A general version of
that claim is a corpus run, and its denominator is **metric-advisory pairs
where the text is silent**, not advisories -- labelling which pairs those are
is the hard part of the measurement, not running the model.

`PROMPT_VERSION` rides on every answer because `docs/SCORING_MODEL.md` keeps the
prompt and model version for audit. **Bump it whenever the wording below
changes**: two answers are only comparable if the same question produced them.
A test fingerprints the rendered prompt against the version, so wording that
moves without the version moving fails the suite rather than quietly spoiling a
comparison.
"""

import json
from dataclasses import dataclass

from council.definitions import definition_of
from council.redaction import redact
from council.reply_format import (
    CONFIDENCE_FIELD,
    CONFIDENCE_WORDS,
    EVIDENCE_FIELD,
    NO_EVIDENCE_VALUE,
    VALUE_FIELD,
)
from cvss.metrics import metric_name

PROMPT_VERSION = "member-base-metric-3"

SCHEMA_INDENT = 2

SYSTEM_TEMPLATE = f"""\
You assess one metric of the CVSS v3.1 Base score from the text of a security
advisory, and from nothing else.

You are one of several assessors reading this advisory independently. You will
not see what the others answered, and you must not guess at it.

The metric you are assessing, and what its values mean:

{{description}}

{{values}}

That definition is reference material. It is not the advisory and you may not
quote it.

- Decide only this metric. Say nothing about the others.
- Judge from the advisory text in the next message. Do not use anything you may
  remember about this vulnerability from elsewhere.
- Support your value with a quotation copied word for word from that advisory.
  Inventing a quotation is worse than declining: application code checks it
  against the advisory, and an invented or reworded one is thrown out.
- If the advisory says nothing that supports any value, answer {NO_EVIDENCE_VALUE}.
  Declining is a correct answer. Guessing is not.
- Reply with one JSON object and nothing else.
"""

USER_TEMPLATE = """\
{advisory}

Reply with one JSON object of exactly these three fields:

{schema}
"""


@dataclass(frozen=True)
class MemberPrompt:
    """One question to one member: what it was asked, and exactly what it was shown.

    `advisory_shown` is the redacted text, which is what the member read, so it
    is also what its quotation must be checked against. `withheld` is what came
    out of the original, so a record can say the scores really were held back.
    """

    metric: str
    system: str
    user: str
    advisory_shown: str
    withheld: tuple[str, ...]
    version: str


def build_prompt(metric: str, advisory_text: str) -> MemberPrompt:
    """Build the prompt asking one member for one metric of one advisory."""
    advisory = redact(advisory_text)
    return MemberPrompt(
        metric=metric,
        system=system_prompt(metric),
        user=user_prompt(metric, advisory.text),
        advisory_shown=advisory.text,
        withheld=advisory.removed,
        version=PROMPT_VERSION,
    )


def system_prompt(metric: str) -> str:
    """Render the standing instruction: the rules, the metric, and what its values mean."""
    return SYSTEM_TEMPLATE.format(
        description=describe(metric), values="\n".join(value_lines(metric))
    )


def user_prompt(metric: str, advisory_text: str) -> str:
    """Render the turn the member answers: the advisory, and the shape of a reply."""
    return USER_TEMPLATE.format(advisory=advisory_text.strip(), schema=reply_schema(metric))


def describe(metric: str) -> str:
    """Say in one line what a metric measures, naming it in words as well as letters."""
    return f"{metric_name(metric)} ({metric}) measures {definition_of(metric).measures}"


def value_lines(metric: str) -> tuple[str, ...]:
    """List a metric's values as 'X = what it means' lines, in specification order."""
    meanings = definition_of(metric).value_meanings
    return tuple(f"{value} = {meaning}" for value, meaning in meanings.items())


def reply_schema(metric: str) -> str:
    """Show the exact JSON object a reply must be, naming this metric's own values."""
    allowed = ", ".join(definition_of(metric).value_meanings)
    return json.dumps(
        {
            VALUE_FIELD: (
                f"one of {allowed} -- or {NO_EVIDENCE_VALUE} "
                "if the advisory supports none of them"
            ),
            EVIDENCE_FIELD: (
                "a quotation copied word for word from the advisory above, "
                "never from the metric definition -- "
                f"or an empty string if you answered {NO_EVIDENCE_VALUE}"
            ),
            CONFIDENCE_FIELD: f"one of {', '.join(CONFIDENCE_WORDS)}",
        },
        indent=SCHEMA_INDENT,
    )
