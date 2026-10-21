"""Guards on the approve-mode command line: what `--approve` takes, and what it refuses.

The other mode records a decision on a report already written rather than auditing one,
so it takes no repository and none of the audit's flags. The audit-mode guards are in
`test_arguments`.
"""

from pathlib import Path

import pytest

from cli.arguments import (
    APPROVE_NEEDS_ANSWERS,
    APPROVE_TAKES_NO_COUNCIL,
    APPROVE_TAKES_NO_DEBUG,
    APPROVE_TAKES_NO_FORMAT,
    APPROVE_WITH_REPOSITORY,
    NO_REPOSITORY,
    REPLACE_APPROVAL_NEEDS_APPROVE,
    parse_arguments,
)
from cli.main import COULD_NOT_RUN

APPROVE = ["--approve", "reports/x.json", "--answers", "a.json"]


def test_approve_names_a_report_and_takes_no_repository():
    # The other mode: record a decision on a report already written, not audit one.
    options = parse_arguments(APPROVE)
    assert options.approve == Path("reports/x.json")
    assert options.answers == Path("a.json")
    assert options.repository is None


def test_an_ordinary_run_names_no_report_to_approve():
    assert parse_arguments(["repo"]).approve is None
    assert parse_arguments(["repo"]).replace_approval is False


def test_replace_approval_is_read_beside_approve():
    assert parse_arguments([*APPROVE, "--replace-approval"]).replace_approval is True


def test_approve_without_answers_is_refused(capsys):
    # The decision is read from the answers file, so there is nothing to record without one.
    with pytest.raises(SystemExit) as leaving:
        parse_arguments(["--approve", "reports/x.json"])
    assert leaving.value.code == COULD_NOT_RUN
    assert APPROVE_NEEDS_ANSWERS in capsys.readouterr().err


def test_approve_beside_a_repository_is_refused(capsys):
    with pytest.raises(SystemExit):
        parse_arguments(["repo", *APPROVE])
    assert APPROVE_WITH_REPOSITORY in capsys.readouterr().err


def test_approve_beside_a_format_is_refused(capsys):
    # It rewrites all three reports, so a format would choose nothing.
    with pytest.raises(SystemExit):
        parse_arguments([*APPROVE, "--format", "json"])
    assert APPROVE_TAKES_NO_FORMAT in capsys.readouterr().err


def test_approve_beside_a_council_is_refused(capsys):
    with pytest.raises(SystemExit):
        parse_arguments([*APPROVE, "--council-member", "small"])
    assert APPROVE_TAKES_NO_COUNCIL in capsys.readouterr().err


def test_approve_beside_all_findings_is_refused(capsys):
    # --council-all-findings runs no council here either, so it is refused by the same rule.
    with pytest.raises(SystemExit):
        parse_arguments([*APPROVE, "--council-all-findings"])
    assert APPROVE_TAKES_NO_COUNCIL in capsys.readouterr().err


def test_approve_beside_debug_is_refused(capsys):
    # Approving makes no model call, so there is no per-call log for --debug to print.
    with pytest.raises(SystemExit):
        parse_arguments([*APPROVE, "--debug"])
    assert APPROVE_TAKES_NO_DEBUG in capsys.readouterr().err


def test_replace_approval_without_approve_is_refused(capsys):
    with pytest.raises(SystemExit):
        parse_arguments(["repo", "--replace-approval"])
    assert REPLACE_APPROVAL_NEEDS_APPROVE in capsys.readouterr().err


def test_replace_approval_alone_names_its_own_fault_not_the_missing_repository(capsys):
    # With neither a repository nor --approve, --replace-approval still names itself first.
    with pytest.raises(SystemExit):
        parse_arguments(["--replace-approval"])
    assert REPLACE_APPROVAL_NEEDS_APPROVE in capsys.readouterr().err


def test_no_repository_and_no_approve_names_both_ways_to_run(capsys):
    with pytest.raises(SystemExit):
        parse_arguments([])
    assert NO_REPOSITORY in capsys.readouterr().err
