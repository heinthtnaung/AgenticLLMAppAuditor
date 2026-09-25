"""Every test runs on the default settings: the operator's `.env` is never read.

The file is the operator's, and on this machine it holds a key for a hosted
service no test may touch. So before any test module is imported, the settings
are pointed at a file that does not exist, and any `AUDITOR_*` variable in the
environment is taken out -- a test's model, server, window and timeout are the
defaults in `council.settings`, whatever the shell running the suite exports.
A live test asks another model through `COUNCIL_LIVE_MODEL`, its own flag.

A test of the settings themselves gives `load_settings` its own environment and
its own file, under `tmp_path`.
"""

import os
from pathlib import Path

import pytest

from council import settings

# Inside the project, so its absence is checkable, and never written by anything.
NO_ENV_FILE = Path(__file__).resolve().parent / "no-operator-settings.env"


def pytest_configure(config: pytest.Config) -> None:
    """Keep the operator's settings out of the run, before any test module is collected."""
    if NO_ENV_FILE.exists():
        raise RuntimeError(f"{NO_ENV_FILE} must not exist: tests read their settings from it")
    settings.ENV_FILE = NO_ENV_FILE
    for name in [name for name in os.environ if name.startswith(settings.PREFIX)]:
        del os.environ[name]
    settings.current_settings.cache_clear()
