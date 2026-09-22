"""Guards on the roster: the three edges, and egress failing closed."""

import pytest

from council.answer import MemberIdentity
from council.roster import (
    Member,
    Roster,
    is_single_assessor,
    members_skipped,
    members_to_ask,
)
from council_samples import hosted, member


def test_a_roster_keeps_its_members_in_the_order_they_are_asked():
    # Escalation orders the roster by cost, so the order is meaningful.
    roster = Roster((member("small"), member("large"), hosted(egress=True)))
    asked = [entry.name for entry in members_to_ask(roster)]
    assert asked == ["small", "large", "hosted-other-family"]


def test_an_empty_roster_is_a_configuration_error():
    # Not an empty council. Falling back to a published vector and calling that
    # an assessment is what the design forbids by name.
    with pytest.raises(ValueError, match="at least one member"):
        Roster(())


def test_two_members_sharing_a_name_are_refused():
    with pytest.raises(ValueError, match="small names more than one member"):
        Roster((member("small"), member("small", model="qwen3:8b")))


def test_a_hosted_member_without_egress_does_not_run():
    roster = Roster((member("small"), hosted()))
    assert [asked.name for asked in members_to_ask(roster)] == ["small"]


def test_a_hosted_member_that_does_not_run_is_reported_as_skipped():
    # A record that quietly omits a member is worse than one that says where the
    # text went, so the skip and its reason survive to the report.
    roster = Roster((member("small"), hosted()))
    skipped = members_skipped(roster)
    assert [entry.member.name for entry in skipped] == ["hosted-other-family"]
    assert "egress" in skipped[0].reason


def test_a_hosted_member_with_egress_runs():
    roster = Roster((member("small"), hosted(egress=True)))
    assert len(members_to_ask(roster)) == 2
    assert members_skipped(roster) == ()


def test_egress_is_off_by_default():
    assert not hosted().egress
    assert not hosted().may_run()


def test_a_local_member_needs_no_egress():
    assert member().may_run()


def test_a_roster_nobody_can_be_asked_from_is_refused():
    with pytest.raises(ValueError, match="can ask nobody"):
        members_to_ask(Roster((hosted("one"), hosted("two"))))


def test_one_member_is_a_single_assessor_and_not_a_council():
    assert is_single_assessor(Roster((member(),)))


def test_two_members_are_not_a_single_assessor():
    assert not is_single_assessor(Roster((member("small"), member("large"))))


def test_a_roster_left_with_one_runnable_member_is_a_single_assessor():
    # Asked rather than configured: three members of whom two are hosted without
    # egress cross-check nothing, and no reader should take council-grade
    # confidence from the one that ran.
    roster = Roster((member("small"), hosted("one"), hosted("two")))
    assert is_single_assessor(roster)


def test_an_even_roster_needs_no_rule_because_nothing_is_counted():
    roster = Roster((member("a"), member("b"), member("c"), member("d")))
    assert not is_single_assessor(roster)
    assert len(members_to_ask(roster)) == 4


@pytest.mark.parametrize("field", ["name", "provider", "model", "family"])
def test_a_member_a_record_could_not_name_is_refused(field):
    with pytest.raises(ValueError, match=f"needs {field}"):
        member(**{field: ""})


@pytest.mark.parametrize("flag", ["runs_local", "egress"])
def test_a_flag_that_is_not_a_flag_is_refused(flag):
    # Truthiness would let "no" opt a hosted member into egress.
    with pytest.raises(TypeError, match=f"must say {flag} as true or false"):
        member(**{flag: "yes"})


def test_a_member_names_itself_on_an_answer_with_the_prompt_it_was_asked_with():
    identity = member("small").identify("member-base-metric-1")
    assert isinstance(identity, MemberIdentity)
    assert identity.name == "small"
    assert identity.ran_local
    assert identity.prompt_version == "member-base-metric-1"


def test_a_hosted_member_identifies_itself_as_having_run_hosted():
    assert not hosted(egress=True).identify("member-base-metric-1").ran_local


def test_a_member_is_frozen():
    with pytest.raises(AttributeError):
        member().egress = True


def test_a_roster_is_frozen():
    with pytest.raises(AttributeError):
        Roster((member(),)).members = ()


def test_a_member_built_directly_defaults_egress_off():
    built = Member(name="m", provider="openrouter", model="x/y", family="x", runs_local=False)
    assert not built.may_run()
