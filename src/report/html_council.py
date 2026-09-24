"""What the council did, on the page: which advisories, and what came of each.

Which metrics a reader is shown is decided here; what one of them looks like
opened is `report.html_metric`. The sentences this shares with the terminal
rendering are `report.council_words`, so the two cannot come to word one record
differently.

**Settled and unsettled are read differently.** Agreement is most of the page and
nobody reads it, so the settled metrics are counted; the rest are disclosed one
`<details>` each, which costs no JavaScript.

**The settled rest is counted by what settled it.** Only a settled ruling carries
a basis -- `src/council/ruling.py` puts it on `SettledMetric` and nowhere else --
so a contested metric's disclosure has no why to show and the counting line is
where the chairman's own words belong. A metric where it overruled a dissenter
reads nothing like one nobody argued about, and a bare `settled` says neither.

**A run one member answered says so.** `docs/COUNCIL.md` marks it single-assessor
so no reader takes council-grade confidence from one model, and a page that
dropped the mark leaves a council of one looking like a council of two.

**And the findings it was never put to are named, with the reason.** A scoped run
assesses the findings whose sources do not settle them; a page that simply left
the rest out would say no council had run on them, which is a different and false
thing.
"""

from collections import Counter

from report.council_record import (
    CouncilAssessment,
    CouncilNotAsked,
    CouncilWithoutVector,
    MetricRuling,
    Outcome,
    PassedOver,
    grouped_by_reason,
    was_assessed,
)
from report.council_words import (
    NOT_ASKED, NO_VECTOR, SETTLED, SINGLE_ASSESSOR, could_not_settle, counted, metrics_settled,
)
from report.html_layout import listing, section, separated, tag, text
from report.html_metric import metric_details
from report.record import Report

COUNCIL_LEDE = (
    "What the assessor council settled, and what it could not. Every metric the chairman "
    "could not settle opens to each member's answer, the quotation behind it in full, and "
    "whether that quotation was found in the advisory."
)

def council_section(report: Report) -> str:
    """Say what the council assessed, what it could not settle, and what it was never put to."""
    # Four states a reader has to tell apart: no council ran, which is this
    # section being absent and the absence named under `Not assessed`; a council
    # settled a vector; a council ran and could not; and a finding it was never
    # put to, which is the one a scoped run would otherwise drop in silence.
    if not report.council:
        return ""
    outcomes = [report.council[one] for one in sorted(report.council)]
    assessed = [one for one in outcomes if was_assessed(one)]
    body = listing([council_entry(one) for one in assessed], "council") if assessed else ""
    passed = [one for one in outcomes if not was_assessed(one)]
    return section(f"Council ({len(assessed)})", COUNCIL_LEDE, body + passed_over(passed))


def passed_over(passed: list[CouncilNotAsked]) -> str:
    """Name the findings the council was not put to, grouped by the reason it was not."""
    if not passed:
        return ""
    headed = tag("p", text(f"{counted(len(passed), 'finding')} {NOT_ASKED}"), "not-asked")
    rows = [reason_row(one) for one in grouped_by_reason(passed)]
    return headed + listing(rows, "not-asked")


def reason_row(group: PassedOver) -> str:
    """Give one reason findings were passed over, and name every finding it covers."""
    named = tag("code", text(", ".join(group.advisory_ids)))
    return tag("span", text(group.because), "absence-why") + named


def council_entry(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Give one advisory: what the council made of it, then the metrics it left open."""
    unsettled = [one for one in outcome.rulings if one.outcome is not Outcome.SETTLED]
    settled = [one for one in outcome.rulings if one.outcome is Outcome.SETTLED]
    return outcome_line(outcome) + settled_note(settled) + open_metrics(unsettled)


def outcome_line(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Name the advisory, say whether a vector came out of it, and mark a run of one."""
    named = tag("code", text(outcome.advisory_id))
    return tag("p", separated([named, headline(outcome), single_assessor(outcome)]), "council-name")


def headline(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Say whether the council handed over a vector, or what stopped it."""
    if isinstance(outcome, CouncilAssessment):
        return separated([text(SETTLED), tag("code", text(outcome.vector))])
    return separated([text(NO_VECTOR), text(could_not_settle(outcome))])


def single_assessor(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Mark a run only one member answered, so nobody reads a council into it."""
    if not outcome.single_assessor:
        return ""
    return tag("span", text(SINGLE_ASSESSOR), "flag")


def settled_note(settled: list[MetricRuling]) -> str:
    """Count the metrics nobody needs to open, and say what the chairman settled them on."""
    if not settled:
        return ""
    return tag("p", text(metrics_settled(len(settled))), "council-settled") + basis_list(settled)


def basis_list(settled: list[MetricRuling]) -> str:
    """Count the settled metrics by what settled them, in the chairman's own words."""
    bases = Counter(one.basis for one in settled if one.basis)
    if not bases:
        return ""
    return listing([basis_row(one, count) for one, count in sorted(bases.items())], "bases")


def basis_row(basis: str, count: int) -> str:
    """Say how many of the settled metrics rested on one basis."""
    return tag("span", text(count), "basis-count") + text(basis)


def open_metrics(unsettled: list[MetricRuling]) -> str:
    """Open one disclosure per metric the chairman could not settle."""
    return "".join(metric_details(one) for one in unsettled)
