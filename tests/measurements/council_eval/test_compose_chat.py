"""Guards on rebuilding a roster from pasted passes: hosted members, the replies as pasted."""

from itertools import chain

import pytest

import chat_samples
import eval_samples as samples
from council.prompt import PROMPT_VERSION
from council_eval.chat_replay import PastedReplayClient
from council_eval.collect import ask_item
from council_eval.compose import item_client, pass_models, pass_roster, replay_roster, rosters
from council_eval.replies import Replies
from council_eval.variants import CHAT


def local_pass() -> Replies:
    """Take one local pass of the sample model over the sample item, as `collect` takes it."""
    records = ask_item(samples.item(), samples.MODEL, samples.FakeServer())
    calls = {(samples.KEY, samples.MODEL, one.metric): one for one in records}
    return Replies(headers=(samples.header(),), calls=calls)


def test_a_pasted_pass_is_replayed_with_hosted_members_answering_from_its_replies():
    pasted = chat_samples.fixture_pass()
    roster = pass_roster((chat_samples.FIXTURE_MODEL,), CHAT, pasted)
    assert [(one.provider, one.runs_local) for one in roster.members] == [("chat", False)]
    assert isinstance(item_client(samples.KEY, pasted, CHAT), PastedReplayClient)
    (outcome,) = replay_roster((samples.item(),), (chat_samples.FIXTURE_MODEL,), pasted)
    ui = next(ruling for ruling in outcome.rulings if ruling.metric == "UI")
    assert (ui.value, ui.said[0].member.ran_local) == ("N", False)


def test_a_pasted_record_names_the_product_s_prompt_version_on_its_members():
    # A known gap, asserted so that closing it turns this red. As for a variant,
    # the product's runner names each member by the prompt it built; that the
    # chat prompt was asked is carried by the pass's header and each call's digest.
    (outcome,) = replay_roster(
        (samples.item(),), (chat_samples.FIXTURE_MODEL,), chat_samples.fixture_pass()
    )
    everyone = chain.from_iterable(ruling.said for ruling in outcome.rulings)
    assert {said.member.prompt_version for said in everyone} == {PROMPT_VERSION}


def test_a_pasted_pass_and_a_local_pass_cannot_form_one_roster():
    pasted, local = chat_samples.fixture_pass(), local_pass()
    mixed = Replies(headers=(*pasted.headers, local.headers[0]), calls=local.calls)
    with pytest.raises(ValueError, match="cannot form one roster"):
        replay_roster((samples.item(),), (chat_samples.FIXTURE_MODEL, samples.MODEL), mixed)


def test_two_models_pasted_the_same_prompts_form_every_roster_the_two_can():
    other = "another fixture model"
    ours, theirs = chat_samples.fixture_pass(), chat_samples.fixture_pass(model=other)
    both = Replies(headers=(*ours.headers, *theirs.headers), calls={**ours.calls, **theirs.calls})
    assert rosters(pass_models(both)) == (
        (chat_samples.FIXTURE_MODEL,), (other,), (chat_samples.FIXTURE_MODEL, other)
    )
    (outcome,) = replay_roster((samples.item(),), pass_models(both), both)
    ui = next(ruling for ruling in outcome.rulings if ruling.metric == "UI")
    assert {said.member.name for said in ui.said} == {chat_samples.FIXTURE_MODEL, other}
