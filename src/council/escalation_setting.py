"""The model a council escalates to: `AUDITOR_ESCALATION_MODEL`, read as every other setting is.

An environment variable wins over `.env`, only `AUDITOR_*` lines are read, and a
misspelt key is refused -- by the same loader as every setting,
`council.env_file`. The value is one model name, as `ollama list` gives it.

**Unset is no escalation, never a default model.** Unset or empty, a metric the
council leaves open stays open, and the record says no escalation model was
named. An empty environment variable wins over the file like any other, so it
switches escalation off for one run.

**Only ever a local model.** The name is a model on the Ollama server
`AUDITOR_SERVER_URL` names, which `council.settings` holds to this machine, and
the member built from it runs local (`cli.council_run.local_member`). There is
no provider to name, so a hosted escalation cannot be written here.

Read only when a council is asked for, so a `.env` naming a model starts no
model call on its own.
"""

import os
from pathlib import Path
from typing import Mapping

from council import settings
from council.env_file import (
    ESCALATION_MODEL,
    FROM_ENVIRONMENT,
    SettingsError,
    auditor_lines,
    refuse_unknown_names,
)

# What would make one name two, or a name no model has.
NOT_IN_A_NAME = (",", " ", "\t")


def escalation_model() -> str | None:
    """Give the model a council escalates to, or None where none is named."""
    return load_escalation_model(os.environ, settings.ENV_FILE)


def load_escalation_model(environment: Mapping[str, str], env_file: Path) -> str | None:
    """Read the escalation model: an environment variable wins, then `.env`; unset is None."""
    refuse_unknown_names(environment, FROM_ENVIRONMENT)
    from_file = auditor_lines(env_file)
    if ESCALATION_MODEL in environment:
        return model_named(environment[ESCALATION_MODEL], FROM_ENVIRONMENT)
    if ESCALATION_MODEL in from_file:
        return model_named(*from_file[ESCALATION_MODEL])
    return None


def model_named(value: str, source: str) -> str | None:
    """Give the one model a value names, None for an empty one, refusing a list or a spaced name."""
    name = value.strip()
    if not name:
        return None
    if any(mark in name for mark in NOT_IN_A_NAME):
        raise SettingsError(
            f"{ESCALATION_MODEL} is {value!r} ({source}); it names one model, "
            "as `ollama list` gives it"
        )
    return name
