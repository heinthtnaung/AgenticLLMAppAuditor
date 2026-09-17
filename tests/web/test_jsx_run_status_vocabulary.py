"""The run-status vocabulary is spelled once in the page, and it is the server's own.

`web/run_record.py::RUN_STATUSES` is the closed set a run can be in. The browser
needs the same three words -- the audit form disables itself while one is
`running`, the redirect fires on `finished`, the failure notice on `failed` --
and it had spelled them in a module apiece. That is the shape of duplication
this project has already paid for once: a guard written several times and fixed
in all but one of them.

**How many copies there were, and which files, is written in
`frontend/src/runStatus.js` and nowhere else** -- not here, and not in
`docs/TODO.md`. This note carried its own census until the list went stale in
two directions at once: it named a component that had never spelled a status and
missed the one that spelled three of them as bare object keys, which is the
exact form the second sweep below exists for. A count restated in three
documents is three counts.

`runStatus.js` is the one copy now, and this file holds two claims about it:

- **It equals the server's vocabulary**, name for name and value for value, so a
  status renamed in `src/` fails here rather than silently un-triggering the
  redirect. A *fourth* status added in `src/` fails here too, and that is
  deliberate: `AuditPage` shows an overlay for `running` and a notice for
  `failed`, so a run in a status the page has never heard of renders as nothing
  at all.
- **Nothing else spells one.** Two forms are swept, because the words can be
  written two ways: as a string literal (`const RUNNING = "running"`), and as a
  bare object key (`{ finished: "low" }`), which is how a status-keyed lookup
  table re-introduces the same copy without a quote in sight.

**No test in this suite renders React**, which is a recorded defect and not
something this file closes. It reads the page's modules as text: it can say
which module *mentions* a name and which module imports it, and it cannot say
that the value reaches a rendered element. `jsx_sweep.strip_comments` runs first,
so a component that explains its decisions in prose that names a status --
several do -- is not reported as a module spelling one.

Reads `web/run_record.py`, which is free of fastapi on purpose, and the JSX as
text. No fastapi, no node, no build.
"""

import re
from pathlib import Path

from run_record import FAILED, FINISHED, RUN_STATUSES, RUNNING

from .jsx_sweep import FRONTEND_SRC, strip_comments

VOCABULARY = FRONTEND_SRC / "runStatus.js"

# What the page is written in. `.json` and `.css` are not code and are not swept.
CODE_SUFFIXES = (".js", ".jsx")

# The constant names the shared module is expected to export, mapped to the
# values `src/` gives them. The names are spelled here; every value comes from
# the server's own module.
SERVER_VOCABULARY = {"RUNNING": RUNNING, "FINISHED": FINISHED, "FAILED": FAILED}

# An exported constant, and one import of the shared module with the names it
# takes. Both matched on the module's own spelling.
EXPORTED_CONSTANT = re.compile(r'export const ([A-Z][A-Z_]*) = "([^"]*)";')
EXPORTED_NAME = re.compile(r"export (?:const|function) ([A-Za-z_]\w*)")
VOCABULARY_IMPORT = re.compile(r'import \{([^}]*)\} from "[./]*runStatus\.js";')

# The two ways a module can re-spell a status: quoted, and as a bare key in an
# object literal. The second is the one a reader's eye slides over.
QUOTED_STATUS = re.compile(rf"""["'`]({"|".join(RUN_STATUSES)})["'`]""")
STATUS_AS_KEY = re.compile(rf"""\b({"|".join(RUN_STATUSES)})\s*:""")

# Floors, so a sweep that read nothing cannot pass as a sweep that found no
# fault. Both are set well under what the page has, so an ordinary edit does not
# move them -- and neither is a census: `runStatus.js` names the importers, and
# a second list here is the thing this file's own docstring got wrong.
MINIMUM_MODULES = 20
MINIMUM_IMPORTERS = 4

# Planted below, because both sweeps return an empty list either way.
A_STATUS_SPELLED_AGAIN = f'const RUNNING = "{RUNNING}";'
A_STATUS_USED_AS_A_KEY = f'const TONE = {{ {FINISHED}: "low" }};'


def modules() -> list[Path]:
    """Every JavaScript module the page's own source ships, in a stable order."""
    found = sorted(path for path in FRONTEND_SRC.rglob("*.js*")
                   if path.suffix in CODE_SUFFIXES)
    assert found, f"no JavaScript under {FRONTEND_SRC}; the page has no code at all"
    return found


def code_of(path: Path) -> str:
    """One module's source with its comments gone: they name statuses in prose."""
    return strip_comments(path.read_text(encoding="utf-8"))


def other_modules() -> list[tuple[str, str]]:
    """Every module but the vocabulary itself, paired with its name."""
    return [(path.name, code_of(path)) for path in modules() if path != VOCABULARY]


def declared() -> dict[str, str]:
    """The status constants the shared module exports, name to value."""
    return dict(EXPORTED_CONSTANT.findall(code_of(VOCABULARY)))


def exported_names() -> set[str]:
    """Every name the shared module exports, constants and functions alike."""
    return set(EXPORTED_NAME.findall(code_of(VOCABULARY)))


def imported_names() -> set[str]:
    """Every name any module takes from the shared vocabulary."""
    taken: set[str] = set()
    for _, text in other_modules():
        for group in VOCABULARY_IMPORT.findall(text):
            taken |= {name.strip() for name in group.split(",") if name.strip()}
    return taken


def importers() -> set[str]:
    """Every module that reads the shared vocabulary rather than restating it."""
    return {where for where, text in other_modules() if VOCABULARY_IMPORT.search(text)}


def modules_naming_a_status_constant() -> set[str]:
    """Every module that uses one of the constant names, however it got it."""
    named = set()
    for where, text in other_modules():
        used = [name for name in SERVER_VOCABULARY if re.search(rf"\b{name}\b", text)]
        if used:
            named.add(where)
    return named


def reported(sources: list[tuple[str, str]], pattern: re.Pattern) -> list[str]:
    """Name every source that re-spells a status, file and word, or return nothing."""
    return sorted({f"{where}: {word}" for where, text in sources
                   for word in pattern.findall(text)})


# --- the one copy is the server's own -----------------------------------------

def test_the_page_spells_exactly_the_three_statuses_the_server_writes() -> None:
    """A rename in `src/` fails here rather than silently un-triggering the redirect."""
    assert declared() == SERVER_VOCABULARY


def test_the_vocabulary_is_the_whole_closed_set_the_server_has() -> None:
    """A fourth status in `src/` is a run the page would render as nothing at all."""
    assert set(declared().values()) == set(RUN_STATUSES)


# --- and nothing else spells one -----------------------------------------------

def test_no_other_module_spells_a_status_as_a_string_of_its_own() -> None:
    """The five copies this module replaced; a sixth would be a guard fixed in five places."""
    assert reported(other_modules(), QUOTED_STATUS) == []


def test_no_module_keys_a_map_by_the_status_words_instead_of_the_vocabulary() -> None:
    """The quiet form of the same copy: a lookup table keyed by bare status words.

    `StageProgress.jsx` already shows the form that does not duplicate --
    `{ [DONE]: "✓" }`, computed from the constant -- so a map keyed by the
    words themselves is a second vocabulary with no quote to notice.
    """
    keyed = reported(other_modules(), STATUS_AS_KEY)
    assert keyed == [], f"key this by the constants, as StageProgress keys MARK: {keyed}"


def test_every_module_that_branches_on_a_status_takes_it_from_the_one_module() -> None:
    """The other direction: a name used without the import is a name from somewhere else."""
    assert sorted(modules_naming_a_status_constant() - importers()) == []


def test_every_name_the_vocabulary_exports_is_read_somewhere() -> None:
    """An export nothing imports is dead code (rule 14), and a predicate nobody calls."""
    unread = sorted(exported_names() - imported_names())
    assert unread == [], f"{VOCABULARY.name} exports what nothing imports: {unread}"


# --- the sweeps really swept ---------------------------------------------------

def test_the_sweep_read_the_modules_the_page_is_written_from() -> None:
    """Non-vacuity: an empty module list satisfies every sweep above having read nothing."""
    assert len(modules()) >= MINIMUM_MODULES
    assert len(importers()) >= MINIMUM_IMPORTERS


def test_a_status_a_module_spells_itself_is_reported_with_its_file() -> None:
    """Planted: the quoted sweep is a check that returns an empty list either way."""
    assert reported([("AuditPage.jsx", A_STATUS_SPELLED_AGAIN)], QUOTED_STATUS) == [
        f"AuditPage.jsx: {RUNNING}"]


def test_a_status_used_as_a_map_key_is_reported_with_its_file() -> None:
    """Planted for the second form, which is the one that is passing today."""
    assert reported([("HistoryTable.jsx", A_STATUS_USED_AS_A_KEY)], STATUS_AS_KEY) == [
        f"HistoryTable.jsx: {FINISHED}"]
