"""Guards on reading `.env`: only `AUDITOR_*` lines, only setting names, and no value quoted."""

from pathlib import Path

import pytest

from council.env_file import (
    ESCALATION_MODEL,
    FROM_ENVIRONMENT,
    NAMES,
    SettingsError,
    auditor_lines,
    refuse_unknown_names,
)

SECRET = "sk-not-to-be-read"


def env_file(tmp_path: Path, *lines: str) -> Path:
    """Write a settings file of the lines given, as an operator would."""
    path = tmp_path / ".env"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_only_auditor_lines_are_read_and_no_other_line_is_parsed_or_kept(tmp_path):
    written = env_file(
        tmp_path, "NO_PROXY=localhost", f"OPENROUTER_API_KEY={SECRET}", "a line that is no setting",
        "# a comment", "AUDITOR_CONTEXT_TOKENS=nonsense",
    )
    read = auditor_lines(written)
    assert read == {"AUDITOR_CONTEXT_TOKENS": ("nonsense", f"{written} line 5")}
    assert SECRET not in str(read)


def test_a_file_that_is_not_there_holds_no_setting():
    assert auditor_lines(Path("/absent.env")) == {}


def test_a_misspelt_setting_in_the_file_is_refused_naming_it_and_not_its_value(tmp_path):
    written = env_file(tmp_path, "AUDITOR_MODLE=gemma4:latest")
    said = r"line 1 sets AUDITOR_MODLE, which is not a setting"
    with pytest.raises(SettingsError, match=said) as refused:
        auditor_lines(written)
    assert "gemma4" not in str(refused.value)


def test_a_setting_written_twice_or_without_its_value_is_refused(tmp_path):
    twice = env_file(tmp_path, "AUDITOR_MODEL=a:1b", "AUDITOR_MODEL=b:2b")
    with pytest.raises(SettingsError, match="set twice: at .* line 1, and at .* line 2"):
        auditor_lines(twice)
    with pytest.raises(SettingsError, match="AUDITOR_MODEL has no '='"):
        auditor_lines(env_file(tmp_path, "AUDITOR_MODEL gemma4:latest"))


def test_quotes_and_an_export_are_read_as_an_operator_writes_them(tmp_path):
    quoted = ('export AUDITOR_MODEL="gemma4:latest"', "AUDITOR_CONTEXT_TOKENS='16384'")
    read = auditor_lines(env_file(tmp_path, *quoted))
    assert {name: value for name, (value, _) in read.items()} == {
        "AUDITOR_MODEL": "gemma4:latest", "AUDITOR_CONTEXT_TOKENS": "16384",
    }


def test_the_escalation_model_is_a_setting_and_a_misspelling_of_it_is_not():
    assert ESCALATION_MODEL in NAMES
    refuse_unknown_names({ESCALATION_MODEL: "qwen3.8:27b"}, FROM_ENVIRONMENT)
    with pytest.raises(SettingsError, match="the settings are .*AUDITOR_ESCALATION_MODEL"):
        refuse_unknown_names({"AUDITOR_ESCALATE_MODEL": "qwen3.8:27b"}, FROM_ENVIRONMENT)
