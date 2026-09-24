"""Guards on carrying what a council did through to the record, rather than discarding it."""

import json

import pytest

from cli.council_detail import rulings_of
from cli.council_run import FALLBACKS, build_roster
from council.prompt import build_prompt
from council.runner import assess
from report.council_record import Outcome, SaidKind
from cli_samples import ADVISORY, LEGAL, QUOTATION

# `ADVISORY.details` first, so `QUOTATION` is verbatim in it.
TEXT = f"{ADVISORY.details} Exploiting it requires a specially crafted payload."
OTHER_QUOTE = "requires a specially crafted payload"


# Twin of `council_runs.replying`, which `pytest tests/cli` run alone cannot import.
def replying(**by_member):
    """A client giving each member its own answer, defaulting to a quoted legal one."""
    def said(member, prompt):
        """Answer one prompt from the member's table, or with a quoted legal value."""
        table = by_member.get(member.name, {})
        if prompt.metric in table:
            return json.dumps(table[prompt.metric])
        return json.dumps(
            {"value": LEGAL[prompt.metric], "evidence": QUOTATION, "confidence": "high"}
        )

    return {"ollama": said}


def ruled(clients, members=("qwen2.5:7b", "gemma4:latest")):
    """Run a council and convert what it did into the record's own terms."""
    roster = build_roster(members)
    run = assess(TEXT, roster, FALLBACKS, clients)
    return {one.metric: one for one in rulings_of(run, build_prompt("AV", TEXT).advisory_shown)}


def by_name(ruling):
    """Index one metric's rows by the member that said them."""
    return {one.member.name: one for one in ruling.said}


def test_every_metric_the_council_ruled_on_reaches_the_record():
    assert len(ruled(replying())) == 8


def test_every_member_that_spoke_reaches_the_record():
    assert len(ruled(replying())["AV"].said) == 2


def test_a_members_identity_travels_with_what_it_said():
    # A roster's agreement means nothing without knowing whether its members
    # share a lineage, so the family is on every row.
    who = ruled(replying())["AV"].said[0].member
    assert (who.name, who.family, who.provider) == ("qwen2.5:7b", "qwen2.5", "ollama")
    assert who.ran_local
    assert who.prompt_version


def test_an_answer_carries_its_value_evidence_and_confidence():
    said = ruled(replying())["AV"].said[0]
    assert said.kind is SaidKind.ANSWERED
    assert (said.value, said.evidence, said.confidence) == ("N", QUOTATION, "high")


def test_whether_a_quotation_checked_out_travels_with_it():
    # It is what decided the metric, so a reader should not have to re-derive it.
    invented = {"AV": {"value": "L", "evidence": "not in the text", "confidence": "low"}}
    said = by_name(ruled(replying(**{"gemma4:latest": invented}))["AV"])
    assert said["qwen2.5:7b"].verified
    assert not said["gemma4:latest"].verified


def test_a_member_that_declined_is_recorded_as_declining():
    declining = {"UI": {"value": "NO_EVIDENCE", "evidence": ""}}
    said = by_name(ruled(replying(**{"qwen2.5:7b": declining}))["UI"])
    assert said["qwen2.5:7b"].kind is SaidKind.DECLINED
    assert said["qwen2.5:7b"].value == ""


def test_a_member_that_guessed_is_recorded_as_guessing_and_keeps_its_value():
    guessing = {"UI": {"value": "R", "evidence": "", "confidence": "low"}}
    said = by_name(ruled(replying(**{"qwen2.5:7b": guessing}))["UI"])
    assert said["qwen2.5:7b"].kind is SaidKind.GUESSED
    assert said["qwen2.5:7b"].value == "R"


def test_a_member_whose_reply_could_not_be_read_is_recorded_as_failing():
    broken = {"AV": {"value": "NONSENSE", "evidence": QUOTATION, "confidence": "high"}}
    said = by_name(ruled(replying(**{"qwen2.5:7b": broken}))["AV"])
    assert said["qwen2.5:7b"].kind is SaidKind.FAILED
    assert said["qwen2.5:7b"].reason
    # Named exactly as it is when it answers: the call that failed is the one
    # an auditor most needs to trace to a model.
    assert said["qwen2.5:7b"].member == by_name(ruled(replying())["AV"])["qwen2.5:7b"].member


def test_the_chairmans_reasoning_is_recorded_beside_what_it_ruled_on():
    settled = ruled(replying())["AV"]
    assert settled.outcome is Outcome.SETTLED
    assert (settled.value, settled.confidence) == ("N", "high")
    assert settled.basis


@pytest.mark.parametrize(
    ("clients", "outcome"),
    [
        (replying(**{"gemma4:latest": {"AC": {"value": "H", "evidence": OTHER_QUOTE,
                                              "confidence": "high"}}}), Outcome.CONTESTED),
        (replying(**{"qwen2.5:7b": {"AC": {"value": "NO_EVIDENCE", "evidence": ""}},
                     "gemma4:latest": {"AC": {"value": "NO_EVIDENCE", "evidence": ""}}}),
         Outcome.UNRESOLVED),
    ],
    ids=["contested", "unresolved"],
)
def test_a_metric_the_chairman_could_not_settle_says_which_way_it_failed(clients, outcome):
    assert ruled(clients)["AC"].outcome is outcome
