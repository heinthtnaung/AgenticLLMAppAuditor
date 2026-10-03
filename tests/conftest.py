"""Every test runs on the default settings: the operator's `.env` is never read.

The file is the operator's, and on this machine it holds a key for a hosted
service no test may touch. So before any test module is imported, the settings
are pointed at a file that does not exist, and any `AUDITOR_*` variable in the
environment is taken out -- a test's model, server, window and timeout are the
defaults in `council.settings`, whatever the shell running the suite exports.
A live test asks another model through `COUNCIL_LIVE_MODEL`, its own flag.

A test of the settings themselves gives `load_settings` its own environment and
its own file, under `tmp_path`.

**And no test reaches the model server.** Every request to it goes through
`council.transport`, and outside the live tests (`COUNCIL_LIVE_OLLAMA`) one
sent to the server's port is refused, so a test that forgot its fake client
fails rather than asking the operator's Ollama for real. So is one sent to any
machine but this one, on any port, so a test of a server elsewhere
(`remote_server`) cannot reach one. A test's own server, on a port of its own
here, is still reached, whether it is asked with a request or a plain URL.

**The guard covers this process and nothing it starts.** A subprocess -- a
docs live check running `audit`, say -- has its own opener and is not guarded.
No documented run names a council, and
`test_no_documented_run_asks_for_a_council_so_none_reads_the_operator_s_settings`,
in `tests/docs/test_readme_runs.py` and `tests/docs/test_usage_runs.py`, fails
the day one does.
"""

import os
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

import pytest

from council import env_file, settings, transport

# Inside the project, so its absence is checkable, and never written by anything.
NO_ENV_FILE = Path(__file__).resolve().parent / "no-operator-settings.env"
# The flag the live tests are asked for by; only they may reach a model server.
LIVE_MODEL_FLAG = "COUNCIL_LIVE_OLLAMA"
# A documentation address (RFC 5737), which routes nowhere, standing in for an
# Ollama server on the operator's network.
REMOTE_SERVER_URL = "http://192.0.2.15:11434"


def pytest_configure(config: pytest.Config) -> None:
    """Keep the operator's settings out of the run, before any test module is collected."""
    if NO_ENV_FILE.exists():
        raise RuntimeError(f"{NO_ENV_FILE} must not exist: tests read their settings from it")
    settings.ENV_FILE = NO_ENV_FILE
    for name in [name for name in os.environ if name.startswith(env_file.PREFIX)]:
        del os.environ[name]
    settings.current_settings.cache_clear()


@pytest.fixture(autouse=True)
def no_model_server_is_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse every request to the model server, unless the live tests were asked for."""
    if os.environ.get(LIVE_MODEL_FLAG):
        return
    opening = transport.NO_PROXY_OPENER.open
    server = urlsplit(settings.current_settings().server)

    def refusing(request, *given, **named):
        """Fail a request to the model server or another machine; pass a test's own server here."""
        # `open` takes a plain URL as well as a request, as `transport.get_json` sends one.
        url = request if isinstance(request, str) else request.full_url
        sent_to = urlsplit(url)
        if sent_to.port == server.port or sent_to.hostname not in settings.LOOPBACK_HOSTS:
            raise AssertionError(f"a test sent a request to {url}; give it a fake client instead")
        return opening(request, *given, **named)

    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", refusing)


@pytest.fixture
def remote_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Opt the settings in to an Ollama server on another machine for one test, giving its URL."""
    monkeypatch.setenv(env_file.SERVER, REMOTE_SERVER_URL)
    monkeypatch.setenv(env_file.REMOTE_SERVER, settings.REMOTE_OPT_IN)
    settings.current_settings.cache_clear()
    yield REMOTE_SERVER_URL
    # Read again by the next test, from the environment `monkeypatch` puts back.
    settings.current_settings.cache_clear()
