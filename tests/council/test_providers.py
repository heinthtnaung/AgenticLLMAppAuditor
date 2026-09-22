"""Guards on provider reach: who has a client, who does not, and what the record says."""

from types import SimpleNamespace

import pytest

from council.prompt import build_prompt
from council.providers import (
    PROVIDER_CLIENTS,
    ask_local_model,
    no_client_reason,
    reachable_members,
    unreachable_members,
)
from council.roster import Roster
from council_samples import hosted, member

ANY_CLIENT = {"ollama": lambda asked, prompt: "{}"}


def test_the_shipped_clients_reach_ollama_and_nothing_else():
    # A hosted member has no client and none is stubbed: a stub would answer,
    # and its answer would be recorded as an assessment.
    assert set(PROVIDER_CLIENTS) == {"ollama"}


def test_the_local_client_pins_the_members_own_model(monkeypatch):
    # Without this the member's model is silently ignored and every local member
    # runs on the default, which no test of the dispatch would notice.
    seen = {}

    def remember(prompt, pinning):
        seen["model"] = pinning.model
        return SimpleNamespace(text="it said this")

    monkeypatch.setattr("council.providers.ask", remember)
    said = ask_local_model(member(model="qwen3:8b"), build_prompt("AV", "Some advisory text."))
    assert seen["model"] == "qwen3:8b"
    assert said == "it said this"


def test_members_with_a_client_keep_their_roster_order():
    members = (member("cheap"), hosted("remote", egress=True), member("dear"))
    assert [reached.name for reached in reachable_members(members, ANY_CLIENT)] == ["cheap", "dear"]


def test_a_roster_no_client_can_reach_is_refused():
    # Answering entirely from published fallbacks would look like an assessment.
    with pytest.raises(ValueError, match="nobody can be asked"):
        reachable_members((hosted("one", egress=True),), ANY_CLIENT)


def test_a_member_stopped_by_egress_is_named_with_its_reason():
    skipped = unreachable_members(Roster((member("local"), hosted("remote"))), ANY_CLIENT)
    assert [entry.member.name for entry in skipped] == ["remote"]
    assert "egress" in skipped[0].reason


def test_a_member_with_no_client_is_named_with_its_reason():
    roster = Roster((member("local"), hosted("remote", egress=True)))
    skipped = unreachable_members(roster, ANY_CLIENT)
    assert [entry.member.name for entry in skipped] == ["remote"]
    assert skipped[0].reason == "no client for provider 'openrouter' exists on this machine"


def test_the_two_reasons_stay_apart_in_one_list():
    # "Refused by policy" and "not configured" are different facts about a run,
    # and a reader has to be able to tell which happened to which member.
    roster = Roster((member("local"), hosted("policy"), hosted("missing", egress=True)))
    reasons = {entry.member.name: entry.reason for entry in unreachable_members(roster, ANY_CLIENT)}
    assert "egress" in reasons["policy"]
    assert "no client" in reasons["missing"]


def test_nobody_is_reported_skipped_when_everybody_can_be_asked():
    assert unreachable_members(Roster((member("a"), member("b"))), ANY_CLIENT) == ()


def test_the_reason_names_the_provider_that_has_no_client():
    assert "openrouter" in no_client_reason(hosted())
