"""Guards on the escalation model: read as every setting is, one local model, and unset is none."""

from pathlib import Path

import pytest

from council import settings
from council.env_file import SettingsError
from council.escalation_setting import escalation_model, load_escalation_model

ABSENT = Path("/absent.env")
SECRET = "sk-not-to-be-read"
EXAMPLE = Path(settings.__file__).resolve().parents[2] / ".env.example"


def env_file(tmp_path: Path, *lines: str) -> Path:
    """Write a settings file of the lines given, as an operator would."""
    path = tmp_path / ".env"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_model_is_read_from_the_file(tmp_path):
    written = env_file(tmp_path, f"OPENROUTER_API_KEY={SECRET}", "AUDITOR_ESCALATION_MODEL=big:27b")
    assert load_escalation_model({}, written) == "big:27b"


def test_the_environment_wins_over_the_file_and_empty_there_switches_it_off(tmp_path):
    written = env_file(tmp_path, "AUDITOR_ESCALATION_MODEL=big:27b")
    assert load_escalation_model({"AUDITOR_ESCALATION_MODEL": "other:70b"}, written) == "other:70b"
    assert load_escalation_model({"AUDITOR_ESCALATION_MODEL": ""}, written) is None


EMPTY = [(), ("AUDITOR_ESCALATION_MODEL=",), ("AUDITOR_ESCALATION_MODEL= ",)]


@pytest.mark.parametrize("lines", EMPTY)
def test_unset_or_empty_is_no_escalation_and_never_a_default_model(tmp_path, lines):
    assert load_escalation_model({}, env_file(tmp_path, *lines)) is None


def test_a_file_that_is_not_there_is_no_escalation():
    assert load_escalation_model({}, ABSENT) is None


@pytest.mark.parametrize("value", ["big:27b,other:70b", "big 27b", "big:27b\tother"])
def test_a_value_naming_more_than_one_model_is_refused_naming_where_it_came_from(value):
    with pytest.raises(SettingsError, match=r"names one model") as refused:
        load_escalation_model({"AUDITOR_ESCALATION_MODEL": value}, ABSENT)
    assert "the environment" in str(refused.value)


def test_a_misspelt_setting_beside_it_is_refused():
    with pytest.raises(SettingsError, match="the environment sets AUDITOR_ESCALATE"):
        load_escalation_model({"AUDITOR_ESCALATE": "big:27b"}, ABSENT)


def test_the_committed_example_names_no_escalation_model():
    assert load_escalation_model({}, EXAMPLE) is None


def test_no_test_escalates_whatever_the_operator_s_file_says():
    # `tests/conftest.py` points the settings at a file that is not there.
    assert escalation_model() is None
