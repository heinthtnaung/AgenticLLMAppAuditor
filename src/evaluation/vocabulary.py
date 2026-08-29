"""How much of the detector vocabulary the corpus actually exercises.

An evaluation result, not a detector concern: a name the fixtures never reach is
a name the corpus cannot speak for, however many of them the tables hold. The
count lives here because prose counts drift -- `TODO.md` carried "57 across 12
tables" for a while and no reading of the source reproduced it.

**What counts as a framework name.** An identifier this project looks for in
audited code, drawn from a framework or library API: `ChatOpenAI`,
`AgentExecutor`, `cursor.execute`. Counted once per language, deduplicated,
because `HIGH_PRIVILEGE_TOOLS` and `TOOL_CLASSES` deliberately overlap.

**What does not count, and why.** `PROMPT_NAME_HINTS` are substrings of names
the *app author* chose, not API names. `MESSAGE_TEXT_KEYS` are dict keys in a
chat message. `HTTP_METHODS` and `ROUTE_METHODS` are HTTP verbs.
`ROUTE_DECORATOR_ROOTS` and `ROUTE_OBJECTS` are conventional object names like
`app` and `router`, and the two are the same table under two names. Counting any
of them would inflate the total with things no framework published.
"""

from detectors import detector_names, detector_names_js
from parsing.languages import JAVASCRIPT, PYTHON

# The tables holding framework API names. Every other table in those modules is
# excluded for the reasons in the module docstring.
API_NAME_TABLES = (
    "AGENT_FACTORIES",
    "MODEL_CLASSES",
    "PROMPT_CLASSES",
    "TOOL_CLASSES",
    "TOOL_FACTORIES",
    "TOOL_DECORATORS",
    "HIGH_PRIVILEGE_TOOLS",
    "DATA_SOURCE_CALLS",
    "DATA_SOURCE_METHODS",
    "DATA_SOURCE_MEMBERS",
)

NAME_MODULES = {PYTHON: detector_names, JAVASCRIPT: detector_names_js}


def registered_names(language: str) -> set[str]:
    """Every framework name the detectors look for in one language, deduplicated."""
    module = NAME_MODULES.get(language)
    if module is None:
        raise ValueError(f"no name tables for {language!r}; expected one of {sorted(NAME_MODULES)}")
    names: set[str] = set()
    for table in API_NAME_TABLES:
        names |= set(getattr(module, table, ()))
    return names


def _reaches(registered: str, found: str) -> bool:
    """Say whether one extracted surface name reaches a registered name.

    Matched by dot segment, not by whole string: a detector matches a *root*
    and then names the surface with the attribute chain it found, so
    `AgentExecutor` is genuinely reached by `AgentExecutor.from_agent_and_tools`
    and `execute` by `cursor.execute`. Comparing whole names undercounts, and
    it undercounts in the direction that flatters the corpus -- it reported
    `AgentExecutor` as untested while a graded key entry rests on it.
    """
    return (registered == found
            or found.startswith(f"{registered}.")
            or found.endswith(f".{registered}"))


def exercised_names(surfaces: list, registered: set[str]) -> set[str]:
    """The registered names a scan actually reached."""
    found = {surface.name for surface in surfaces}
    return {name for name in registered if any(_reaches(name, one) for one in found)}


def coverage(language: str, surfaces: list) -> dict:
    """Say how many registered names one language's fixtures reach, and how many they do not."""
    registered = registered_names(language)
    reached = sorted(exercised_names(surfaces, registered))
    return {
        "language": language,
        "registered": len(registered),
        "exercised": len(reached),
        "untested": len(registered) - len(reached),
        "exercised_names": reached,
    }
