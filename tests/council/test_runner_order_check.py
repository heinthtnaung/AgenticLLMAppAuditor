"""Guards on the runner's order check: each metric asked both ways, only a stable value counting."""

import json
from itertools import chain, product

from council.answer import MemberOrderSensitive
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION
from council.roster import Roster
from council.ruling import SettledMetric, UnresolvedMetric
from council.runner import assess
from cvss.metrics import METRIC_ORDER
from council_samples import FALLBACKS, LEGAL_VALUE, OTHER_VALUE, QUOTABLE, clients_of, member

# Reversed, this member reads AV and UI the other way: the list's order decided them.
FLIPPED = {"AV", "UI"}


def answering_by_order(asked: list):
    """Answer every metric the same way in both orders but for AV and UI, noting each call."""

    def said(member_asked, prompt):
        """Answer one call, reading the order from the prompt's version."""
        asked.append((prompt.metric, prompt.version))
        flipped = prompt.version == REVERSED_PROMPT_VERSION and prompt.metric in FLIPPED
        value = OTHER_VALUE[prompt.metric] if flipped else LEGAL_VALUE[prompt.metric]
        return json.dumps({"value": value, "evidence": QUOTABLE, "confidence": "high"})

    return said


def run(order_check: bool) -> tuple:
    """Put the sample advisory to one member, and give the run and every call it made."""
    asked = []
    clients = clients_of(answering_by_order(asked))
    done = assess(QUOTABLE, Roster((member(),)), FALLBACKS, clients, order_check=order_check)
    return done, asked


def test_with_the_check_each_metric_is_asked_in_order_then_reversed():
    _, asked = run(order_check=True)
    in_order = [(metric, PROMPT_VERSION) for metric in METRIC_ORDER]
    reversed_order = [(metric, REVERSED_PROMPT_VERSION) for metric in METRIC_ORDER]
    assert asked == list(chain.from_iterable(zip(in_order, reversed_order)))


def test_without_it_each_metric_is_asked_once_in_order():
    _, asked = run(order_check=False)
    assert asked == [(metric, PROMPT_VERSION) for metric in METRIC_ORDER]


def test_a_value_the_orders_disagree_on_is_no_answer_and_one_they_share_settles():
    done, _ = run(order_check=True)
    rounds = {one.metric: one for one in done.rounds}
    (flipped,) = rounds["AV"].replies
    assert isinstance(flipped, MemberOrderSensitive)
    assert (flipped.in_order_value, flipped.reversed_value) == ("N", "L")
    assert isinstance(rounds["AV"].ruling, UnresolvedMetric)
    assert isinstance(rounds["AC"].ruling, SettledMetric)
    assert rounds["AC"].ruling.value == LEGAL_VALUE["AC"]


def test_each_call_is_announced_with_the_order_it_is_asked_in():
    announced = []
    clients = clients_of(answering_by_order([]))
    assess(QUOTABLE, Roster((member(),)), FALLBACKS, clients,
           lambda metric, name, reversed_options: announced.append((metric, reversed_options)),
           order_check=True)
    assert announced == list(product(METRIC_ORDER, (False, True)))
