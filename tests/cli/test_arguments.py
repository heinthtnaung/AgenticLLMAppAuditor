"""Guards on the command line: what it takes, and what it does by default."""

import pytest

from cli.arguments import (
    BOTH_COUNCILS,
    COUNCIL_HELP,
    DESCRIPTION,
    JSON_FORMAT,
    MEMBER_HELP,
    TEXT_FORMAT,
    parse_arguments,
)
from cli.main import COULD_NOT_RUN


def test_the_repository_is_an_argument_and_nothing_is_hardcoded():
    # The repository under audit changes; fetching it is the operator's, because
    # a clone needs the proxy on and a scan needs it off.
    assert str(parse_arguments(["some/other/repo"]).repository) == "some/other/repo"


def test_a_run_reports_for_a_terminal_unless_asked_otherwise():
    assert parse_arguments(["repo"]).report_format == TEXT_FORMAT


def test_the_audit_record_is_asked_for_by_name():
    assert parse_arguments(["repo", "--format", "json"]).report_format == JSON_FORMAT


def test_a_format_nobody_renders_is_refused():
    with pytest.raises(SystemExit):
        parse_arguments(["repo", "--format", "yaml"])


def test_no_repository_is_refused():
    with pytest.raises(SystemExit):
        parse_arguments([])


def test_the_council_is_off_because_nobody_is_on_the_roster():
    # Eight metrics by n members by findings is hundreds of model calls, so a
    # run asks nobody unless the operator names someone.
    assert parse_arguments(["repo"]).council_models == ()


def test_naming_a_model_puts_it_on_the_roster():
    assert parse_arguments(["repo", "--council-member", "qwen2.5:7b"]).council_models == (
        "qwen2.5:7b",
    )


def test_naming_several_models_keeps_them_in_the_order_given():
    # The roster's order is its cost order, which is what escalation reads.
    given = ["repo", "--council-member", "small", "--council-member", "large"]
    assert parse_arguments(given).council_models == ("small", "large")


def test_the_council_is_scoped_to_the_findings_that_need_one():
    # The council reconciles sources, so by default it is not put to a finding
    # whose sources already agree.
    assert parse_arguments(["repo"]).council_all_findings is False


def test_an_operator_can_refuse_the_scoping_and_ask_about_every_finding():
    # Scoping cannot discover that two agreeing sources are both wrong, and that
    # loss is the operator's call to accept or refuse.
    given = ["repo", "--council-member", "small", "--council-all-findings"]
    assert parse_arguments(given).council_all_findings is True


def test_asking_about_every_finding_with_nobody_to_ask_is_refused(capsys):
    # Accepted, it changes nothing: the run exits as one with no council would,
    # beside a flag that says every finding was put to one.
    with pytest.raises(SystemExit) as leaving:
        parse_arguments(["repo", "--council-all-findings"])
    assert leaving.value.code == COULD_NOT_RUN
    assert "needs --council or a --council-member" in capsys.readouterr().err


def test_the_council_flag_asks_for_the_settings_members_and_names_none_itself():
    options = parse_arguments(["repo", "--council"])
    assert options.council_from_settings is True
    assert options.council_models == ()


def test_a_run_without_the_council_flag_asks_nothing_of_the_settings():
    assert parse_arguments(["repo"]).council_from_settings is False
    assert parse_arguments(["repo", "--council-member", "small"]).council_from_settings is False


def test_the_council_flag_can_ask_about_every_finding():
    assert parse_arguments(["repo", "--council", "--council-all-findings"]).council_all_findings


def test_the_council_flag_beside_a_named_member_is_refused_rather_than_one_winning(capsys):
    with pytest.raises(SystemExit) as leaving:
        parse_arguments(["repo", "--council", "--council-member", "small"])
    assert leaving.value.code == COULD_NOT_RUN
    assert BOTH_COUNCILS in capsys.readouterr().err


@pytest.mark.parametrize("said", [MEMBER_HELP, COUNCIL_HELP], ids=["council-member", "council"])
def test_the_council_flags_name_the_settings_server_and_never_call_its_models_local(said):
    # With AUDITOR_REMOTE_SERVER=yes that server is another machine.
    assert "the Ollama server AUDITOR_SERVER_URL names" in said
    assert "local" not in said


def test_the_description_is_true_for_an_offline_scan_and_a_council_that_reaches_a_server():
    # The scan is offline, but a council can reach a model server, so the help may
    # not call the whole run offline; it names the server the way the flags do.
    assert "offline" in DESCRIPTION
    assert "the Ollama server AUDITOR_SERVER_URL names" in DESCRIPTION
