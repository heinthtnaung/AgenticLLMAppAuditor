"""The operator's `.env`: only its `AUDITOR_*` lines are read, and only names that are settings.

Every setting is read the same way -- an environment variable wins, then this
file -- and this is the part they share: which `AUDITOR_*` names exist, and how
a line of the file is read. What each setting's value may be is its reader's:
`council.settings` for the server and whether it may be another machine,
`council.member_setting` for the members, `council.escalation_setting` for the
escalation model.

**Only `AUDITOR_*` lines are read.** The file is the operator's and holds other
things -- on this machine, a key for a hosted service this project does not use
-- so every other line is passed over unparsed. No refusal quotes any value but
the one it refuses. A misspelt `AUDITOR_*` name is refused rather than ignored,
because a setting nobody reads looks exactly like one that took effect.
"""

from pathlib import Path
from typing import Mapping

PREFIX = "AUDITOR_"
EXPORT = "export "
QUOTES = "\"'"

MODEL = "AUDITOR_MODEL"
SERVER = "AUDITOR_SERVER_URL"
REMOTE_SERVER = "AUDITOR_REMOTE_SERVER"
TIMEOUT = "AUDITOR_TIMEOUT_SECONDS"
CONTEXT = "AUDITOR_CONTEXT_TOKENS"
COUNCIL_MEMBERS = "AUDITOR_COUNCIL_MEMBERS"
ESCALATION_MODEL = "AUDITOR_ESCALATION_MODEL"
# Every name a setting may have, in the order a refusal lists them.
NAMES = (MODEL, SERVER, REMOTE_SERVER, TIMEOUT, CONTEXT, COUNCIL_MEMBERS, ESCALATION_MODEL)

FROM_ENVIRONMENT = "the environment"


class SettingsError(ValueError):
    """A setting is misspelt, malformed or out of range, and where it came from is named."""


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
    unknown = sorted(name for name in names if name.startswith(PREFIX) and name not in NAMES)
    if unknown:
        raise SettingsError(
            f"{where} sets {', '.join(unknown)}, which is not a setting; "
            f"the settings are {', '.join(NAMES)}"
        )


def unquoted(value: str) -> str:
    """Take one matched pair of quotes off a value, leaving an unmatched quote where it is."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTES:
        return value[1:-1]
    return value
