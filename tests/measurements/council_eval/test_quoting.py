"""Guards on what members quoted: whose quotation settled alone, and which quoted the prompt."""

import eval_samples  # noqa: F401  (puts the evaluation package on the path)
from council.definitions import definition_of
from council.ruling import Basis
from council_eval.quoting import prompt_quoted_by_member, sole_by_member, unverified_by_member
from report.council_record import (
    CouncilWithoutVector,
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)

QWEN = MemberIdentity("qwen", "ollama", "qwen", "qwen", ran_local=True, prompt_version="v")
LLAMA = MemberIdentity("llama", "ollama", "llama", "llama", ran_local=True, prompt_version="v")
# Word for word from the prompt's definition of a UI value.
PROMPT_TEXT = definition_of("UI").value_meanings["R"]


def quoted(who: MemberIdentity, evidence: str, verified: bool) -> MemberSaid:
    """Build a member's answer with a quotation."""
    return MemberSaid(who, SaidKind.ANSWERED, "R", evidence, "high", verified=verified)


def record(*rulings: MetricRuling) -> tuple[CouncilWithoutVector]:
    """Wrap rulings in one item's record."""
    return (CouncilWithoutVector(advisory_id="CVE-1", single_assessor=False, rulings=rulings),)


def test_a_value_settled_on_one_quotation_is_counted_to_the_member_that_offered_it():
    guessed = MemberSaid(LLAMA, SaidKind.GUESSED, "N")
    alone = (quoted(QWEN, "text", True), guessed)
    sole = MetricRuling("UI", Outcome.SETTLED, alone, value="R", basis=Basis.SOLE.value)
    agreed = MetricRuling("S", Outcome.SETTLED, (quoted(QWEN, "t", True),), "U", Basis.AGREED.value)
    assert sole_by_member(record(sole, agreed)) == {"qwen": 1}


def test_a_quotation_of_the_prompt_s_definition_is_counted_among_the_unverified():
    offered = (quoted(LLAMA, PROMPT_TEXT, False), quoted(QWEN, "not in the advisory", False))
    outcomes = record(MetricRuling("UI", Outcome.UNRESOLVED, offered))
    assert unverified_by_member(outcomes) == {"llama": 1, "qwen": 1}
    assert prompt_quoted_by_member(outcomes) == {("llama", "UI"): 1}


def test_a_quotation_that_verified_is_not_counted_as_quoted_prompt_however_it_reads():
    outcomes = record(MetricRuling("UI", Outcome.SETTLED, (quoted(LLAMA, PROMPT_TEXT, True),), "R"))
    assert prompt_quoted_by_member(outcomes) == {}


def test_part_of_a_definition_folded_as_the_check_folds_it_is_the_prompt():
    part = "  " + PROMPT_TEXT.split(",")[0].replace(" ", "\n", 1)
    outcomes = record(MetricRuling("UI", Outcome.UNRESOLVED, (quoted(LLAMA, part, False),)))
    assert prompt_quoted_by_member(outcomes) == {("llama", "UI"): 1}
