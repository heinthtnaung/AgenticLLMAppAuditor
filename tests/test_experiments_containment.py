"""`experiments/` is outside `src/`, and nothing under `src/` imports it.

The local-vs-cloud study in `experiments/` is the one place in this repository
that talks to a host on the internet: `cloud_client.py` calls a hosted model's
API. It is not part of the tool -- it drives the auditor from outside, through
the `model_ask_fn` seam -- and the README states both halves of that as a
claim. This file is the test the README says exists.

Why it is not folded into `tests/parsing/test_offline_containment.py`, whose
subject is the same: that file already runs to 183 lines, and rule 18 puts the
ceiling at roughly 200. It also asks a different question. It matches imports
against a fixed set of *network* modules -- `urllib.request`, `socket`,
`requests` -- so a module under `src/` writing `import cloud_client` passes it
without a word, because the socket is opened one file further along. The
question here is reachability, not spelling.

The set of forbidden names is read out of `experiments/` rather than written
down, and that is the point. `experiments/compare_models.py` puts both `src`
and `experiments` on `sys.path` and then imports its own modules by bare name
(`import cloud_client`, `from exposure import ...`), so a module under `src/`
could reach them the same way and never write the word "experiments". Deriving
the names from the files actually present means a new file dropped into
`experiments/` is guarded from the moment it lands.

The cost of deriving them: a name collision would be reported as a violation.
If a file named `config.py` were ever added to `experiments/`, a `src/` module
importing its own `config` would fail this sweep. That is the safe direction to
be wrong in, and the fix is to rename the experiment's file.

Nothing here runs an audit or opens anything. Every test reads the source or
the directory listing, so each answers "could it?" rather than "did it?".
"""

from pathlib import Path

from ast_scan import imported_modules, module_name, parse, source_files
from conftest import REPO_ROOT, SRC_DIR

# The study, and the package name a `from experiments import ...` would spell.
EXPERIMENTS_DIR = REPO_ROOT / "experiments"
EXPERIMENTS_PACKAGE = "experiments"

# The five modules present when this guard was written, named so the sweep
# cannot pass by finding an empty or moved directory. `cloud_client` used to be
# here and moved to `src/` when `--compare-models` landed, so the study no
# longer owns the socket -- what is left is the comparison itself. This is a
# floor, not the whole set: a sixth file is covered by the derivation above
# without editing the list.
KNOWN_EXPERIMENT_MODULES = frozenset({"compare_models", "exposure",
                                      "comparison_report", "agreement", "prompt_kinds"})

# Two planted importers, one per spelling, to prove the sweep fires on a real
# violation rather than on nothing at all.
PLANTED_FILE = "planted.py"
PLANTED_BARE_IMPORT = "import agreement\n"
PLANTED_PACKAGE_IMPORT = "from experiments.exposure import Ledger\n"


def experiment_import_names(root: Path = EXPERIMENTS_DIR) -> set[str]:
    """Every name a module could import the study by: the package, and each file's stem."""
    return {EXPERIMENTS_PACKAGE} | {path.stem for path in source_files(root)}


def root_package(import_name: str) -> str:
    """The first component of a dotted import, so `experiments.exposure` reads as `experiments`."""
    return import_name.split(".")[0]


def modules_importing_experiments(root: Path = SRC_DIR,
                                  names: frozenset[str] | None = None) -> set[str]:
    """The modules under a tree that import the study, by package name or by bare stem."""
    forbidden = names if names is not None else frozenset(experiment_import_names())
    return {module_name(path, root) for path in source_files(root)
            if any(root_package(name) in forbidden
                   for name in imported_modules(parse(path)))}


def test_experiments_is_a_directory_at_the_repository_root() -> None:
    """The structural half of the claim: the study exists where the README says it does."""
    assert EXPERIMENTS_DIR.is_dir()
    assert EXPERIMENTS_DIR.parent == REPO_ROOT


def test_experiments_is_not_inside_src() -> None:
    """The other structural half: the study is not part of the tool's source tree."""
    assert SRC_DIR not in EXPERIMENTS_DIR.parents
    assert EXPERIMENTS_DIR != SRC_DIR


def test_the_experiment_modules_guarded_against_are_present() -> None:
    """Non-vacuity: the sweep below has the four named modules to find, not an empty folder."""
    assert experiment_import_names() >= KNOWN_EXPERIMENT_MODULES


def test_the_studys_own_entry_point_is_one_of_the_names_derived() -> None:
    """A module really present is really derived, so the sweep cannot pass on nothing.

    It used to be `cloud_client` here, because that was the module reaching the
    internet. It now lives in `src/` behind `--compare-models`, so this tree no
    longer owns a socket and the guard's subject is the study's own code.
    """
    assert (EXPERIMENTS_DIR / "compare_models.py").is_file()
    assert "compare_models" in experiment_import_names()


def test_no_source_module_imports_anything_from_experiments() -> None:
    """The import half of the claim, asserted as an exact empty set over all of `src/`."""
    assert modules_importing_experiments() == set()


def test_that_the_sweep_would_notice_a_bare_name_import(tmp_path) -> None:
    """Mutation check: `import agreement` names no folder, and must still be caught."""
    (tmp_path / PLANTED_FILE).write_text(PLANTED_BARE_IMPORT, encoding="utf-8")
    assert modules_importing_experiments(tmp_path) == {PLANTED_FILE}


def test_that_the_sweep_would_notice_a_package_qualified_import(tmp_path) -> None:
    """Mutation check: the other spelling, `from experiments.exposure import ...`."""
    (tmp_path / PLANTED_FILE).write_text(PLANTED_PACKAGE_IMPORT, encoding="utf-8")
    assert modules_importing_experiments(tmp_path) == {PLANTED_FILE}


def test_that_a_new_file_in_experiments_is_guarded_without_editing_this_test(tmp_path) -> None:
    """The derivation earns its keep: a stem that is not in the named four is still forbidden."""
    study = tmp_path / EXPERIMENTS_PACKAGE
    study.mkdir()
    (study / "vendor_probe.py").write_text("API = 'https://example.invalid'\n", encoding="utf-8")
    assert "vendor_probe" in experiment_import_names(study)
