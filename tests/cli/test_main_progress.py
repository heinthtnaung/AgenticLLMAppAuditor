"""Guards on progress: a council run says it is alive on the error stream, and never on stdout.

`cli.progress` prints each line before the call it names; these hold where the
lines go when the whole command line runs, beside a record piped from stdout.
"""

import json

from cli import audit as audit_module
from cli_samples import explaining_nothing, run_command_line


def reporting_council(
    findings, roster, clients=None, progress=None, every_finding=False, escalation=None
):
    """Stand in for a council run, saying what it is doing through the progress it was given."""
    progress.starting("CVE-2021-23337")
    progress.asking("AV", "qwen2.5:7b-instruct")
    return ()


def test_progress_is_said_on_the_error_stream_and_never_on_stdout(monkeypatch, tmp_path):
    # The whole constraint: `--format json` writes the record to stdout and it
    # has to stay pipeable, so progress and the record share a process and
    # nothing else.
    monkeypatch.setattr(audit_module, "assessments", reporting_council)
    explaining_nothing(monkeypatch)
    given = ["--council-member", "qwen2.5:7b-instruct"]
    _, out, error = run_command_line(given, monkeypatch, tmp_path)
    assert error.strip()
    assert error.strip() not in out
    assert out.startswith("Audit of")


def test_the_audit_record_stays_parseable_while_progress_is_being_said(monkeypatch, tmp_path):
    monkeypatch.setattr(audit_module, "assessments", reporting_council)
    explaining_nothing(monkeypatch)
    given = ["--council-member", "qwen2.5:7b-instruct", "--format", "json"]
    _, out, error = run_command_line(given, monkeypatch, tmp_path)
    assert error.strip()
    assert json.loads(out)["run"]["finding_count"] == 1


def test_progress_locates_the_run_by_finding_metric_and_member(monkeypatch, tmp_path):
    monkeypatch.setattr(audit_module, "assessments", reporting_council)
    explaining_nothing(monkeypatch)
    given = ["--council-member", "qwen2.5:7b-instruct"]
    _, _, error = run_command_line(given, monkeypatch, tmp_path)
    assert "CVE-2021-23337" in error
    assert "AV" in error
    assert "qwen2.5:7b-instruct" in error
