"""Where the run history lives is decided by the repository, not by the caller.

`history_store.STORE_DIR` used to be the relative `Path("runs")`. `api.py` opens
the store when it is imported and `serve.py` changes directory to the repository
root *after* that import returns, so the history landed wherever the server
happened to be started: an untracked directory holding every repository URL
anyone audited, and a fresh empty one the next time it was started from
somewhere else. It is anchored to the module's own file now, the way `page.py`
anchors the built page.

**Nothing held it, and the suite could not have.** `tests/web/__init__.py`
rebinds `STORE_DIR` to a temporary directory before the first test module in
this folder is imported -- it has to, because importing `api` creates a database
at whatever that constant then says -- so every test in this folder sees the
redirection and not the default. A relative default could come back and the
suite would stay green. That is the third of the three defects found with this
folder, and the only one that had no regression test.

So the default is read in a fresh interpreter, started somewhere else entirely,
with only `web/` on its path: the one arrangement in which the constant's own
value is visible. Two working directories are measured rather than one, because
a relative path *is* stable when read as a string -- what tells the two apart is
that an anchored one names the same absolute directory from both, and a relative
one names neither.

Nothing here skips: `history_store.py` is free of fastapi on purpose, and the
probe imports that module alone. It opens no store, so no database is created
anywhere -- `sqlite3.connect` is what would make one, and only `open_store`
calls it.
"""

import json
import subprocess
import sys
from pathlib import Path

import history_store

from conftest import REPO_ROOT

from . import STORE_DIR as REDIRECTED_STORE_DIR

# The directory the constant is expected to name, spelled the way a reader of
# `history_store.py` would: inside the checkout, beside `artifacts/`, and not
# under it -- everything under `artifacts/` is a documented artifact with a
# byte-identical guarantee, and a mutable database is not one.
EXPECTED_STORE_DIR = REPO_ROOT / "runs"

# The module the probe must have imported, so an empty answer cannot pass as a
# measurement of the right file.
EXPECTED_MODULE = REPO_ROOT / "web" / "history_store.py"

# A second working directory under the first, so the two runs differ in where
# they stand and in nothing else.
NESTED = "somewhere/else/entirely"

# Puts `web/` on the path, imports the store's module and prints the constant
# together with what it actually imported and where it was standing.
PROBE = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.append(str(Path(sys.argv[1]) / 'web'))\n"
    "import history_store\n"
    "print(json.dumps(dict("
    "store_dir=str(history_store.STORE_DIR), "
    "module=str(Path(history_store.__file__).resolve()), "
    "started_in=str(Path.cwd().resolve()))))\n"
)


def probe(started_in: Path) -> dict:
    """The default `STORE_DIR`, read by a fresh interpreter standing somewhere else."""
    started_in.mkdir(parents=True, exist_ok=True)
    finished = subprocess.run([sys.executable, "-c", PROBE, str(REPO_ROOT)],
                              cwd=started_in, capture_output=True, text=True, check=False)
    assert finished.returncode == 0, (
        f"the probe could not import the store's module:\n{finished.stderr}")
    answered = json.loads(finished.stdout)
    assert answered["module"] == str(EXPECTED_MODULE), (
        f"the probe imported {answered['module']}, so it measured another module's constant")
    assert answered["started_in"] == str(started_in.resolve()), (
        "the probe did not run where this test put it, so its answer says nothing "
        "about the working directory")
    return answered


def store_dir(started_in: Path) -> Path:
    """Just the path the probe read, as a `Path`."""
    return Path(probe(started_in)["store_dir"])


# --- the default is anchored, not relative ------------------------------------

def test_the_default_store_directory_is_absolute(tmp_path) -> None:
    """The regression in one word: a relative default is resolved against the caller."""
    assert store_dir(tmp_path).is_absolute()


def test_the_default_store_directory_is_inside_this_repository(tmp_path) -> None:
    """Anchored to the module's own file, so it is the checkout's `runs/` and no other."""
    assert store_dir(tmp_path) == EXPECTED_STORE_DIR


def test_the_default_is_not_read_from_the_working_directory(tmp_path) -> None:
    """A process started in `tmp_path` must not put the history under `tmp_path`."""
    read = store_dir(tmp_path)
    assert tmp_path.resolve() not in read.parents
    assert read != tmp_path.resolve() / EXPECTED_STORE_DIR.name


def test_two_processes_in_two_directories_read_the_same_path(tmp_path) -> None:
    """What separates an anchored path from a stable string: both name one directory."""
    assert store_dir(tmp_path) == store_dir(tmp_path / NESTED)


# --- why this is a subprocess at all ------------------------------------------

def test_this_process_sees_the_redirection_and_not_the_default() -> None:
    """The reason for the probe: in-process, the constant is this folder's temporary copy."""
    assert history_store.STORE_DIR == REDIRECTED_STORE_DIR
    assert history_store.STORE_DIR != EXPECTED_STORE_DIR


def test_the_repository_is_not_where_this_suite_would_write_a_history() -> None:
    """The redirection's own point, and the reason it cannot be a fixture."""
    assert REPO_ROOT not in REDIRECTED_STORE_DIR.parents
