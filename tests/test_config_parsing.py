"""Parsing side of src/config.py: KEY=value text and the .env file it is read from."""

from pathlib import Path

import pytest
import config


def write_env_file(directory: Path, text: str) -> Path:
    """Write a .env file in the given directory and return its path."""
    path = directory / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_env_text_needs_no_file() -> None:
    """The parser is pure text in, mapping out; the file read stays at the edge."""
    assert config.parse_env_text("AUDITOR_MODEL=tiny\n") == {"AUDITOR_MODEL": "tiny"}


def test_parse_env_text_skips_blank_lines_and_comments() -> None:
    """Blank lines and # comments are ignored, so a .env can be documented."""
    text = "# the model the auditor talks to\n\n   \nAUDITOR_MODEL=tiny\n# trailing note\n"
    assert config.parse_env_text(text) == {"AUDITOR_MODEL": "tiny"}


def test_parse_env_text_reads_several_settings() -> None:
    """Each KEY=value line becomes one entry in the returned mapping."""
    text = "AUDITOR_MODEL=tiny\nAUDITOR_TIMEOUT_SECONDS=30\n"
    assert config.parse_env_text(text) == {
        "AUDITOR_MODEL": "tiny",
        "AUDITOR_TIMEOUT_SECONDS": "30",
    }


def test_parse_env_text_keeps_an_inline_hash() -> None:
    """Only a whole-line # is a comment, so a '#' inside a value survives."""
    assert config.parse_env_text("AUDITOR_MODEL=tiny#1") == {"AUDITOR_MODEL": "tiny#1"}


def test_parse_env_text_splits_on_the_first_equals_only() -> None:
    """A value may contain '=', because only the first one separates key from value."""
    assert config.parse_env_text("AUDITOR_SERVER_URL=http://h/api?a=b") == {
        "AUDITOR_SERVER_URL": "http://h/api?a=b"
    }


def test_parse_env_text_names_the_given_source_in_an_error() -> None:
    """The caller's source label appears in the parse error, next to the line number."""
    with pytest.raises(ValueError, match="my-source:2"):
        config.parse_env_text("AUDITOR_MODEL=tiny\nbroken\n", source="my-source")


@pytest.mark.parametrize("line", ['AUDITOR_MODEL="tiny"', "AUDITOR_MODEL='tiny'"])
def test_quoted_values_are_unquoted(tmp_path: Path, line: str) -> None:
    """Double- and single-quoted values are stripped of their quotes, as .env files expect."""
    env_file = write_env_file(tmp_path, line + "\n")
    assert config.read_env_file(env_file) == {"AUDITOR_MODEL": "tiny"}


def test_read_env_file_returns_empty_for_a_missing_file(tmp_path: Path) -> None:
    """A missing .env is normal, not an error: it contributes no settings."""
    assert config.read_env_file(tmp_path / ".env") == {}


def test_read_env_file_reads_the_file_on_disk(tmp_path: Path) -> None:
    """An existing .env is read and parsed into settings."""
    env_file = write_env_file(tmp_path, "AUDITOR_MODEL=tiny\n")
    assert config.read_env_file(env_file) == {"AUDITOR_MODEL": "tiny"}


def test_malformed_line_names_the_file_and_line_number(tmp_path: Path) -> None:
    """A line with no '=' fails clearly, pointing at the file and the offending line."""
    env_file = write_env_file(tmp_path, "AUDITOR_MODEL=tiny\n\nAUDITOR_SERVER_URL\n")
    with pytest.raises(ValueError) as error:
        config.read_env_file(env_file)
    assert f"{env_file}:3" in str(error.value)
