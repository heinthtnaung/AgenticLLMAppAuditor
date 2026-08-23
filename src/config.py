"""Reads the auditor's settings from the environment, falling back to defaults."""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

# Every setting the auditor understands, with the value used when nothing overrides it.
DEFAULTS = {
    "AUDITOR_MODEL": "qwen2.5-coder:7b-instruct",
    "AUDITOR_SERVER_URL": "http://localhost:11434/api/generate",
    "AUDITOR_TIMEOUT_SECONDS": "120",
}

COMMENT_MARKER = "#"
SETTING_PREFIX = "AUDITOR_"
QUOTES = "\"'"


def _unquote(value: str) -> str:
    """Remove one matched pair of surrounding quotes, leaving an unmatched quote alone."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTES:
        return value[1:-1]
    return value


def parse_env_text(text: str, source: str = "<text>") -> dict[str, str]:
    """Parse KEY=value lines, skipping blank lines and # comments.

    A matched pair of surrounding quotes is removed, because writing
    KEY="value" is a common habit and the quotes are almost never wanted.
    An inline # is NOT a comment: it stays part of the value.
    """
    settings = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(COMMENT_MARKER):
            continue
        if "=" not in line:
            raise ValueError(f"{source}:{number}: expected KEY=value, got {raw!r}")
        key, _, value = line.partition("=")
        settings[key.strip()] = _unquote(value.strip())
    return settings


def read_env_file(path: Path) -> dict[str, str]:
    """Read a settings file. A missing file is a normal state and gives no settings."""
    if not path.is_file():
        return {}
    return parse_env_text(path.read_text(encoding="utf-8"), source=str(path))


def _check_known(name: str) -> None:
    """Reject a setting the auditor does not understand, rather than ignoring it."""
    if name not in DEFAULTS:
        raise KeyError(f"unknown setting {name!r}; expected one of {sorted(DEFAULTS)}")


def _check_no_typos(settings: dict[str, str], source: Path) -> None:
    """Catch a misspelt AUDITOR_* key, which would otherwise be ignored in silence."""
    unknown = sorted(k for k in settings if k.startswith(SETTING_PREFIX) and k not in DEFAULTS)
    if unknown:
        raise ValueError(
            f"{source}: unknown setting(s) {unknown}; expected one of {sorted(DEFAULTS)}"
        )


def get(name: str, env_file: Path = ENV_FILE) -> str:
    """Return one setting: a real environment variable wins, then .env, then the default."""
    _check_known(name)
    if name in os.environ:
        return os.environ[name]
    from_file = read_env_file(env_file)
    _check_no_typos(from_file, env_file)
    return from_file.get(name, DEFAULTS[name])


def _describe_source(name: str, env_file: Path = ENV_FILE) -> str:
    """Say where a setting's value came from, so a bad value can be found and fixed."""
    if name in os.environ:
        return "environment variable"
    if name in read_env_file(env_file):
        return str(env_file)
    return "built-in default"


def get_int(name: str, env_file: Path = ENV_FILE) -> int:
    """Return one setting as a whole number, failing clearly if it is not one."""
    value = get(name, env_file)
    try:
        return int(value)
    except ValueError:
        raise ValueError(
            f"setting {name} must be a whole number, got {value!r} "
            f"(from {_describe_source(name, env_file)})"
        ) from None
