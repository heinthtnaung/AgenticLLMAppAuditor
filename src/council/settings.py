"""The local model server's settings: an environment variable wins, then `.env`, then the default.

Four settings, each named `AUDITOR_*`:

- `AUDITOR_MODEL`, the model asked where none is named -- by a measurement
  such as `prompt_tokens.py` or a bare `LocalModel()`, never by an audit, and
  never under pytest, where every setting is its default;
- `AUDITOR_SERVER_URL`, the Ollama server, which must be this machine;
- `AUDITOR_TIMEOUT_SECONDS`, how long one call may take;
- `AUDITOR_CONTEXT_TOKENS`, the window a member is pinned to, which the
  context guard in `council.ollama` scales with.

**A council is never switched on here.** Its members come from
`--council-member` alone.

**Only `AUDITOR_*` lines of `.env` are read.** The file is the operator's and
holds other things -- on this machine, a key for a hosted service this project
does not use -- so every other line is passed over unparsed. No refusal quotes
any value but the one it refuses. A misspelt `AUDITOR_*` key is refused rather
than ignored, and a bad value is refused naming where it came from.

**Not settings, on purpose:** temperature, seed and `think` stay pinned in
`council.ollama`, because they are what makes a local member reproducible, and
a run whose sampling a file can change is not comparable with the last one. The
window and the timeout can change a result too, so the record states both.
"""

import math
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlsplit

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
PREFIX = "AUDITOR_"
EXPORT = "export "
COMMENT = "#"
QUOTES = "\"'"

MODEL = "AUDITOR_MODEL"
SERVER = "AUDITOR_SERVER_URL"
TIMEOUT = "AUDITOR_TIMEOUT_SECONDS"
CONTEXT = "AUDITOR_CONTEXT_TOKENS"

# The window's default is measured, and pinned rather than generous: the worst
# advisory of 1,187 takes the prompt to 4,897 tokens by Qwen's count and 5,689 by
# Gemma's, a margin of 1.4x to 1.7x. Moving it changes what a run is comparable
# with, which is why the record states the window a run used.
DEFAULTS = {
    MODEL: "qwen2.5:7b-instruct",
    SERVER: "http://127.0.0.1:11434",
    TIMEOUT: "180",
    CONTEXT: "8192",
}

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
SERVER_SCHEMES = ("http", "https")
# What an earlier version of this project had operators write, endpoint and all.
OLD_ENDPOINT = "/api/generate"
FROM_ENVIRONMENT = "the environment"
FROM_DEFAULT = "the default"


class SettingsError(ValueError):
    """A setting is misspelt, malformed or out of range, and where it came from is named."""


@dataclass(frozen=True)
class Settings:
    """The four settings a run of the local model server uses."""

    model: str
    server: str
    timeout_seconds: float
    context_tokens: int


@cache
def current_settings() -> Settings:
    """Give this process's settings, read once, so a run cannot change them part way."""
    return load_settings(os.environ, ENV_FILE)


def load_settings(environment: Mapping[str, str], env_file: Path) -> Settings:
    """Read the four settings: an environment variable wins, then `.env`, then the default."""
    refuse_unknown_names(environment, FROM_ENVIRONMENT)
    from_file = auditor_lines(env_file)
    chosen = {name: chosen_value(name, environment, from_file) for name in DEFAULTS}
    return Settings(
        model=model_of(*chosen[MODEL]),
        server=server_of(*chosen[SERVER]),
        timeout_seconds=positive(TIMEOUT, *chosen[TIMEOUT], float),
        context_tokens=positive(CONTEXT, *chosen[CONTEXT], int),
    )


def chosen_value(
    name: str, environment: Mapping[str, str], from_file: Mapping[str, tuple[str, str]]
) -> tuple[str, str]:
    """Give one setting's value and where it came from."""
    if name in environment:
        return environment[name], FROM_ENVIRONMENT
    return from_file.get(name, (DEFAULTS[name], FROM_DEFAULT))


def auditor_lines(env_file: Path) -> dict[str, tuple[str, str]]:
    """Read the `AUDITOR_*` lines of a settings file, with where each stands, and no other line."""
    if not env_file.is_file():
        return {}
    found: dict[str, tuple[str, str]] = {}
    with env_file.open(encoding="utf-8") as lines:
        for number, raw in enumerate(lines, start=1):
            line = raw.strip().removeprefix(EXPORT).strip()
            if not line.startswith(PREFIX):
                continue
            where = f"{env_file} line {number}"
            name, value = auditor_setting(line, where)
            if name in found:
                raise SettingsError(f"{name} is set twice: at {found[name][1]}, and at {where}")
            found[name] = (value, where)
    return found


def auditor_setting(line: str, where: str) -> tuple[str, str]:
    """Split one `AUDITOR_*` line into its name and value, refusing a line that is neither."""
    name, equals, value = line.partition("=")
    name = name.strip()
    if not equals:
        named = name.split()[0]
        raise SettingsError(f"{where}: a setting is written NAME=value, and {named} has no '='")
    refuse_unknown_names({name: ""}, where)
    return name, unquoted(value.strip())


def refuse_unknown_names(names: Mapping[str, str], where: str) -> None:
    """Refuse an `AUDITOR_*` name that is not a setting, quoting the name and never its value."""
    unknown = sorted(name for name in names if name.startswith(PREFIX) and name not in DEFAULTS)
    if unknown:
        raise SettingsError(
            f"{where} sets {', '.join(unknown)}, which is not a setting; "
            f"the settings are {', '.join(DEFAULTS)}"
        )


def unquoted(value: str) -> str:
    """Take one matched pair of quotes off a value, leaving an unmatched quote where it is."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTES:
        return value[1:-1]
    return value


def model_of(value: str, source: str) -> str:
    """Give the model to ask where none is named, refusing no name at all."""
    if not value.strip():
        raise SettingsError(f"{MODEL} is empty ({source}); name a model as `ollama list` does")
    return value.strip()


def server_of(value: str, source: str) -> str:
    """Give the server's address, the old form with its endpoint accepted, refusing any other."""
    address = value.strip().rstrip("/").removesuffix(OLD_ENDPOINT)
    parts = urlsplit(address)
    if parts.scheme not in SERVER_SCHEMES or not parts.hostname or parts.path:
        raise SettingsError(
            f"{SERVER} is {value!r} ({source}); give the server's address alone, "
            f"as {DEFAULTS[SERVER]}"
        )
    if parts.hostname not in LOOPBACK_HOSTS:
        raise SettingsError(
            f"{SERVER} is {value!r} ({source}), which is not this machine: a local member "
            f"may only talk to {', '.join(LOOPBACK_HOSTS[:2])}"
        )
    return address


def positive(name: str, value: str, source: str, kind: Callable[[str], float]) -> float:
    """Give a setting as a positive number of the kind asked for, refusing anything else."""
    wanted = "whole number" if kind is int else "number"
    refusal = SettingsError(f"{name} is {value!r} ({source}); it must be a positive {wanted}")
    try:
        number = kind(value.strip())
    except ValueError:
        raise refusal from None
    if not math.isfinite(number) or number <= 0:
        raise refusal
    return number
