"""Council records built by running the real chairman, not by filling in a dataclass.

`report.council_record.MetricRuling` is one flat type with every field optional,
because a projection has to hold three council rulings in one shape. The
council's own types do not: `src/council/ruling.py` puts `basis` on
`SettledMetric` **and nowhere else**, so a contested ruling carrying a basis is a
record no chairman can emit -- and a test that pins one reports coverage of a
path that never runs.

So these build the record the one way that cannot lie about its shape: a roster,
the real runner, the real chairman, and the real conversion in
`cli.council_detail`. **Nothing here opens a socket** -- a member's reply comes
from a dict, which is the seam `src/council/providers.py` exists to leave open.

Named `council_runs` and not `samples`: pytest puts each test directory on the
path and imports by basename.
"""

import json

from cli.council_detail import rulings_of
from cli.council_run import FALLBACKS, assess_one, build_roster, passed_over
from council.prompt import build_prompt
from council.ruling import Basis, PublishedFallback
from council.runner import assess
from cvss.metrics import METRIC_ORDER
from report.council_record import CouncilNotAsked, CouncilOutcome, CouncilWithoutVector, Outcome
from report_samples import TOTAL_LOSS, component, finding

ADVISORY = (
    "A remote attacker can inject commands through a template option. "
    "Exploiting it requires a specially crafted payload."
)
QUOTED = "A remote attacker can inject commands"
# The advisory's whole first sentence, verbatim, so it verifies, and a rendering
# that shortened it would no longer contain it.
LONG_QUOTE = "A remote attacker can inject commands through a template option."
OTHER_QUOTE = "requires a specially crafted payload"
# From `measurements/council_runs/gpu-full.report.txt`: at a quotation's depth on
# the page, `re-escapes` straddles the edge.
HYPHENATED_AT_THE_EDGE = (
    "During parsing it runs a legacy decoding pass over the scheme component and never "
    "re-escapes the result, and serialization writes the scheme back out verbatim, unlike "
    "the host component which is re-escaped."
)
# A sentence the advisory does not contain, so the quotation check refuses it.
INVENTED = "the maintainers have not replied to the report"
# A backslash, an apostrophe and straight double quotes, each of which an
# escaping renderer turns into text the advisory never contained. Verbatim in
# `AWKWARD_ADVISORY`, so a member quoting it offers a quotation that verifies.
AWKWARD_QUOTE = r"""the pattern /^\s*"(.*)"\s*$/ backtracks on "don't fix" paths like C:\temp"""
AWKWARD_ADVISORY = f"{ADVISORY} Here {AWKWARD_QUOTE}."

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
# On AC both members quote the advisory and read it apart, so it is contested; on
# S both find nothing to quote, so it is unresolved. One record, both open states.
OPEN_TWO_WAYS = {
    "qwen2.5:7b": {
        "AC": {"value": "H", "evidence": LONG_QUOTE, "confidence": "high"},
        "S": {"value": "NO_EVIDENCE", "evidence": ""},
    },
    "gemma4:latest": {
        "AC": {"value": "L", "evidence": OTHER_QUOTE, "confidence": "high"},
        "S": {"value": "NO_EVIDENCE", "evidence": ""},
    },
}
# On AV one member quotes text the advisory does not carry and the other quotes
# nothing at all, so no evidence settles it and only an offered fallback fills it.
NOTHING_VERIFIED = {
    "qwen2.5:7b": {"AV": {"value": "N", "evidence": INVENTED, "confidence": "high"}},
    "gemma4:latest": {"AV": {"value": "A", "evidence": "", "confidence": "high"}},
}
# On UI one member finds nothing to quote and the other answers quoting nothing,
# so one open metric carries a decline beside a guess.
DECLINED_AND_GUESSED = {
    "qwen2.5:7b": {"UI": {"value": "NO_EVIDENCE", "evidence": ""}},
    "gemma4:latest": {"UI": {"value": "R", "evidence": "", "confidence": "high"}},
}
# On AV one member declines and the other replies with a value AV does not have,
# so its call is recorded as failed, with the reason its reply was refused.
UNPARSEABLE = {
    "qwen2.5:7b": {"AV": {"value": "NO_EVIDENCE", "evidence": ""}},
    "gemma4:latest": {"AV": {"value": "NONSENSE", "evidence": QUOTED, "confidence": "high"}},
}


def replying(**by_member):
    """Give a provider registry whose members answer from a table, quoting the advisory."""
    def said(member, prompt):
        """Answer one prompt from the table, or with a legal value and a real quotation."""
        table = by_member.get(member.name, {})
        if prompt.metric in table:
            return json.dumps(table[prompt.metric])
        return json.dumps(
            {"value": LEGAL[prompt.metric], "evidence": QUOTED, "confidence": "high"}
        )

    return {"ollama": said}


def council_ran(
    advisory_id: str = "CVE-2019-14234", models=BOTH, details: str = ADVISORY, **by_member
):
    """Put one advisory to a real council by the path the command line takes."""
    one = finding(component(), advisory_id=advisory_id, summary=details, details=details)
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


def fell_back(advisory_id: str = "CVE-FALLBACK") -> CouncilWithoutVector:
    """Give a real record of AV left unresolved and filled from ghsa's published value."""
    offered = {**FALLBACKS, "AV": published("N")}
    return outcome_from(rulings_with_fallbacks(offered, **NOTHING_VERIFIED), advisory_id)


def council_states() -> tuple[CouncilOutcome, ...]:
    """Give one record of every state a finding's council entry can be in."""
    # Each renderer's test renders these, and `test_council_record.py` holds their
    # types equal to `CouncilOutcome`: a state added to the union fails there until
    # it is added here, and from here every renderer is shown it.
    return (
        council_ran(advisory_id="CVE-SETTLED"),
        council_ran(advisory_id="CVE-OPEN", **DISSENTING),
        *passed_over_entirely(),
    )


def passed_over_entirely() -> tuple[CouncilNotAsked, ...]:
    """Give the record of a run whose members were named and whose every finding was passed over."""
    both_agree = {"ghsa": TOTAL_LOSS, "nvd": TOTAL_LOSS}
    agreeing = finding(component(), advisory_id="CVE-PASSED", vectors=both_agree)
    return passed_over((agreeing,), every_finding=False)
