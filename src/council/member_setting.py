"""The members `--council` runs: `AUDITOR_COUNCIL_MEMBERS`, read as every other setting is.

An environment variable wins over `.env`, only `AUDITOR_*` lines are read, and a
misspelt key is refused -- by the same loader as the rest of `council.settings`.
The value is model names separated by commas, in the order they are asked.

**Unset is no members, never a default model.** A council asked for with nobody
named is refused, saying where the setting was looked for, because running one
model nobody chose would be a council the operator did not ask for.

Read only when `--council` asks for it, so a `.env` naming members starts no
model call on its own.
"""

import os
from pathlib import Path
from typing import Mapping

from council import settings
from council.settings import (
    COUNCIL_MEMBERS,
    FROM_ENVIRONMENT,
    SettingsError,
    auditor_lines,
    refuse_unknown_names,
)

SEPARATOR = ","
NO_SUCH_FILE = " (no such file)"


def council_members() -> tuple[str, ...]:
    """Give the members `--council` runs, from this process's environment and `.env`."""
    return load_council_members(os.environ, settings.ENV_FILE)


def load_council_members(environment: Mapping[str, str], env_file: Path) -> tuple[str, ...]:
    """Read the members: an environment variable wins, then `.env`; none at all is refused."""
    refuse_unknown_names(environment, FROM_ENVIRONMENT)
    from_file = auditor_lines(env_file)
    if COUNCIL_MEMBERS in environment:
        return members_of(environment[COUNCIL_MEMBERS], FROM_ENVIRONMENT)
    if COUNCIL_MEMBERS in from_file:
        return members_of(*from_file[COUNCIL_MEMBERS])
    looked = f"{env_file}{'' if env_file.is_file() else NO_SUCH_FILE}"
    raise SettingsError(
        f"--council runs the members {COUNCIL_MEMBERS} names, and it is set in neither "
        f"the environment nor {looked}; name the models there, comma-separated, "
        "or give --council-member"
    )


def members_of(value: str, source: str) -> tuple[str, ...]:
    """Split the setting into model names, refusing none, an empty entry, or one named twice."""
    names = [one.strip() for one in value.split(SEPARATOR)]
    if names == [""]:
        raise SettingsError(
            f"{COUNCIL_MEMBERS} is empty ({source}), so --council has no member to run; "
            "name the models there, comma-separated"
        )
    if "" in names:
        raise SettingsError(
            f"{COUNCIL_MEMBERS} is {value!r} ({source}), which has an empty entry; "
            "separate model names with single commas"
        )
    twice = sorted({one for one in names if names.count(one) > 1})
    if twice:
        raise SettingsError(
            f"{COUNCIL_MEMBERS} names {', '.join(twice)} more than once ({source}); "
            "a member is asked once"
        )
    return tuple(names)
