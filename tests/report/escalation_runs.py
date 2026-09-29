"""Council records with an escalation in them, built by running the real council and escalation.

As `council_runs` does for the council: a roster, the real runner, the real
chairman, the real escalation and the real conversion in `cli.council_detail`,
so a record here is one the product can write. **Nothing here opens a socket**:
the council answers from `council_runs`' tables, and the escalation model from
a table of its own, by metric and, where the two orders are to differ, by order.
"""

import json

from cli.council_run import assess_one, build_roster, escalation_member
from council.prompt import REVERSED_PROMPT_VERSION
from council.transport import ModelUnavailable
from council_runs import (
    ADVISORY,
    BOTH,
    DISSENTING,
    INVENTED,
    OPEN_TWO_WAYS,
    OTHER_QUOTE,
    QUOTED,
    answering,
    declining,
    replying,
)
from report_samples import component, finding

BIG = "big:27b"

# The council leaves AC contested (H against L) and S unresolved (both declined);
# the escalation model reads AC as L and S as U, each quoting the advisory.
SETTLING = {"AC": answering("L", OTHER_QUOTE), "S": answering("U", QUOTED)}
# On AV the council is split N against A; the model reads L, quoting the advisory.
ANOTHER_VALUE = {"AV": answering("L", QUOTED)}
# The model reads AC as L in order and H reversed, and quotes S from nowhere.
UNSTABLE_AND_INVENTED = {
    ("AC", REVERSED_PROMPT_VERSION): answering("H", QUOTED),
    "AC": answering("L", QUOTED),
    "S": answering("U", INVENTED),
}
TIMED_OUT = ModelUnavailable("timed out after 180 s")


def escalating(big_says: dict, members: dict):
    """Give a registry whose council answers from its tables, and the escalation model from one."""
    council = replying(**members)["ollama"]

    def said(member, prompt):
        """Answer one prompt: a council member from its table, the model by metric and order."""
        if member.name != BIG:
            return council(member, prompt)
        reply = big_says.get((prompt.metric, prompt.version), big_says.get(prompt.metric))
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply or declining())

    return {"ollama": said}


def escalated(big_says: dict, members: dict = OPEN_TWO_WAYS, advisory_id: str = "CVE-ESCALATED"):
    """Put one advisory to a real council and escalate what it left open to the model."""
    one = finding(component(), advisory_id=advisory_id, summary=ADVISORY, details=ADVISORY)
    clients = escalating(big_says, members)
    return assess_one(one, build_roster(BOTH), clients, escalation=escalation_member(BIG))


def by_metric(outcome) -> dict:
    """Give a council record's rulings by metric."""
    return {one.metric: one for one in outcome.rulings}


def split_on_av(big_says: dict):
    """Escalate a council split N against A on AV to a model answering from `big_says`."""
    return escalated(big_says, members=DISSENTING)
