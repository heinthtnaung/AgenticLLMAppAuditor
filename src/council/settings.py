"""The local model server's settings: an environment variable wins, then `.env`, then the default.

Four settings, each named `AUDITOR_*`:

- `AUDITOR_MODEL`, the model asked where none is named -- by a measurement
  such as `prompt_tokens.py` or a bare `LocalModel()`, never by an audit, and
  never under pytest, where every setting is its default;
- `AUDITOR_SERVER_URL`, the Ollama server, which must be this machine;
- `AUDITOR_TIMEOUT_SECONDS`, how long one call may take;
- `AUDITOR_CONTEXT_TOKENS`, the window a member is pinned to, which the
  context guard in `council.ollama` scales with.

How `.env` is read, and which other `AUDITOR_*` names exist, is
`council.env_file`. **A council is never switched on here.** A setting names
members; only `--council` or `--council-member` runs one. A bad value is
refused naming where it came from.

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

from council.env_file import (
    CONTEXT,
    FROM_ENVIRONMENT,
    MODEL,
    SERVER,
    TIMEOUT,
    SettingsError,
    auditor_lines,
    refuse_unknown_names,
)

# Looked up each time a setting is read, which is how the tests point it at no file at all.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

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
FROM_DEFAULT = "the default"


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
