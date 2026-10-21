"""Guards on when a run asks the approved questions: after its own checks, before the scan."""

from pathlib import Path

import pytest

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from cli.interactive_answers import PROMPT_SUFFIX
from cli_samples import (
    DATED,
    NO_TO_EVERYTHING,
    REPORTS_FOLDER,
    FakeTerminal,
    feed,
    scanners_answering,
)
from council.settings import Settings, SettingsError
from scoring.library import APPROVED_QUESTIONS


def test_a_refused_setting_stops_the_run_before_any_question(tmp_path, monkeypatch):
    def refused() -> Settings:
        """Refuse as a misspelt setting is refused."""
        raise SettingsError("the environment sets AUDITOR_TIMEOUT, which is not a setting")

    monkeypatch.setattr(audit_module, "current_settings", refused)
    stdin, error = feed(NO_TO_EVERYTHING), FakeTerminal()
    options = Options(tmp_path, TEXT_FORMAT, ("small:1b",))
    with pytest.raises(SettingsError):
        run_audit(options, DATED, error, stdin, tmp_path / REPORTS_FOLDER)
    assert stdin.tell() == 0
    assert PROMPT_SUFFIX not in error.getvalue()


def test_every_question_is_answered_before_the_scan_starts(tmp_path, monkeypatch):
    stdin, error = feed(NO_TO_EVERYTHING), FakeTerminal()
    asked_before_scan = []

    def scanned(path: Path):
        """Note how many questions had been asked when the scan began."""
        asked_before_scan.append(error.getvalue().count(PROMPT_SUFFIX))
        return real_scan(path)

    scanners_answering(monkeypatch)
    real_scan = audit_module.syft_runner.scan_directory
    monkeypatch.setattr(audit_module.syft_runner, "scan_directory", scanned)
    (tmp_path / REPORTS_FOLDER).mkdir()
    run_audit(Options(tmp_path, TEXT_FORMAT, ()), DATED, error, stdin, tmp_path / REPORTS_FOLDER)
    assert asked_before_scan == [len(APPROVED_QUESTIONS)]
