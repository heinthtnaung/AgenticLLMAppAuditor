"""Council records built by running the real chairman, not by filling in a dataclass.

`report.council_record.MetricRuling` is one flat type with every field optional,
because a projection has to hold three council rulings in one shape. The
council's own types do not: `src/council/ruling.py` puts `basis` on
`SettledMetric` **and nowhere else**, so a contested ruling carrying a basis is a
record no chairman can emit -- and a test that pins one reports coverage of a
path that never runs. This project has shipped that defect twice.

So these build the record the one way that cannot lie about its shape: a roster,
the real runner, the real chairman, and the real conversion in
`cli.council_detail`. **Nothing here opens a socket** -- a member's reply comes
from a dict, which is the seam `src/council/providers.py` exists to leave open.

Named `council_runs` and not `samples`: pytest puts each test directory on the
path and imports by basename.
"""

import json

from cli.council_detail import rulings_of
from cli.council_run import assess_one, build_roster
from council.prompt import build_prompt
from council.ruling import Basis, PublishedFallback
from council.runner import assess
from cvss.metrics import METRIC_ORDER
from report.council_record import CouncilWithoutVector, Outcome
from report_samples import component, finding

ADVISORY = (
    "A remote attacker can inject commands through a template option. "
    "Exploiting it requires a specially crafted payload."
)
QUOTED = "A remote attacker can inject commands"
# Longer than the sixty characters a terminal used to cut a quotation at, and
# verbatim, so a test that it survives whole is testing a quotation that verifies.
LONG_QUOTE = "A remote attacker can inject commands through a template option."
OTHER_QUOTE = "requires a specially crafted payload"
# A sentence the advisory does not contain, so the quotation check refuses it.
INVENTED = "the maintainers have not replied to the report"

AGREED = Basis.AGREED.value
EVIDENCE = Basis.EVIDENCE.value

BOTH = ("qwen2.5:7b", "gemma4:latest")
ALONE = ("qwen2.5:7b",)
# A model with no tag, so `build_roster` guesses a family that is its name again.
UNTAGGED = ("gemma4",)

# One legal value per metric, so an unremarkable member answers a whole vector.
LEGAL = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}

# Two members reading one advisory apart. On AV both quote it and reach different
# values, so nothing settles it and it comes out contested; on AC one quotes text
# the advisory does not contain, so the verified quotation settles it and the
# chairman records the EVIDENCE basis. One run, both of the two bases, one
# contested metric -- which is every shape the page has to render at once.
DISSENTING = {
    "qwen2.5:7b": {"AV": {"value": "N", "evidence": LONG_QUOTE, "confidence": "high"}},
    "gemma4:latest": {
        "AV": {"value": "A", "evidence": OTHER_QUOTE, "confidence": "high"},
        "AC": {"value": "H", "evidence": INVENTED, "confidence": "high"},
    },
}


def replying(**by_member):
    """Give a provider registry whose members answer from a table, quoting the advisory."""
    def said(member, prompt):
        table = by_member.get(member.name, {})
        if prompt.metric in table:
            return json.dumps(table[prompt.metric])
        return json.dumps(
            {"value": LEGAL[prompt.metric], "evidence": QUOTED, "confidence": "high"}
        )

    return {"ollama": said}


def council_ran(advisory_id: str = "CVE-2019-14234", models=BOTH, **by_member):
    """Put one advisory to a real council by the path the command line takes."""
    one = finding(component(), advisory_id=advisory_id, summary=ADVISORY, details=ADVISORY)
    return assess_one(one, build_roster(models), replying(**by_member))


def rulings_with_fallbacks(fallbacks: dict, models=BOTH, **by_member):
    """Give the chairman's rulings where a caller did offer published fallbacks.

    `cli.council_run` offers none, because choosing a source is the precedence
    `docs/SCORING_MODEL.md` refuses to set -- but the chairman takes whatever a
    caller hands it, so a record naming a fallback source is one it can produce.
    """
    run = assess(ADVISORY, build_roster(models), fallbacks, replying(**by_member))
    return rulings_of(run, build_prompt(METRIC_ORDER[0], ADVISORY).advisory_shown)


def published(value: str, source: str = "ghsa") -> PublishedFallback:
    """Offer one published value for a metric no member's quotation could settle."""
    return PublishedFallback(value=value, source=source)


def answering(value: str, evidence: str = QUOTED, confidence: str = "high") -> dict:
    """Give one member's reply to one metric."""
    return {"value": value, "evidence": evidence, "confidence": confidence}


def declining() -> dict:
    """Give the reply of a member that found nothing in the advisory to quote."""
    return {"value": "NO_EVIDENCE", "evidence": ""}


def outcome_from(rulings, advisory_id: str = "CVE-2019-14234", single_assessor: bool = False):
    """Wrap real rulings the way `cli.council_run` wraps the ones it could not settle."""
    unresolved = tuple(one.metric for one in rulings if one.outcome is Outcome.UNRESOLVED)
    contested = tuple(one.metric for one in rulings if one.outcome is Outcome.CONTESTED)
    return CouncilWithoutVector(advisory_id, single_assessor, unresolved, contested, rulings)
