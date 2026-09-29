"""Guards on the settings: environment, then `.env`, then default, and only `AUDITOR_*` read."""

from pathlib import Path

import pytest

import council.ollama
from council import settings
from council.env_file import NAMES
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


def test_a_misspelt_setting_in_the_environment_is_refused():
    with pytest.raises(SettingsError, match="the environment sets AUDITOR_TIMEOUT"):
        load_settings({"AUDITOR_TIMEOUT": "600"}, Path("/absent.env"))


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


def test_the_committed_example_holds_every_setting_at_its_default_and_nothing_else():
    example = Path(settings.__file__).resolve().parents[2] / ".env.example"
    lines = [line for line in example.read_text("utf-8").splitlines() if line and line[0] != "#"]
    assert [line.split("=")[0] for line in lines] == list(NAMES)
    assert load_settings({}, example) == DEFAULTS


def test_the_members_setting_is_known_here_and_changes_no_setting_of_the_server(tmp_path):
    # Read by `council.member_setting` only; here it is a name, and not a misspelling.
    written = env_file(tmp_path, "AUDITOR_COUNCIL_MEMBERS=a:1b,a:1b")
    assert load_settings({"AUDITOR_COUNCIL_MEMBERS": ""}, written) == DEFAULTS


def test_the_escalation_setting_is_known_here_and_changes_no_setting_of_the_server(tmp_path):
    # Read by `council.escalation_setting` only; here it is a name, and not a misspelling.
    written = env_file(tmp_path, "AUDITOR_ESCALATION_MODEL=qwen3.8:27b")
    assert load_settings({"AUDITOR_ESCALATION_MODEL": ""}, written) == DEFAULTS
