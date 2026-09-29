"""The product's order check rules as the evaluation's did, on the passes it was measured on.

The product (`council.order_check`, asked through `council.runner.assess`) and
the evaluation (`council_eval.order_checked`) are two implementations of one
rule. Put to Qwen's and Llama's saved passes in both orders, they must reach the
same outcome and value on every metric of every finding, and the product's
reversed requests must be the ones the evaluation recorded, byte for byte.
"""

from pathlib import Path

import eval_samples  # noqa: F401  (puts the evaluation package on the path)
from cli.council_run import FALLBACKS, advisory_text, build_roster
from council.ollama import LocalModel, build_request, read_answer
from council.prompt import REVERSED_PROMPT_VERSION, MemberPrompt
from council.providers import AskMember
from council.roster import Member
from council.ruling import ContestedMetric, SettledMetric
from council.runner import assess
from council_eval.dataset import Item, read_dataset
from council_eval.order_checked import order_checked_roster
from council_eval.recording import request_digest
from council_eval.replies import read_replies
from report.council_record import CouncilOutcome

RUNS = Path(__file__).resolve().parents[3] / "measurements" / "council_eval_runs"
DATASET = RUNS / "pilot-vulnscout" / "vulnscout.dataset.json"
FORWARD = (
    RUNS / "pilot-vulnscout" / "qwen2.5-7b-instruct.run1.replies.jsonl",
    RUNS / "pilot-vulnscout" / "llama3.2-latest.run2.replies.jsonl",
)
REVERSED = (
    RUNS / "reversed-vulnscout" / "qwen2.5-7b-instruct.run1.replies.jsonl",
    RUNS / "reversed-vulnscout" / "llama3.2-latest.run1.replies.jsonl",
)
MODELS = ("qwen2.5:7b-instruct", "llama3.2:latest")
WINDOW = 8192


def answering_from(key: str, forward: dict, reversed_: dict) -> AskMember:
    """Build a client answering the product's prompts from the passes, by the order each is in."""

    def client(member: Member, prompt: MemberPrompt) -> str:
        """Answer from the call recorded for this prompt, refusing one asked otherwise."""
        calls = reversed_ if prompt.version == REVERSED_PROMPT_VERSION else forward
        recorded = calls[(key, member.model, prompt.metric)]
        pinning = LocalModel(model=member.model, context_tokens=WINDOW)
        assert recorded.request_sha256 == request_digest(build_request(prompt, pinning))
        return read_answer(recorded.envelope, prompt, pinning).text

    return client


def product_outcomes(item: Item, forward: dict, reversed_: dict) -> dict[str, tuple[str, str]]:
    """Rule on one finding with the product's order check, by metric: outcome and value."""
    client = answering_from(item.key, forward, reversed_)
    run = assess(advisory_text(item.finding), build_roster(MODELS), FALLBACKS,
                 {"ollama": client}, order_check=True)
    return {one.metric: outcome_of(one.ruling) for one in run.rounds}


def outcome_of(ruling: object) -> tuple[str, str]:
    """Name a ruling's outcome and settled value, as the record names them."""
    if isinstance(ruling, SettledMetric):
        return "settled", ruling.value
    return ("contested" if isinstance(ruling, ContestedMetric) else "unresolved"), ""


def measured_outcomes(outcome: CouncilOutcome) -> dict[str, tuple[str, str]]:
    """Give what the evaluation's order check ruled on one finding, by metric: outcome and value."""
    return {one.metric: (one.outcome.value, one.value) for one in outcome.rulings}


def test_the_product_rules_as_the_measured_rule_did_on_every_metric_of_every_finding():
    items = read_dataset(DATASET)
    forward, reversed_ = read_replies(FORWARD), read_replies(REVERSED)
    measured, _ = order_checked_roster(items, MODELS, forward, reversed_)
    for item, outcome in zip(items, measured):
        expected = measured_outcomes(outcome)
        assert product_outcomes(item, forward.calls, reversed_.calls) == expected, item.key
