"""Guards on a roster whose server is elsewhere: every member and the escalation model there."""

from cli.council_run import build_roster, escalation_member
from council.escalation import refuse_unfit_escalation
from council.providers import PROVIDER_CLIENTS


def test_every_member_named_is_recorded_as_run_elsewhere_with_egress(remote_server):
    roster = build_roster(("small", "large"))
    assert [(one.runs_local, one.egress) for one in roster.members] == [(False, True)] * 2


def test_the_escalation_model_is_on_the_members_server_and_is_not_refused(remote_server):
    big = escalation_member("big:27b")
    assert (big.provider, big.runs_local, big.egress) == ("ollama", False, True)
    refuse_unfit_escalation(big, ("small", "large"), PROVIDER_CLIENTS)
