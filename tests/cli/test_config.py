"""Settings resolution: os.environ beats the .env file, which beats the built-in defaults.

Every test passes an explicit tmp_path env file, so none of them depends on whether a
real .env exists at the repo root, and none leaves an environment variable behind.
Parsing of the .env text itself is covered in test_config_parsing.py.
"""

from pathlib import Path

import pytest
import config
from conftest import REPO_ROOT

# One setting is enough to prove the resolution order; the rest share the same code path.
SETTING = "AUDITOR_MODEL"



@pytest.fixture(autouse=True)
def clear_auditor_env(monkeypatch) -> None:
    """Unset every known setting so a stray environment variable cannot mask a bug."""
    for name in config.DEFAULTS:
        monkeypatch.delenv(name, raising=False)


def write_env_file(directory: Path, text: str) -> Path:
    """Write a .env file in the given directory and return its path."""
    path = directory / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def missing_env_file(directory: Path) -> Path:
    """Return a path to a .env that deliberately does not exist."""
    return directory / ".env"


def test_defaults_hold_the_three_known_settings() -> None:
    """DEFAULTS names exactly the settings the auditor understands."""
    assert sorted(config.DEFAULTS) == [
        "AUDITOR_MODEL",
        "AUDITOR_SERVER_URL",
        "AUDITOR_TIMEOUT_SECONDS",
    ]


def test_default_values_are_all_strings() -> None:
    """Defaults are stored as text, because that is what an environment gives back."""
    assert all(isinstance(value, str) for value in config.DEFAULTS.values())


def test_env_file_constant_points_at_the_repo_root_dotenv() -> None:
    """ENV_FILE is the .env at the repo root, not a path relative to the caller's cwd."""
    assert config.ENV_FILE == REPO_ROOT / ".env"


def test_default_is_used_when_nothing_sets_the_value(tmp_path: Path) -> None:
    """With no environment variable and no .env, get returns the built-in default."""
    assert config.get(SETTING, env_file=missing_env_file(tmp_path)) == config.DEFAULTS[SETTING]


def test_env_file_value_is_used_when_only_the_file_sets_it(tmp_path: Path) -> None:
    """A value in .env overrides the built-in default."""
    env_file = write_env_file(tmp_path, f"{SETTING}=from-file\n")
    assert config.get(SETTING, env_file=env_file) == "from-file"


def test_environment_variable_beats_the_env_file(tmp_path: Path, monkeypatch) -> None:
    """When both set the same key, the real environment variable wins."""
    env_file = write_env_file(tmp_path, f"{SETTING}=from-file\n")
    monkeypatch.setenv(SETTING, "from-environment")
    assert config.get(SETTING, env_file=env_file) == "from-environment"


def test_get_reports_a_malformed_env_file(tmp_path: Path) -> None:
    """get does not swallow a broken .env; the parse error reaches the caller."""
    env_file = write_env_file(tmp_path, "this line has no equals sign\n")
    with pytest.raises(ValueError, match="expected KEY=value"):
        config.get(SETTING, env_file=env_file)


def test_get_rejects_an_unknown_setting_name(tmp_path: Path) -> None:
    """Asking for a setting the auditor does not define is a programming error."""
    with pytest.raises(KeyError, match="unknown setting"):
        config.get("AUDITOR_NOT_A_SETTING", env_file=missing_env_file(tmp_path))


def test_get_int_returns_a_whole_number(tmp_path: Path) -> None:
    """A numeric setting comes back as an int, not the text form."""
    env_file = write_env_file(tmp_path, "AUDITOR_TIMEOUT_SECONDS=45\n")
    assert config.get_int("AUDITOR_TIMEOUT_SECONDS", env_file=env_file) == 45


def test_get_int_reads_the_default_timeout(tmp_path: Path) -> None:
    """With nothing configured, the default timeout parses as an int."""
    value = config.get_int("AUDITOR_TIMEOUT_SECONDS", env_file=missing_env_file(tmp_path))
    assert value == int(config.DEFAULTS["AUDITOR_TIMEOUT_SECONDS"])


def test_get_int_accepts_a_negative_number(tmp_path: Path) -> None:
    """A leading '-' is accepted; get_int checks the format, not the sensible range."""
    env_file = write_env_file(tmp_path, "AUDITOR_TIMEOUT_SECONDS=-5\n")
    assert config.get_int("AUDITOR_TIMEOUT_SECONDS", env_file=env_file) == -5


@pytest.mark.parametrize("value", ["abc", "12.5"])
def test_get_int_rejects_a_value_that_is_not_a_whole_number(tmp_path: Path, value: str) -> None:
    """Text and decimals are refused with an error naming the setting and the bad value."""
    env_file = write_env_file(tmp_path, f"AUDITOR_TIMEOUT_SECONDS={value}\n")
    with pytest.raises(ValueError, match="must be a whole number"):
        config.get_int("AUDITOR_TIMEOUT_SECONDS", env_file=env_file)


def test_get_int_rejects_a_bad_environment_variable(tmp_path: Path, monkeypatch) -> None:
    """The whole-number check also covers a value coming from the environment."""
    monkeypatch.setenv("AUDITOR_TIMEOUT_SECONDS", "soon")
    with pytest.raises(ValueError, match="soon"):
        config.get_int("AUDITOR_TIMEOUT_SECONDS", env_file=missing_env_file(tmp_path))


def test_get_int_error_says_where_the_bad_value_came_from(tmp_path: Path) -> None:
    """A bad number points at the .env that holds it, so it can be fixed."""
    env_file = write_env_file(tmp_path, "AUDITOR_TIMEOUT_SECONDS=abc\n")
    with pytest.raises(ValueError, match=str(env_file)):
        config.get_int("AUDITOR_TIMEOUT_SECONDS", env_file=env_file)


def test_source_is_reported_as_the_environment(tmp_path: Path, monkeypatch) -> None:
    """A value taken from os.environ is reported as coming from the environment."""
    monkeypatch.setenv(SETTING, "from-environment")
    assert config._describe_source(SETTING, env_file=missing_env_file(tmp_path)) == (
        "environment variable"
    )


def test_source_is_reported_as_the_env_file(tmp_path: Path) -> None:
    """A value taken from .env is reported as coming from that file's path."""
    env_file = write_env_file(tmp_path, f"{SETTING}=from-file\n")
    assert config._describe_source(SETTING, env_file=env_file) == str(env_file)


def test_source_is_reported_as_the_built_in_default(tmp_path: Path) -> None:
    """With nothing configured, the value is reported as the built-in default."""
    assert config._describe_source(SETTING, env_file=missing_env_file(tmp_path)) == (
        "built-in default"
    )


def test_settings_fall_back_to_defaults_when_nothing_is_set(tmp_path: Path) -> None:
    """With no environment variable and no .env, every setting is its built-in default."""
    empty = tmp_path / ".env"
    for name, default in config.DEFAULTS.items():
        assert config.get(name, env_file=empty) == default


def test_get_int_rejects_values_that_look_numeric_but_are_not(tmp_path: Path) -> None:
    """A value int() cannot parse must still name the setting and its source."""
    env_file = tmp_path / ".env"
    env_file.write_text("AUDITOR_TIMEOUT_SECONDS=--5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a whole number"):
        config.get_int("AUDITOR_TIMEOUT_SECONDS", env_file=env_file)


def test_misspelt_setting_in_env_file_is_rejected(tmp_path: Path) -> None:
    """A typo like AUDITOR_MODLE must fail loudly, not silently give the default."""
    env_file = tmp_path / ".env"
    env_file.write_text("AUDITOR_MODLE=oops\n", encoding="utf-8")
    with pytest.raises(ValueError, match="AUDITOR_MODLE"):
        config.get("AUDITOR_MODEL", env_file=env_file)


def test_unrelated_keys_in_env_file_are_left_alone(tmp_path: Path) -> None:
    """A shared .env may hold other tools' settings; only AUDITOR_* typos are our business."""
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgres://x\nAUDITOR_MODEL=tiny\n", encoding="utf-8")
    assert config.get("AUDITOR_MODEL", env_file=env_file) == "tiny"


def test_unmatched_quote_is_kept(tmp_path: Path) -> None:
    """Only a matched pair of quotes is stripped, so a typo stays visible."""
    assert config.parse_env_text('AUDITOR_MODEL="oops\'') == {"AUDITOR_MODEL": '"oops\''}
