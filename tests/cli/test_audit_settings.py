"""Guards on a run's settings: stated beside the council, read before the scan, never a council."""

import json
from pathlib import Path
from typing import Any

import pytest

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from cli.main import COULD_NOT_RUN, FOUND_SOMETHING
from cli_samples import DATED, run_command_line, scanners_answering
from council import settings
from council.settings import Settings, SettingsError, current_settings
from report.provenance import LocalModels

WIDER = Settings("gemma4:latest", "http://127.0.0.1:11434", 600.0, 16_384)
MEMBER = ["--council-member", "small:1b"]


def options_for(path: Path, models: tuple[str, ...] = (), from_settings: bool = False) -> Options:
    """Build the options of a run naming these council members, or none."""
    return Options(
        repository=path, report_format=TEXT_FORMAT, council_models=tuple(models),
        council_from_settings=from_settings,
    )


def asking_nobody(findings: Any, roster: Any, **_: Any) -> tuple:
    """Stand in for the council, which these tests do not need to hear from."""
    return ()


@pytest.fixture
def operator_file(tmp_path, monkeypatch):
    """Point the settings at a `.env` a test writes, and forget whatever it was read as."""
    written = tmp_path / ".env"
    monkeypatch.setattr(settings, "ENV_FILE", written)
    current_settings.cache_clear()
    yield written
    current_settings.cache_clear()


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



def test_the_council_flag_runs_the_members_the_file_names_on_the_roster_a_flag_builds(
    tmp_path, monkeypatch, operator_file
):
    # Switching models is one line of `.env`, and the members it names go through
    # the same roster, and so the same egress gate, as members named here.
    rosters = []

    def listening(findings: Any, roster: Any, **_: Any) -> tuple:
        """Keep the roster each run was put to, and ask nobody."""
        rosters.append(roster)
        return ()

    scanners_answering(monkeypatch)
    monkeypatch.setattr(audit_module, "assessments", listening)
    operator_file.write_text("AUDITOR_COUNCIL_MEMBERS=gemma4:latest,small:1b\n", encoding="utf-8")
    from_file = run_audit(options_for(tmp_path, from_settings=True), DATED)
    named = run_audit(options_for(tmp_path, ("gemma4:latest", "small:1b")), DATED)
    assert [one.name for one in rosters[0].members] == ["gemma4:latest", "small:1b"]
    assert rosters[0] == rosters[1]
    assert from_file.coverage == named.coverage


def test_the_council_flag_with_no_members_set_stops_the_run_and_says_where_it_looked(
    tmp_path, monkeypatch
):
    code, out, error = run_command_line(["--council"], monkeypatch, tmp_path)
    assert (code, out) == (COULD_NOT_RUN, "")
    assert "AUDITOR_COUNCIL_MEMBERS" in error
    assert f"neither the environment nor {settings.ENV_FILE} (no such file)" in error


def test_a_file_naming_members_starts_no_council_without_a_flag(
    tmp_path, monkeypatch, operator_file
):
    def asked(*_: Any, **__: Any) -> tuple:
        """Fail the test: no flag asked for a council."""
        raise AssertionError("a council ran that no flag asked for")

    operator_file.write_text("AUDITOR_COUNCIL_MEMBERS=gemma4:latest\n", encoding="utf-8")
    monkeypatch.setattr(audit_module, "assessments", asked)
    code, out, _ = run_command_line(["--format", "json"], monkeypatch, tmp_path)
    assert code == FOUND_SOMETHING
    assert json.loads(out)["run"]["local_models"] is None


@pytest.mark.parametrize(
    "flag", [["--council"], ["--council-member", "small:1b"]], ids=["council", "council-member"]
)
def test_the_settings_are_read_only_when_a_flag_asks_for_a_council(
    tmp_path, monkeypatch, operator_file, flag
):
    # A file broken on its first line proves each read: a run that read it is refused.
    operator_file.write_text("AUDITOR_COUNCIL_MEMBRS=gemma4:latest\n", encoding="utf-8")
    monkeypatch.setattr(audit_module, "assessments", asking_nobody)
    unasked, _, _ = run_command_line([], monkeypatch, tmp_path)
    asked, _, error = run_command_line(flag, monkeypatch, tmp_path)
    assert unasked == FOUND_SOMETHING
    assert asked == COULD_NOT_RUN
    assert "sets AUDITOR_COUNCIL_MEMBRS, which is not a setting" in error
