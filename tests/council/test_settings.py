"""Guards on the settings: environment, then `.env`, then default, and only `AUDITOR_*` read."""

from pathlib import Path

import pytest

import council.ollama
from council import settings
from council.ollama import LocalModel, build_request
from council.prompt import build_prompt
from council.settings import Settings, SettingsError, current_settings, load_settings

DEFAULTS = Settings("qwen2.5:7b-instruct", "http://127.0.0.1:11434", 180.0, 8192)
SECRET = "sk-not-to-be-read"


def env_file(tmp_path: Path, *lines: str) -> Path:
    """Write a settings file of the lines given, as an operator would."""
    path = tmp_path / ".env"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_with_nothing_set_the_defaults_are_used(tmp_path):
    assert load_settings({}, tmp_path / "absent.env") == DEFAULTS


def test_the_environment_wins_over_the_file_and_the_file_over_the_default(tmp_path):
    written = env_file(tmp_path, "AUDITOR_MODEL=gemma4:latest", "AUDITOR_TIMEOUT_SECONDS=600")
    chosen = load_settings({"AUDITOR_TIMEOUT_SECONDS": "900"}, written)
    assert (chosen.model, chosen.timeout_seconds) == ("gemma4:latest", 900.0)
    assert chosen.context_tokens == 8192


def test_only_auditor_lines_are_read_and_no_other_line_is_parsed_or_quoted(tmp_path):
    written = env_file(
        tmp_path, "NO_PROXY=localhost", f"OPENROUTER_API_KEY={SECRET}", "a line that is no setting",
        "# a comment", "AUDITOR_CONTEXT_TOKENS=nonsense",
    )
    with pytest.raises(SettingsError) as refused:
        load_settings({}, written)
    assert "AUDITOR_CONTEXT_TOKENS is 'nonsense'" in str(refused.value)
    assert SECRET not in str(refused.value) and "NO_PROXY" not in str(refused.value)


def test_a_file_s_other_keys_are_passed_over_when_its_settings_are_good(tmp_path):
    written = env_file(tmp_path, f"OPENROUTER_API_KEY={SECRET}", "AUDITOR_MODEL=llama3.2:latest")
    assert load_settings({}, written).model == "llama3.2:latest"


def test_the_old_server_form_with_its_endpoint_is_read_as_the_server_alone(tmp_path):
    written = env_file(tmp_path, "AUDITOR_SERVER_URL=http://localhost:11434/api/generate")
    assert load_settings({}, written).server == "http://localhost:11434"


@pytest.mark.parametrize(
    "value, said",
    [
        ("http://ollama.example.com:11434", "is not this machine"),
        ("http://127.0.0.1:11434/v1/chat", "give the server's address alone"),
        ("127.0.0.1:11434", "give the server's address alone"),
    ],
)
def test_a_server_not_this_machine_s_ollama_is_refused_naming_the_file(tmp_path, value, said):
    written = env_file(tmp_path, f"AUDITOR_SERVER_URL={value}")
    with pytest.raises(SettingsError, match=f"{said}") as refused:
        load_settings({}, written)
    assert f"{written} line 1" in str(refused.value)


@pytest.mark.parametrize("value", ["abc", "0", "-5", "inf", "nan", ""])
def test_a_timeout_that_is_not_a_positive_number_is_refused_naming_where_it_came_from(value):
    with pytest.raises(SettingsError, match=r"AUDITOR_TIMEOUT_SECONDS .*\(the environment\)"):
        load_settings({"AUDITOR_TIMEOUT_SECONDS": value}, Path("/absent.env"))


@pytest.mark.parametrize("value", ["8192.5", "0", "a lot"])
def test_a_window_that_is_not_a_positive_whole_number_is_refused(value):
    with pytest.raises(SettingsError, match="must be a positive whole number"):
        load_settings({"AUDITOR_CONTEXT_TOKENS": value}, Path("/absent.env"))


def test_a_misspelt_setting_in_the_file_is_refused_naming_it_and_not_its_value(tmp_path):
    written = env_file(tmp_path, "AUDITOR_MODLE=gemma4:latest")
    said = r"line 1 sets AUDITOR_MODLE, which is not a setting"
    with pytest.raises(SettingsError, match=said) as refused:
        load_settings({}, written)
    assert "gemma4" not in str(refused.value)


def test_a_misspelt_setting_in_the_environment_is_refused():
    with pytest.raises(SettingsError, match="the environment sets AUDITOR_TIMEOUT"):
        load_settings({"AUDITOR_TIMEOUT": "600"}, Path("/absent.env"))


def test_a_setting_written_twice_or_without_its_value_is_refused(tmp_path):
    twice = env_file(tmp_path, "AUDITOR_MODEL=a:1b", "AUDITOR_MODEL=b:2b")
    with pytest.raises(SettingsError, match="set twice: at .* line 1, and at .* line 2"):
        load_settings({}, twice)
    with pytest.raises(SettingsError, match="AUDITOR_MODEL has no '='"):
        load_settings({}, env_file(tmp_path, "AUDITOR_MODEL gemma4:latest"))


def test_quotes_and_an_export_are_read_as_an_operator_writes_them(tmp_path):
    quoted = ('export AUDITOR_MODEL="gemma4:latest"', "AUDITOR_CONTEXT_TOKENS='16384'")
    written = env_file(tmp_path, *quoted)
    chosen = load_settings({}, written)
    assert (chosen.model, chosen.context_tokens) == ("gemma4:latest", 16384)


def test_no_test_reads_the_operator_s_settings_file():
    assert settings.ENV_FILE != Path(settings.__file__).resolve().parents[2] / ".env"
    assert not settings.ENV_FILE.exists()
    assert current_settings() == DEFAULTS


def test_a_member_named_no_further_takes_its_model_window_and_server_from_the_settings(monkeypatch):
    chosen = Settings("gemma4:latest", "http://localhost:11434", 600.0, 4096)
    monkeypatch.setattr(council.ollama, "current_settings", lambda: chosen)
    pinning = LocalModel()
    assert (pinning.model, pinning.context_tokens) == ("gemma4:latest", 4096)
    assert pinning.host == chosen.server
    # The guard scales with the window: this prompt fits 8,192 and not 4,096.
    with pytest.raises(ValueError, match="is pinned to"):
        build_request(build_prompt("AV", "word " * 2600), pinning)


def test_the_committed_example_holds_the_four_settings_at_their_defaults_and_nothing_else():
    example = Path(settings.__file__).resolve().parents[2] / ".env.example"
    lines = [line for line in example.read_text("utf-8").splitlines() if line and line[0] != "#"]
    assert [line.split("=")[0] for line in lines] == list(settings.DEFAULTS)
    assert load_settings({}, example) == DEFAULTS
