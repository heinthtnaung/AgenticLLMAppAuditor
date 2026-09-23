"""Guards on the command line: what it takes, and what it does by default."""

import pytest

from cli.arguments import JSON_FORMAT, TEXT_FORMAT, parse_arguments


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
