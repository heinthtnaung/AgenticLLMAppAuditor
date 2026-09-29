"""Guards on the members `--council` runs: read as every setting is, and never a default model."""

from pathlib import Path

import pytest

from council import settings
from council.member_setting import council_members, load_council_members
from council.settings import SettingsError

ABSENT = Path("/absent.env")
SECRET = "sk-not-to-be-read"
EXAMPLE = Path(settings.__file__).resolve().parents[2] / ".env.example"


def env_file(tmp_path: Path, *lines: str) -> Path:
    """Write a settings file of the lines given, as an operator would."""
    path = tmp_path / ".env"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_members_are_read_from_the_file_in_the_order_written(tmp_path):
    written = env_file(tmp_path, "AUDITOR_COUNCIL_MEMBERS=gemma4:latest, qwen2.5:7b-instruct")
    assert load_council_members({}, written) == ("gemma4:latest", "qwen2.5:7b-instruct")


def test_the_environment_wins_over_the_file(tmp_path):
    written = env_file(tmp_path, "AUDITOR_COUNCIL_MEMBERS=gemma4:latest")
    chosen = load_council_members({"AUDITOR_COUNCIL_MEMBERS": "llama3.2:latest"}, written)
    assert chosen == ("llama3.2:latest",)


def test_quotes_an_export_and_other_keys_are_read_as_an_operator_writes_them(tmp_path):
    lines = (f"OPENROUTER_API_KEY={SECRET}", 'export AUDITOR_COUNCIL_MEMBERS="a:1b,b:2b"')
    assert load_council_members({}, env_file(tmp_path, *lines)) == ("a:1b", "b:2b")


def test_unset_is_refused_naming_the_setting_and_everywhere_it_looked():
    # No default model: a council nobody named is not one the operator asked for.
    with pytest.raises(SettingsError) as refused:
        load_council_members({}, ABSENT)
    said = str(refused.value)
    assert "AUDITOR_COUNCIL_MEMBERS" in said
    assert f"neither the environment nor {ABSENT} (no such file)" in said


def test_unset_in_a_file_that_exists_names_the_file_without_calling_it_absent(tmp_path):
    written = env_file(tmp_path, "AUDITOR_MODEL=gemma4:latest")
    with pytest.raises(SettingsError, match=f"nor {written}; name the models"):
        load_council_members({}, written)


@pytest.mark.parametrize("value", ["", "  ", '""'])
def test_an_empty_setting_is_refused_naming_where_it_came_from(tmp_path, value):
    written = env_file(tmp_path, f"AUDITOR_COUNCIL_MEMBERS={value}")
    with pytest.raises(SettingsError, match=rf"is empty \({written} line 1\)"):
        load_council_members({}, written)


def test_an_empty_setting_in_the_environment_is_refused_naming_the_environment():
    with pytest.raises(SettingsError, match=r"is empty \(the environment\)"):
        load_council_members({"AUDITOR_COUNCIL_MEMBERS": ""}, ABSENT)


@pytest.mark.parametrize("value", ["a:1b,,b:2b", "a:1b,", ",a:1b", "a:1b, ,b:2b"])
def test_an_empty_entry_is_refused_naming_where_it_came_from(value):
    with pytest.raises(SettingsError, match=r"\(the environment\), which has an empty entry"):
        load_council_members({"AUDITOR_COUNCIL_MEMBERS": value}, ABSENT)


def test_a_member_named_twice_is_refused_naming_it_and_the_file(tmp_path):
    written = env_file(tmp_path, "AUDITOR_COUNCIL_MEMBERS=a:1b,b:2b, a:1b")
    with pytest.raises(SettingsError, match=rf"names a:1b more than once \({written} line 1\)"):
        load_council_members({}, written)


def test_a_misspelt_key_is_refused_naming_it_and_not_its_value(tmp_path):
    written = env_file(tmp_path, "AUDITOR_COUNCIL_MEMBER=gemma4:latest")
    with pytest.raises(SettingsError, match="line 1 sets AUDITOR_COUNCIL_MEMBER, which is not"):
        load_council_members({}, written)
    with pytest.raises(SettingsError, match="the environment sets AUDITOR_COUNCIL"):
        load_council_members({"AUDITOR_COUNCIL": "gemma4:latest"}, ABSENT)


def test_the_committed_example_names_no_member_so_copying_it_runs_no_council():
    with pytest.raises(SettingsError, match=f"is empty \\({EXAMPLE} line"):
        load_council_members({}, EXAMPLE)


def test_no_test_reads_the_operator_s_members():
    # `tests/conftest.py` points the settings at a file that does not exist.
    with pytest.raises(SettingsError, match=f"nor {settings.ENV_FILE} \\(no such file\\)"):
        council_members()
