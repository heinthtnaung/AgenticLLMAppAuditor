"""Council records whose members read a metric one way in order and another reversed.

As `council_runs` does: a roster, the real runner, the real chairman and the real
conversion in `cli.council_detail`, so a record here is one the product can
write. **Nothing here opens a socket**: a member answers from a table keyed by
metric, or by metric and prompt version where its two orders differ, and as
`council_runs.replying` does for anything the table leaves out.
"""

import json

from cli.council_run import assess_one, build_roster
from council.prompt import REVERSED_PROMPT_VERSION
from council_runs import (
    ADVISORY,
    BOTH,
    INVENTED,
    LONG_QUOTE,
    OTHER_QUOTE,
    answering,
    declining,
    replying,
)
from report_samples import component, finding

# On UI Qwen reads R in order and declines reversed, and Gemma declines both
# ways, so UI is unresolved. On AC Qwen reads H both ways, quoting the advisory in
# order and nothing it contains reversed, and Gemma reads L, so AC is contested.
ONE_WAY = {
    "qwen2.5:7b": {
        "UI": answering("R", OTHER_QUOTE),
        ("UI", REVERSED_PROMPT_VERSION): declining(),
        "AC": answering("H", LONG_QUOTE),
        ("AC", REVERSED_PROMPT_VERSION): answering("H", INVENTED),
    },
    "gemma4:latest": {"UI": declining(), "AC": answering("L", OTHER_QUOTE)},
}


def by_order(tables: dict):
    """Give a registry whose members answer from their tables, by order where a table says."""
    otherwise = replying()["ollama"]

    def said(member, prompt):
        """Answer one prompt from the member's table, by its order where the table names one."""
        table = tables.get(member.name, {})
        reply = table.get((prompt.metric, prompt.version), table.get(prompt.metric))
        if reply is None:
            return otherwise(member, prompt)
        return json.dumps(reply)

    return {"ollama": said}


def one_way(advisory_id: str = "CVE-ONE-WAY"):
    """Put one advisory to a real council whose members read UI and AC apart by order."""
    one = finding(component(), advisory_id=advisory_id, summary=ADVISORY, details=ADVISORY)
    return assess_one(one, build_roster(BOTH), by_order(ONE_WAY))


def rulings_of(outcome) -> dict:
    """Give a council record's rulings by metric."""
    return {one.metric: one for one in outcome.rulings}
