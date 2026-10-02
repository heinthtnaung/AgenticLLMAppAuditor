"""What the council did, on the page, led by the metrics a reader has to decide.

Eight metrics by n members for every assessed finding is more page than anyone
reads, and most of it is agreement. So the page shows the metrics the chairman
could **not** settle -- contested and unresolved -- with every member's answer,
its evidence and whether that evidence checked out, and counts the settled rest.
The audit record carries all of it; this chooses.

Contested is the case the whole project exists for. Two model families reading
one advisory and reaching different values, each with a quotation that verifies,
is not something a count can express -- and a human exercising the override the
design gives them needs to see who said what, on what evidence.

**The settled rest is counted by what settled it.** A metric where the chairman
overruled a dissenter reads nothing like one nobody argued about, and a bare
`settled` says neither. The bases come off the record, so this counts them
rather than wording them.

**And the findings it was never put to are named, with the reason.** A scoped run
assesses the findings whose sources do not settle them; a page that simply left
the rest out would say no council had run on them, which is a different and false
thing. They are grouped by reason and listed by id, so a reader can see whether
their own CVE was passed over.

What one of those metrics looks like is `report.text_metric`. The sentences this
shares with the web page are `report.council_words`.
"""

from collections import Counter
from itertools import chain

from report.council_beside import banded, figure_of
from report.council_passed_over import PassedOver, grouped_by_reason
from report.council_queries import council_left_open, was_assessed
from report.council_record import (
    CouncilAssessment,
    CouncilNotAsked,
    CouncilWithoutVector,
    MetricRuling,
)
from report.council_words import (
    NO_VECTOR,
    NOT_ASKED,
    SETTLED,
    could_not_settle,
    counted,
    escalation_named,
    metrics_settled,
    models_named,
    uncross_checked,
)
from report.record import Report
from report.text_layout import SOURCE_SEPARATOR, indented, section, wrapped
from report.text_metric import ADVISORY_DEPTH, MEMBER_DEPTH, METRIC_DEPTH, ruling_lines


def council_block(report: Report) -> str:
    """Say what the council assessed, what it could not settle, and what it was never put to."""
    if not report.council:
        return ""
    outcomes = [report.council[one] for one in sorted(report.council)]
    assessed = [one for one in outcomes if was_assessed(one)]
    entries = chain.from_iterable(advisory_lines(one) for one in assessed)
    passed = [one for one in outcomes if not was_assessed(one)]
    local = report.provenance.local_models
    said = [*escalation_named(local), *models_named(local)]
    named = [indented(ADVISORY_DEPTH, one) for one in said]
    return section(f"COUNCIL ({len(assessed)})", [*named, *entries, *passed_over_lines(passed)])


def passed_over_lines(passed: list[CouncilNotAsked]) -> list[str]:
    """Name the findings the council was not put to, grouped by the reason it was not."""
    if not passed:
        return []
    headed = indented(ADVISORY_DEPTH, f"{counted(len(passed), 'finding')} {NOT_ASKED}")
    grouped = grouped_by_reason(passed)
    return [headed, *chain.from_iterable(reason_lines(one) for one in grouped)]


def reason_lines(group: PassedOver) -> list[str]:
    """Give one reason findings were passed over, and name every finding it covers."""
    named = ", ".join(group.advisory_ids)
    return [indented(METRIC_DEPTH, group.because), *wrapped(named, MEMBER_DEPTH)]


def advisory_lines(outcome: CouncilAssessment | CouncilWithoutVector) -> list[str]:
    """Give one advisory's heading, then the metrics the chairman could not settle."""
    # An escalated metric is shown whatever came of it: the council did not settle it.
    unsettled = [one for one in outcome.rulings if council_left_open(one)]
    settled = [one for one in outcome.rulings if not council_left_open(one)]
    heading = SOURCE_SEPARATOR.join([headline(outcome), *uncross_checked(outcome)])
    return [
        indented(ADVISORY_DEPTH, f"{outcome.advisory_id}  {heading}"),
        *settled_lines(settled),
        *chain.from_iterable(ruling_lines(one) for one in unsettled),
    ]


def headline(outcome: CouncilAssessment | CouncilWithoutVector) -> str:
    """Say whether the council handed over a vector, or what stopped it."""
    if isinstance(outcome, CouncilAssessment):
        return SOURCE_SEPARATOR.join([SETTLED, outcome.vector, banded(figure_of(outcome))])
    return SOURCE_SEPARATOR.join([NO_VECTOR, could_not_settle(outcome)])


def settled_lines(settled: list[MetricRuling]) -> list[str]:
    """Count the metrics nobody needs to read, and say what the chairman settled them on."""
    if not settled:
        return []
    bases = Counter(one.basis for one in settled if one.basis)
    return [
        indented(METRIC_DEPTH, metrics_settled(len(settled))),
        *[basis_line(basis, count) for basis, count in sorted(bases.items())],
    ]


def basis_line(basis: str, count: int) -> str:
    """Say how many of the settled metrics rested on one basis, in the chairman's own words."""
    return indented(MEMBER_DEPTH, f"{count}  {basis}")
