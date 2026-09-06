"""`Probe.detail` is prose, and exactly one thing in the project joins on it.

`Probe`'s docstring and `SCHEMAS.md` both say it: `detail` is descriptive text,
much of it model-written, so **nothing in the audit or scoring path may join on
it** -- a reader that branched on it would branch on a sentence that changes run
to run. One join exists, outside both paths.
`experiments/agreement.reason_without_a_model` compares a probe's detail against
`semantic_probe.STATIC_REFUTATION` to tell a template refuted from its own text
apart from one a model called safe: both are `refuted` carrying no reason --
`Probe.__post_init__` forbids a reason on a concluded outcome -- so the sentence
is the only marker there is.

The docstring goes on to say that "a second such join would mean the field is
carrying a vocabulary and should be given one". Nothing noticed a second join,
so that sentence was a wish. This file is the sweep that makes it a rule: the
constant may be *defined* in `src/checks/semantic_probe.py` and *named* in
`experiments/agreement.py`, and nowhere else in either tree.

Two spellings of the same join, both caught, because the import is not the only
way in: `from checks.semantic_probe import STATIC_REFUTATION`, and
`semantic_probe.STATIC_REFUTATION` reached through a module `run_checks.py`
already imports. `referenced_names` reads both, plus a bare definition of the
same name, which would be a third copy of the sentence rather than a join.

Copying the sentence instead of importing it is the other way round the rule,
so `modules_using_value` closes it: the literal appears once in `src/`, in the
module that owns it, and nowhere in `experiments/`.

**What this sweep does not cover, deliberately.** Three test modules import
`STATIC_REFUTATION` to pin the constant to the probe that emits it; that is an
assertion about a value, not a branch in a code path, so `tests/` is not swept.
And there is no sweep here for a *direct* comparison against a `.detail`
attribute. It would have to fire on `==`, `in`, `.startswith`, a dict lookup and
a `.get("detail")` to mean anything, and it could not tell a `Probe`'s detail
from a `Surface`'s without inferring types -- so it would either miss the join
it exists for or report `Surface(detail=...)` construction as a violation. The
constant is the reliable signal: joining on the sentence without naming it means
copying it, and the copy is caught above.

Nothing here runs an audit. Every test reads source with the shared scanners, so
each answers "could it?" rather than "did it?".
"""

from pathlib import Path

from ast_scan import (
    imported_modules,
    module_name,
    modules_using_value,
    parse,
    referenced_names,
    source_files,
)
from checks.semantic_probe import STATIC_REFUTATION
from conftest import REPO_ROOT, SRC_DIR

# The study tree, which is not under `src/` -- `test_experiments_containment.py`
# owns that claim and asserts it.
EXPERIMENTS_DIR = REPO_ROOT / "experiments"

# The constant, by name; the module allowed to define it; and the module allowed
# to join on it. Named as paths relative to their own tree, the way the scanners
# report a module.
CONSTANT_NAME = "STATIC_REFUTATION"
OWNER_MODULE = "checks/semantic_probe.py"
OWNER_IMPORT = "checks.semantic_probe"
JOINING_MODULE = "agreement.py"

# Three planted violations, one per spelling, to prove the sweeps fire on a real
# second join rather than on nothing at all.
PLANTED_FILE = "planted.py"
PLANTED_IMPORT_JOIN = (
    "from checks.semantic_probe import STATIC_REFUTATION\n\n"
    "def settled_statically(probe):\n"
    "    return probe.detail == STATIC_REFUTATION\n"
)
PLANTED_ATTRIBUTE_JOIN = (
    "from checks import semantic_probe\n\n"
    "def settled_statically(probe):\n"
    "    return probe.detail == semantic_probe.STATIC_REFUTATION\n"
)
PLANTED_COPIED_SENTENCE = f"SENTENCE = {STATIC_REFUTATION!r}\n"


def modules_naming_the_constant(root: Path) -> set[str]:
    """The modules under a tree that mention `STATIC_REFUTATION`, however they reach it."""
    return {module_name(path, root) for path in source_files(root)
            if CONSTANT_NAME in referenced_names(parse(path))}


def plant(tmp_path: Path, source: str) -> Path:
    """Write a throwaway source tree holding one module, and return its root."""
    root = tmp_path / "planted_src"
    root.mkdir()
    (root / PLANTED_FILE).write_text(source, encoding="utf-8")
    return root


def test_the_owning_module_defines_the_constant() -> None:
    """Non-vacuity for the `src/` sweep: it finds the one module that may name it."""
    assert STATIC_REFUTATION.strip() != ""
    assert OWNER_MODULE in modules_naming_the_constant(SRC_DIR)


def test_no_module_under_src_reaches_for_the_constant() -> None:
    """The audit path does not join on `detail`, even through the constant that names it."""
    assert modules_naming_the_constant(SRC_DIR) == {OWNER_MODULE}


def test_agreement_is_the_only_module_in_the_study_that_names_the_constant() -> None:
    """The one permitted join is one: a second module naming it fails here."""
    assert modules_naming_the_constant(EXPERIMENTS_DIR) == {JOINING_MODULE}


def test_the_one_permitted_join_really_imports_it_from_the_probe() -> None:
    """Non-vacuity: the exception exists, and takes the sentence from the module that owns it."""
    joining = EXPERIMENTS_DIR / JOINING_MODULE
    assert joining.is_file()
    tree = parse(joining)
    assert CONSTANT_NAME in referenced_names(tree)
    assert OWNER_IMPORT in imported_modules(tree)


def test_no_module_under_src_copies_the_sentence() -> None:
    """The other way round the rule: the literal is written once, where it is defined."""
    assert modules_using_value(STATIC_REFUTATION, SRC_DIR) == {OWNER_MODULE}


def test_the_study_joins_on_the_constant_rather_than_on_a_copy() -> None:
    """`agreement.py` imports the sentence; it does not restate it and drift from it."""
    assert modules_using_value(STATIC_REFUTATION, EXPERIMENTS_DIR) == set()


def test_a_planted_import_of_the_constant_is_reported(tmp_path) -> None:
    """Mutation check: `from checks.semantic_probe import STATIC_REFUTATION`."""
    assert modules_naming_the_constant(plant(tmp_path, PLANTED_IMPORT_JOIN)) == {PLANTED_FILE}


def test_a_planted_attribute_reach_for_the_constant_is_reported(tmp_path) -> None:
    """Mutation check: the spelling an import sweep alone would miss."""
    assert modules_naming_the_constant(plant(tmp_path, PLANTED_ATTRIBUTE_JOIN)) == {PLANTED_FILE}


def test_a_planted_copy_of_the_sentence_is_reported(tmp_path) -> None:
    """Mutation check: the join written out in full, naming no constant at all."""
    root = plant(tmp_path, PLANTED_COPIED_SENTENCE)
    assert modules_using_value(STATIC_REFUTATION, root) == {PLANTED_FILE}
