"""What the council did, on its tab: which advisories, and what came of each.

Which metrics a reader is shown is decided here; what one of them looks like
opened is `report.html_metric`. The sentences this shares with the terminal
rendering are `report.council_words`, so the two cannot come to word one record
differently.

**Settled and unsettled are read differently.** Agreement is most of the page and
nobody reads it, so the settled metrics are counted; the rest are disclosed one
`<details class="metric">` each. A toolbar opens or closes them all at once;
without JavaScript each still opens on its own, and with the script, printing
opens every one.

**A run one member answered says so**, and **the findings it was never put to are
named, with the reason**: a scoped run assesses only the findings whose sources do
not settle them, and a page that dropped the rest would say no council had run on
them.
"""

from collections import Counter

from report.council_beside import figure_of
from report.council_record import (
    CouncilAssessment, CouncilNotAsked, CouncilWithoutVector, MetricRuling, council_left_open,
    was_assessed,
)
from report.council_passed_over import PassedOver, grouped_by_reason
from report.council_words import (
    NOT_ASKED, NO_VECTOR, SETTLED, could_not_settle, counted, escalation_named, metrics_settled,
    uncross_checked,
)
from report.html_filters import empty_line, search_box, toggle_all_button, toolbar
from report.html_layout import empty_note, figure_chip, listing, panel_head, separated, tag, text
from report.html_metric import metric_details
from report.html_vector import vector_markup
from report.record import Report

COUNCIL_LIST = "council-list"
NO_COUNCIL = "No council ran on this audit."
NO_MATCH = "No advisory matches."
COUNCIL_LEDE = (
    "What the assessor council settled, and what it could not. Every metric the chairman "
    "could not settle opens to each member's answer, the quotation behind it in full, and "
    "whether that quotation was found in the advisory."
)


def council_panel(report: Report) -> str:
    """Give the Council tab: what it settled, what it could not, and what it was never put to."""
    if not report.council:
        return panel_head("Council", COUNCIL_LEDE) + empty_note(NO_COUNCIL)
    outcomes = [report.council[one] for one in sorted(report.council)]
    assessed = [one for one in outcomes if was_assessed(one)]
    passed = [one for one in outcomes if not was_assessed(one)]
    head = panel_head(f"Council ({len(assessed)})", COUNCIL_LEDE)
    named = escalation_lines(report)
    cards = "".join(council_card(one) for one in assessed) + empty_line(NO_MATCH)
    host = f'<div id="{COUNCIL_LIST}" class="cards">{cards}</div>'
    return head + council_toolbar() + named + host + passed_over(passed)



def council_toolbar() -> str:
    """Give the bar that opens or closes every unsettled metric and searches the cards."""
    toggle = toggle_all_button(COUNCIL_LIST, "Expand all metrics", "Collapse all metrics")
    return toolbar(COUNCIL_LIST, toggle + search_box("Search the council's advisories"))


def escalation_lines(report: Report) -> str:
    """Say which model the metrics the council left open went to, or that none was named."""
    local = report.provenance.local_models
    return "".join(tag("p", text(one), "escalation-model") for one in escalation_named(local))


def council_card(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Give one advisory as a linkable card: outcome, settled count, then open metrics."""
    unsettled = [one for one in outcome.rulings if council_left_open(one)]
    settled = [one for one in outcome.rulings if not council_left_open(one)]
    body = outcome_line(outcome) + settled_note(settled) + open_metrics(unsettled)
    ident = text(outcome.advisory_id)
    return f'<article class="card" id="council-{ident}" data-tags="">{body}</article>'


def outcome_line(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Name the advisory, say whether a vector came out of it, and mark one nothing checked."""
    named = tag("code", text(outcome.advisory_id))
    flagged = separated([named, headline(outcome), cross_check_flags(outcome)])
    return tag("p", flagged, "council-name")


def headline(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Say whether the council handed over a vector, or what stopped it."""
    if isinstance(outcome, CouncilAssessment):
        vector = vector_markup(outcome.vector)
        return separated([text(SETTLED), vector, figure_chip(figure_of(outcome))])
    return separated([text(NO_VECTOR), text(could_not_settle(outcome))])


def cross_check_flags(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Flag a result nothing in which was cross-checked, so nobody reads a council into it."""
    return "".join(tag("span", text(one), "flag") for one in uncross_checked(outcome))


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
