"""Importing the wrapper leaves one copy of `web/` and one of `src/` on `sys.path`.

The three modules in `web/` that are imported by bare name bootstrap the import
path themselves: `api.py` inserts its own directory and `src/`,
`artifacts_read.py` inserts `src/`, `serve.py` inserts `web/`. Each insert has
to ask first whether the directory is already there, and twice one of them did
not -- `artifacts_read.py` and `serve.py` were unguarded, so importing either
after `api` left the same directory on the path twice. Nothing tested it, which
is how the second instance survived the fix for the first. A duplicate entry is
not cosmetic: the same file can then be imported under two names, and every
import after it pays for the extra directory scan.

**Import order is the test, not a detail of it.** A duplicate can only appear
when one module has already added a directory and a second adds it again, so a
probe that imports one module proves nothing about the module that runs after
it. Two orders are measured, each a way the wrapper is really started:

- `api`, then `artifacts_read`, then `serve`, with both directories already on
  the path. That is the arrangement inside this suite -- `tests/conftest.py`
  adds `src/` and `tests/web/__init__.py` adds `web/` before any test here
  imports anything -- and it is the order the duplication was found in.
- `serve` alone, with only `web/` on the path: `python web/serve.py`, where the
  interpreter puts the script's own directory there and `serve` pulls in `api`,
  which pulls in `artifacts_read`.

**Each measurement is taken in a subprocess, because `sys.path` is
process-global.** By the time this file runs, other files in this folder have
imported `api` and `serve` for their own reasons, so a count taken here would
describe what they left behind rather than what the wrapper does -- and it could
not choose an import order at all, since a module already in `sys.modules` does
not run again. Every probe below is a fresh interpreter, counting entries on its
own path.

**Every module in `web/` is loaded, and that is asserted rather than assumed.**
The folder went from five modules to ten when the audit became a background
job, and only three of them touch `sys.path` -- so the guard against an
unmeasured *fourth* bootstrapper is that the probe loads the whole folder and
says which names it loaded. A module added to `web/` that nothing imports fails
`test_the_probe_loaded_every_module_in_the_wrapper` by name, which is the
signal to read this file again.

**What it does not cover.** The probe counts these two directories. A wrapper
module that bootstrapped some *third* directory would still be unmeasured until
that directory is counted here.

**The child runs from a temporary directory, not from the repository.**
Importing `api` opens the run history with `create=True` against a relative
path, so a probe started in the checkout would write `runs/history.sqlite3`
into it. The directory the child sits in does not affect what it measures: the
repository root reaches it as `argv[1]`.

The child imports fastapi (through `api`) and uvicorn (through `serve`), so this
file skips without the server packages as the other ten in this folder do.
The probe runs under `sys.executable`, so what this process can import the child
can. Nothing here binds a port or serves a request: the probe imports modules
and prints two counts and two lists of names.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no server")
pytest.importorskip("uvicorn", reason="the web extra is not installed, so there is no server")

from conftest import REPO_ROOT  # noqa: E402

# The two directories the wrapper bootstraps, spelled as its modules spell them:
# absolute and resolved, because `sys.path` holds strings and a count compares
# them exactly. `REPO_ROOT` is resolved, so `str(REPO_ROOT / "src")` is the same
# string `artifacts_read.py` builds from its own `__file__`.
WEB_DIR = REPO_ROOT / "web"
SRC_DIR = REPO_ROOT / "src"

# Every module in `web/` that touches `sys.path`. The probe reports which of them
# the child loaded, so no count below can be read off a run that imported nothing.
WRAPPERS = ("api", "artifacts_read", "serve")

# The whole folder, read off disk rather than listed: ten modules today, and the
# point is to notice the eleventh. `__init__` is excluded because `web/` is not
# a package -- its modules are imported by bare name.
WEB_MODULES = tuple(sorted(path.stem for path in (REPO_ROOT / "web").glob("*.py")
                           if not path.stem.startswith("__")))

# One entry per directory, however many of those modules ran.
EXPECTED_COPIES = 1

# A floor under the folder listing, so a glob that matched nothing cannot pass
# as a folder that was fully loaded. Ten modules today.
MINIMUM_WEB_MODULES = 10

# Puts the named folders on the path, imports the named modules in order, and
# prints what `sys.path` then holds. `dict(...)` rather than a `{}` literal so
# the wrapper names can be formatted in and stay defined in one place.
PROBE = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "root = Path(sys.argv[1])\n"
    "for folder in sys.argv[2].split(','):\n"
    "    sys.path.append(str(root / folder))\n"
    "for module in sys.argv[3].split(','):\n"
    "    __import__(module)\n"
    "print(json.dumps(dict("
    "web=sys.path.count(str(root / 'web')), "
    "src=sys.path.count(str(root / 'src')), "
    "loaded=[name for name in {wrappers} if name in sys.modules], "
    "folder=[name for name in {modules} if name in sys.modules])))\n"
).format(wrappers=WRAPPERS, modules=WEB_MODULES)

# What this suite has on the path before any wrapper is imported, and the import
# order the duplication appeared in.
SUITE_PATH = ("src", "web")
SUITE_ORDER = ("api", "artifacts_read", "serve")

# What `python web/serve.py` has: the script's own directory, and one import.
LAUNCHER_PATH = ("web",)
LAUNCHER_ORDER = ("serve",)


def run_probe(started_in: Path, on_path_first: tuple[str, ...],
              import_in_order: tuple[str, ...]) -> subprocess.CompletedProcess:
    """Import the wrapper modules in that order in a fresh interpreter."""
    return subprocess.run(
        [sys.executable, "-c", PROBE, str(REPO_ROOT),
         ",".join(on_path_first), ",".join(import_in_order)],
        cwd=started_in, capture_output=True, text=True, check=False)


def path_counts(started_in: Path, on_path_first: tuple[str, ...],
                import_in_order: tuple[str, ...]) -> dict:
    """The child's copy counts, once it has shown that all three wrappers really ran."""
    finished = run_probe(started_in, on_path_first, import_in_order)
    assert finished.returncode == 0, f"the probe could not import the wrapper:\n{finished.stderr}"
    counts = json.loads(finished.stdout)
    assert counts["loaded"] == list(WRAPPERS), (
        f"the probe loaded {counts['loaded']} and not every wrapper, so it measured nothing")
    return counts


def duplicated(directory: Path, counts: dict) -> str:
    """The failure message: which directory was added twice, and how many copies there are."""
    return (f"{directory} appears {counts[directory.name]} times on the child's sys.path; "
            "a module in web/ inserted it without checking whether it was already there")


def test_the_order_that_duplicated_leaves_one_web_directory(tmp_path) -> None:
    """`serve` runs last and adds `web/`, which is the instance that survived the first fix."""
    counts = path_counts(tmp_path, SUITE_PATH, SUITE_ORDER)
    assert counts[WEB_DIR.name] == EXPECTED_COPIES, duplicated(WEB_DIR, counts)


def test_the_order_that_duplicated_leaves_one_src_directory(tmp_path) -> None:
    """`artifacts_read` runs after `api` has already added `src/`: the first instance."""
    counts = path_counts(tmp_path, SUITE_PATH, SUITE_ORDER)
    assert counts[SRC_DIR.name] == EXPECTED_COPIES, duplicated(SRC_DIR, counts)


def test_the_launcher_order_leaves_one_web_directory(tmp_path) -> None:
    """Started as `python web/serve.py`, the launcher's own directory is already there."""
    counts = path_counts(tmp_path, LAUNCHER_PATH, LAUNCHER_ORDER)
    assert counts[WEB_DIR.name] == EXPECTED_COPIES, duplicated(WEB_DIR, counts)


def test_the_launcher_order_leaves_one_src_directory(tmp_path) -> None:
    """Under the launcher `api` adds `src/`, so `artifacts_read` must not add it again."""
    counts = path_counts(tmp_path, LAUNCHER_PATH, LAUNCHER_ORDER)
    assert counts[SRC_DIR.name] == EXPECTED_COPIES, duplicated(SRC_DIR, counts)


def test_the_probe_loaded_every_module_in_the_wrapper(tmp_path) -> None:
    """The guard on the two directories above: a module nothing imports is unmeasured.

    `docs/TODO.md` asked for this file to be re-read when a fourth module landed
    in `web/`; five landed at once. Reading the folder off disk turns that from a
    note into a test -- an eleventh module that no import chain reaches is named
    here rather than silently left out of the counts.
    """
    counts = path_counts(tmp_path, SUITE_PATH, SUITE_ORDER)
    assert counts["folder"] == list(WEB_MODULES)


def test_the_wrapper_really_has_the_modules_this_file_counts(tmp_path) -> None:
    """Non-vacuity: an empty folder listing would satisfy the sweep above."""
    assert len(WEB_MODULES) >= MINIMUM_WEB_MODULES
    assert set(WRAPPERS) <= set(WEB_MODULES)
