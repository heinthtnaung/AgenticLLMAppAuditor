"""Guards on the audit's order check: every council run asks each metric both ways round.

Why a value counts only where both orders give it is `council.order_check`.
"""

import io
from itertools import chain, product

from cli.council_run import assessments, build_roster, watching
from cli_samples import ADVISORY, LODASH, answering
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION
from cvss.metrics import METRIC_ORDER
from findings.finding import build_finding

FINDING = build_finding(LODASH, ADVISORY)


def asked_in(order_check: bool = True) -> list[tuple[str, str]]:
    """Put the sample finding to one member, and give each call's metric and prompt version."""
    asked = []
    answer = answering()["ollama"]

    def recording(member, prompt):
        """Note the call, then answer it as `answering` does."""
        asked.append((prompt.metric, prompt.version))
        return answer(member, prompt)

    roster, clients = build_roster(("small",)), {"ollama": recording}
    assessments((FINDING,), roster, clients, order_check=order_check)
    return asked


def test_every_council_run_asks_each_metric_in_order_then_reversed():
    both = (PROMPT_VERSION, REVERSED_PROMPT_VERSION)
    assert asked_in() == list(product(METRIC_ORDER, both))


def test_a_run_with_the_check_off_asks_each_metric_once_in_order():
    # Only the measurement harness turns it off, to replay passes recorded in one order.
    assert asked_in(order_check=False) == list(product(METRIC_ORDER, (PROMPT_VERSION,)))


def test_the_progress_line_tells_a_reversed_call_from_the_in_order_one():
    # Two identical lines per metric would read as a run repeating itself.
    roster, out = build_roster(("small",)), io.StringIO()
    assessments((FINDING,), roster, answering(), watching((FINDING,), roster, out))
    asked = [line.split("  ")[-2] for line in out.getvalue().splitlines()]
    assert asked[:2] == ["AV", "AV (options reversed)"]
    assert len(set(asked)) == len(asked) == 16


def test_the_total_counts_one_order_when_the_check_is_off():
    counted = watching((FINDING,), build_roster(("small",)), io.StringIO(), order_check=False)
    assert counted.calls == 8


def prompts_named(order_check: bool = True) -> set[tuple[str, str]]:
    """Give every pair of prompt versions the record names a member by."""
    roster = build_roster(("small",))
    (outcome,) = assessments((FINDING,), roster, answering(), order_check=order_check)
    everyone = chain.from_iterable(ruling.said for ruling in outcome.rulings)
    return {(said.member.prompt_version, said.member.reversed_prompt_version) for said in everyone}


def test_an_order_checked_record_names_both_prompts_each_member_saw():
    assert prompts_named() == {(PROMPT_VERSION, REVERSED_PROMPT_VERSION)}


def test_a_record_asked_in_one_order_names_no_reversed_prompt():
    assert prompts_named(order_check=False) == {(PROMPT_VERSION, "")}
