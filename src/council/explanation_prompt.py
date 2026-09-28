"""What the explainer is asked: why the published sources read one advisory differently.

**It is told the disagreement, never the vectors.** For each disputed metric it
sees each source's value and what those values mean, and nothing of the metrics
the sources agree on. The advisory is redacted as a member's is
(`council.redaction`), so no CVE id or published vector reaches it either.

**The structure is the member prompt's, for the member prompt's measured
reason** (`council.prompt`): the instruction, the disagreement and the meanings
in the system turn, and the advisory alone in the user turn, because a model
asked to quote the advisory quotes whatever else shares its turn.

**Only the quotation is checked.** Each item carries a verbatim quotation, which
`council.explanation` holds to the advisory; the `why` beside it is the model's
own prose, which nothing here can check and the record labels as such.

`EXPLANATION_PROMPT_VERSION` rides on every explanation. **Bump it whenever the
wording below changes**: a test fingerprints the rendered prompt against it.
"""

import json
from dataclasses import dataclass
from typing import Mapping

from council.definitions import definition_of
from council.redaction import redact
from cvss.metrics import metric_name, refuse_illegal_pair

EXPLANATION_PROMPT_VERSION = "sources-differ-1"
SUBJECT = "explanation"
ITEMS_FIELD = "items"
METRIC_FIELD = "metric"
WHY_FIELD = "why"
QUOTATION_FIELD = "quotation"
SCHEMA_INDENT = 2
# Two different values at least, or there is no disagreement to explain.
FEWEST_VALUES = 2

SYSTEM_TEMPLATE = """\
You explain why published CVSS v3.1 assessments of one vulnerability disagree,
from the text of its security advisory and from nothing else.

The published sources gave these different values:

{disagreement}

For each metric above, say what in the advisory could lead one reader to one
value and another reader to another: a detail it states, leaves out, or leaves
open.

- Explain only the metrics above, one item each.
- Do not say which source is right.
- Judge from the advisory text in the next message. Do not use anything you may
  remember about this vulnerability from elsewhere.
- Support each item with a quotation copied word for word from that advisory.
  Application code checks it against the advisory, and an item whose quotation
  is not there is thrown out.
- Reply with one JSON object and nothing else.
"""

USER_TEMPLATE = """\
{advisory}

Reply with one JSON object of exactly this shape:

{schema}
"""


@dataclass(frozen=True)
class ExplanationPrompt:
    """One question to the explainer about one finding, and exactly what it was shown.

    `advisory_shown` is the redacted text, which is what each quotation is
    checked against; `metrics` are the disputed metrics, the only ones an item
    may be about.
    """

    metrics: tuple[str, ...]
    system: str
    user: str
    advisory_shown: str
    withheld: tuple[str, ...]
    version: str

    @property
    def subject(self) -> str:
        """Name what this prompt asks for, as a refusal of it says it."""
        return SUBJECT


def build_explanation_prompt(
    advisory_text: str, published: Mapping[str, Mapping[str, str]]
) -> ExplanationPrompt:
    """Build the prompt asking why the sources differ, from each source's disputed values."""
    refuse_no_disagreement(published)
    advisory = redact(advisory_text)
    metrics = tuple(published)
    return ExplanationPrompt(
        metrics=metrics,
        system=SYSTEM_TEMPLATE.format(disagreement=disagreement_lines(published)),
        user=USER_TEMPLATE.format(advisory=advisory.text.strip(), schema=reply_schema(metrics)),
        advisory_shown=advisory.text,
        withheld=advisory.removed,
        version=EXPLANATION_PROMPT_VERSION,
    )


def disagreement_lines(published: Mapping[str, Mapping[str, str]]) -> str:
    """Say, per disputed metric, what each source gave and what each value given means."""
    return "\n\n".join(metric_lines(metric, by_source) for metric, by_source in published.items())


def metric_lines(metric: str, by_source: Mapping[str, str]) -> str:
    """Give one metric's line of sources and values, then the meaning of each value named."""
    given = ", ".join(f"{source} {value}" for source, value in sorted(by_source.items()))
    meanings = definition_of(metric).value_meanings
    named = [f"  {one} = {meanings[one]}" for one in sorted(set(by_source.values()))]
    return "\n".join([f"{metric} ({metric_name(metric)}): {given}", *named])


def reply_schema(metrics: tuple[str, ...]) -> str:
    """Show the reply's shape: one item per disputed metric, each with its three fields."""
    item = {
        METRIC_FIELD: f"one of {', '.join(metrics)}",
        WHY_FIELD: "what in the advisory could lead readers to different values",
        QUOTATION_FIELD: "a quotation copied word for word from the advisory",
    }
    return json.dumps({ITEMS_FIELD: [item]}, indent=SCHEMA_INDENT)


def refuse_no_disagreement(published: Mapping[str, Mapping[str, str]]) -> None:
    """Refuse a prompt with no disputed metric, or a metric the sources do not disagree on."""
    if not published:
        raise ValueError("There is no disputed metric to explain")
    for metric, by_source in published.items():
        refuse_agreed_metric(metric, by_source)


def refuse_agreed_metric(metric: str, by_source: Mapping[str, str]) -> None:
    """Refuse a metric whose sources give one value, or a value the metric does not have."""
    values = set(by_source.values())
    if len(values) < FEWEST_VALUES:
        raise ValueError(f"The sources agree on {metric}, so there is nothing to explain")
    refuse_illegal_values(metric, values)


def refuse_illegal_values(metric: str, values: set[str]) -> None:
    """Refuse a value no source could have published for this metric."""
    for value in sorted(values):
        refuse_illegal_pair(metric, value)
