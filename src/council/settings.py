"""The local model server's settings: an environment variable wins, then `.env`, then the default.

Five settings, each named `AUDITOR_*`:

- `AUDITOR_MODEL`, the model asked where none is named -- by a measurement
  such as `prompt_tokens.py` or a bare `LocalModel()`, never by an audit, and
  never under pytest, where every setting is its default;
- `AUDITOR_SERVER_URL`, the Ollama server, which must be this machine unless
  the next setting says otherwise;
- `AUDITOR_REMOTE_SERVER`, the operator's opt-in to a server on another
  machine: only `yes` lets the server be one, and every advisory text a council
  reads is then sent to it;
- `AUDITOR_TIMEOUT_SECONDS`, how long one call may take;
- `AUDITOR_CONTEXT_TOKENS`, the window a member is pinned to, which the
  context guard in `council.ollama` scales with.

How `.env` is read, and which other `AUDITOR_*` names exist, is
`council.env_file`. **A council is never switched on here.** A setting names
members; only `--council` or `--council-member` runs one. A bad value is
refused naming where it came from.

**Whether a run was local is read off the server's host, not the opt-in.** `yes`
beside a loopback address is allowed, and that run is recorded as local,
because it was.

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
    REMOTE_SERVER,
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
    # Unset or empty: the server stays on this machine.
    REMOTE_SERVER: "",
    TIMEOUT: "180",
    CONTEXT: "8192",
}

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
SERVER_SCHEMES = ("http", "https")
# The one value that lets the server be another machine; `true` or `1` is refused.
REMOTE_OPT_IN = "yes"
# What an earlier version of this project had operators write, endpoint and all.
OLD_ENDPOINT = "/api/generate"
# What an address may not carry, by its opening mark; "#" goes first, owning any "?" after it.
USERINFO_MARK = "@"
EXTRA_PARTS = (("#", "a fragment"), ("?", "a query"))
FROM_DEFAULT = "the default"


@dataclass(frozen=True)
class Settings:
    """The five settings a run of the model server uses; one on this machine need not opt in."""

    model: str
    server: str
    timeout_seconds: float
    context_tokens: int
    remote_opted_in: bool = False


@cache
def current_settings() -> Settings:
    """Give this process's settings, read once, so a run cannot change them part way."""
    return load_settings(os.environ, ENV_FILE)


def load_settings(environment: Mapping[str, str], env_file: Path) -> Settings:
    """Read the five settings: an environment variable wins, then `.env`, then the default."""
    refuse_unknown_names(environment, FROM_ENVIRONMENT)
    from_file = auditor_lines(env_file)
    chosen = {name: chosen_value(name, environment, from_file) for name in DEFAULTS}
    remote_opted_in = opted_in(*chosen[REMOTE_SERVER])
    return Settings(
        model=model_of(*chosen[MODEL]),
        server=server_of(*chosen[SERVER], remote_opted_in),
        timeout_seconds=positive(TIMEOUT, *chosen[TIMEOUT], float),
        context_tokens=positive(CONTEXT, *chosen[CONTEXT], int),
        remote_opted_in=remote_opted_in,
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


def opted_in(value: str, source: str) -> bool:
    """Say whether the operator opted in to a server elsewhere, refusing all but `yes` or none."""
    if value.strip() == REMOTE_OPT_IN:
        return True
    if not value.strip():
        return False
    raise SettingsError(
        f"{REMOTE_SERVER} is {value!r} ({source}); only `{REMOTE_OPT_IN}` enables it, letting "
        f"{SERVER} name another machine, and unset or empty leaves it off"
    )


def server_of(value: str, source: str, remote_opted_in: bool) -> str:
    """Give the server's address, the old form with its endpoint accepted, refusing any other."""
    refuse_extra_parts(value, source)
    address = value.strip().rstrip("/").removesuffix(OLD_ENDPOINT)
    parts = urlsplit(address)
    if parts.scheme not in SERVER_SCHEMES or not parts.hostname or parts.path:
        raise SettingsError(
            f"{SERVER} is {value!r} ({source}); give the server's address alone, "
            f"as {DEFAULTS[SERVER]}"
        )
    if remote_opted_in or on_this_machine(address):
        return address
    raise SettingsError(
        f"{SERVER} is {value!r} ({source}), which is not this machine: a local member "
        f"may only talk to {', '.join(LOOPBACK_HOSTS[:2])}; set {REMOTE_SERVER}={REMOTE_OPT_IN} "
        "to send the advisory text to that machine"
    )


def refuse_extra_parts(value: str, source: str) -> None:
    """Refuse an address carrying a username or password, a fragment or a query, naming which."""
    # Not quoted: what sits before an "@" may be a password.
    if USERINFO_MARK in value:
        raise SettingsError(
            f"{SERVER} ({source}) has an '{USERINFO_MARK}' in it, so it may carry a username or "
            f"password; give the server's address alone, as {DEFAULTS[SERVER]}. It is not "
            "quoted here in case it holds a secret"
        )
    carried = [part for mark, part in EXTRA_PARTS if mark in value]
    if carried:
        raise SettingsError(
            f"{SERVER} is {value!r} ({source}), which carries {carried[0]}; give the server's "
            f"address alone, as {DEFAULTS[SERVER]}"
        )


def on_this_machine(server: str) -> bool:
    """Say whether a server's address is this machine's own."""
    return not remote_host(server)


def remote_host(server: str) -> str:
    """Give the host of a server on another machine, and nothing for this machine's own."""
    hostname = urlsplit(server).hostname
    if not hostname:
        raise SettingsError(f"{server!r} names no host, so nothing can say which machine it is")
    return "" if hostname in LOOPBACK_HOSTS else hostname


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
