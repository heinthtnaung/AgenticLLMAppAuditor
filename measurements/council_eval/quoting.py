"""Two things a report's wording does not show: who a lone settlement rests on, and quoted prompt.

**Whose quotation settled a value alone.** The `SOLE` basis says one member's
quotation settled a metric with nobody else quoting; it does not say whose. On
a roster where one member guesses a lot, that is the difference between a
council and one assessor wearing its name.

**A quotation of the prompt's own definitions.** The failure `council.prompt`
names -- a member offering the definition it was given as the advisory's words.
The quotation check refuses it, so it is counted among the quotations that did
not verify; this says how many of those were the prompt. "Of the prompt" means
the quotation, folded as the check folds it, is contained in the metric's
description or in one of its value meanings.
"""

from collections import Counter
from itertools import chain
from typing import Iterable

from council.definitions import definition_of
from council.evidence import normalise
from council.ruling import Basis
from report.council_record import CouncilOutcome, MemberSaid, MetricRuling, Outcome, SaidKind


def rulings_of(outcomes: Iterable[CouncilOutcome]) -> list[MetricRuling]:
    """Give every metric ruling of every item."""
    return list(chain.from_iterable(outcome.rulings for outcome in outcomes))


def quoted(ruling: MetricRuling) -> list[MemberSaid]:
    """Give the members that offered a quotation on one ruling, verified or not."""
    return [said for said in ruling.said if said.kind is SaidKind.ANSWERED]


def sole_by_member(outcomes: Iterable[CouncilOutcome]) -> Counter:
    """Count the values settled on one quotation alone, by the member that offered it."""
    sole = [one for one in rulings_of(outcomes) if is_sole(one)]
    return Counter(quoted(one)[0].member.name for one in sole)


def is_sole(ruling: MetricRuling) -> bool:
    """Say whether a ruling settled on one member's quotation, nobody else quoting."""
    return ruling.outcome is Outcome.SETTLED and ruling.basis == Basis.SOLE.value


def unverified_by_member(outcomes: Iterable[CouncilOutcome]) -> Counter:
    """Count each member's quotations the advisory does not contain."""
    return Counter(said.member.name for _, said in unverified(outcomes))


def prompt_quoted_by_member(outcomes: Iterable[CouncilOutcome]) -> Counter:
    """Count each member's unverified quotations that are the prompt's definitions, by metric."""
    offered = unverified(outcomes)
    found = [(metric, said) for metric, said in offered if quotes_definition(metric, said)]
    return Counter((said.member.name, metric) for metric, said in found)


def unverified(outcomes: Iterable[CouncilOutcome]) -> list[tuple[str, MemberSaid]]:
    """Give every quotation that did not verify, with the metric it was offered for."""
    return list(chain.from_iterable(unverified_in(one) for one in rulings_of(outcomes)))


def unverified_in(ruling: MetricRuling) -> list[tuple[str, MemberSaid]]:
    """Give one ruling's quotations that did not verify, with its metric."""
    return [(ruling.metric, said) for said in quoted(ruling) if not said.verified]


def quotes_definition(metric: str, said: MemberSaid) -> bool:
    """Say whether a quotation is text the prompt gave as the metric's definition."""
    folded = normalise(said.evidence)
    definition = definition_of(metric)
    texts = [definition.measures, *definition.value_meanings.values()]
    return bool(folded) and any(folded in normalise(text) for text in texts)
