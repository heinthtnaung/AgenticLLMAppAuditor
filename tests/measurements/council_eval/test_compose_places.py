"""Guards on where a replayed member ran: where its pass's header says, not this machine."""

from itertools import chain

import pytest

import eval_samples as samples
from council_eval.collect import ask_item
from council_eval.compose import replay_roster
from council_eval.pass_provenance import REMOTE_HOST_FIELD
from council_eval.replies import Replies

REMOTE_HOST = "192.0.2.15"
BOTH = (samples.MODEL, samples.OTHER_MODEL)


def pass_of(model: str) -> dict:
    """Take one model's pass over the sample item, keyed as a replies file keys it."""
    records = ask_item(samples.item(), model, samples.FakeServer())
    return {(samples.KEY, model, one.metric): one for one in records}


def passes(elsewhere: tuple[str, ...] = (), host: object = REMOTE_HOST) -> Replies:
    """Take a pass of each model, heading the ones named elsewhere with a remote host."""
    calls = {}
    for model in BOTH:
        calls.update(pass_of(model))
    headers = tuple(headed(model, model in elsewhere, host) for model in BOTH)
    return Replies(headers=headers, calls=calls)


def headed(model: str, elsewhere: bool, host: object) -> dict:
    """Give a pass's header, naming the remote host only where it ran elsewhere."""
    header = samples.header(model)
    return {**header, REMOTE_HOST_FIELD: host} if elsewhere else header


def places_said(replies: Replies, models: tuple[str, ...] = BOTH) -> dict[str, bool]:
    """Replay a roster, and give per model whether its record says it ran on this machine."""
    (outcome,) = replay_roster((samples.item(),), models, replies)
    everyone = chain.from_iterable(ruling.said for ruling in outcome.rulings)
    return {said.member.model: said.member.ran_local for said in everyone}


def rulings_of(outcome) -> list[tuple]:
    """Give each ruling's metric, value and outcome, and nothing of where its members ran."""
    return [(one.metric, one.value, one.outcome) for one in outcome.rulings]


def test_a_member_whose_pass_ran_on_a_server_elsewhere_replays_as_run_there():
    said = places_said(passes(elsewhere=(samples.MODEL,)))
    assert said == {samples.MODEL: False, samples.OTHER_MODEL: True}


def test_a_pass_taken_here_replays_as_local_wherever_this_machine_s_settings_point(remote_server):
    assert places_said(passes()) == {samples.MODEL: True, samples.OTHER_MODEL: True}


def test_where_a_member_ran_changes_nothing_but_where_its_record_says_it_ran():
    (here,) = replay_roster((samples.item(),), BOTH, passes())
    (there,) = replay_roster((samples.item(),), BOTH, passes(elsewhere=BOTH))
    assert rulings_of(here) == rulings_of(there)


@pytest.mark.parametrize("host", ["", None, 15])
def test_a_pass_naming_no_usable_remote_host_is_refused(host):
    with pytest.raises(ValueError, match="names its remote host as"):
        places_said(passes(elsewhere=(samples.MODEL,), host=host))


def test_a_model_no_pass_names_is_refused_rather_than_placed():
    with pytest.raises(ValueError, match="no pass names absent:1b"):
        places_said(passes(), models=("absent:1b",))
