"""Guards on a run's settings: stated beside the council, read before the scan, never a council."""

import json
from pathlib import Path
from typing import Any

import pytest

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from cli.main import COULD_NOT_RUN
from cli_samples import DATED, run_command_line, scanners_answering
from council.settings import Settings, SettingsError
from report.provenance import LocalModels

WIDER = Settings("gemma4:latest", "http://127.0.0.1:11434", 600.0, 16_384)
MEMBER = ["--council-member", "small:1b"]


def options_for(path: Path, models: tuple[str, ...] = ()) -> Options:
    """Build the options of a run naming these council members, or none."""
    return Options(repository=path, report_format=TEXT_FORMAT, council_models=tuple(models))


def asking_nobody(findings: Any, roster: Any, **_: Any) -> tuple:
    """Stand in for the council, which these tests do not need to hear from."""
    return ()


def test_a_run_naming_no_member_asks_no_model_whatever_the_settings_name(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    monkeypatch.setattr(audit_module, "current_settings", lambda: WIDER)
    report = run_audit(options_for(tmp_path), DATED)
    assert report.provenance.local_models is None
    assert report.council == {}


def test_a_council_run_states_the_window_and_timeout_it_used_beside_the_pinning(
    tmp_path, monkeypatch
):
    scanners_answering(monkeypatch)
    monkeypatch.setattr(audit_module, "current_settings", lambda: WIDER)
    monkeypatch.setattr(audit_module, "assessments", asking_nobody)
    report = run_audit(options_for(tmp_path, ("small:1b",)), DATED)
    assert report.provenance.local_models == LocalModels(
        server="http://127.0.0.1:11434", context_tokens=16_384, timeout_seconds=600.0,
        temperature=0, seed=11, think=False,
    )


def test_a_bad_setting_stops_a_council_run_before_anything_is_scanned(tmp_path, monkeypatch):
    def refused() -> Settings:
        """Refuse as a misspelt setting is refused."""
        raise SettingsError("the environment sets AUDITOR_TIMEOUT, which is not a setting")

    def scanned(path: Path) -> None:
        """Fail the test: nothing should be scanned once a setting is refused."""
        raise AssertionError("the repository was scanned")

    scanners_answering(monkeypatch)
    monkeypatch.setattr(audit_module, "current_settings", refused)
    monkeypatch.setattr(audit_module.syft_runner, "scan_directory", scanned)
    with pytest.raises(SettingsError, match="AUDITOR_TIMEOUT"):
        run_audit(options_for(tmp_path, ("small:1b",)), DATED)


def test_the_json_record_states_the_local_models_and_null_when_none_was_asked(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(audit_module, "assessments", asking_nobody)
    _, asked, _ = run_command_line(["--format", "json", *MEMBER], monkeypatch, tmp_path)
    _, alone, _ = run_command_line(["--format", "json"], monkeypatch, tmp_path)
    assert json.loads(asked)["run"]["local_models"] == {
        "server": "http://127.0.0.1:11434", "context_tokens": 8192, "timeout_seconds": 180.0,
        "temperature": 0, "seed": 11, "think": False,
    }
    assert json.loads(alone)["run"]["local_models"] is None


def test_a_refused_setting_is_what_the_command_line_says_it_could_not_run_for(
    tmp_path, monkeypatch
):
    def refused() -> Settings:
        """Refuse as a bad timeout is refused."""
        raise SettingsError("AUDITOR_TIMEOUT_SECONDS is 'soon' (the environment)")

    monkeypatch.setattr(audit_module, "current_settings", refused)
    code, _, error = run_command_line(MEMBER, monkeypatch, tmp_path)
    assert code == COULD_NOT_RUN
    assert "AUDITOR_TIMEOUT_SECONDS is 'soon'" in error
