"""Puts the HTTP wrapper's own modules on the import path for the tests in this folder.

`web/` is not part of the tool. It sits outside `src/`, imports its own modules
by bare name (`from api import app`), and `tests/test_web_containment.py` holds
that nothing under `src/` may reach it. So the root `tests/conftest.py`
deliberately leaves it off: adding it there would put a module that accepts
connections within reach of every test in the suite, for the sake of the files
in this folder that import the wrapper. One of them needs nothing on this path:
`test_import_path_bootstrap.py`, which counts `sys.path` entries in a
subprocess exactly because this process's copy is the append below and not the
wrapper's own doing. Several need only the wrapper's fastapi-free modules --
`run_record`, `history_store`, `run_jobs`, `audit_request` -- and so never skip;
`test_jsx_record_fields.py` is one, since the run record is now a shape the page
reads.

This is a package rather than a second `conftest.py` for the reason
`tests/experiments/__init__.py` records: with no `__init__.py` anywhere else
under `tests/`, pytest imports every conftest as the top-level module
`conftest`, so a second one replaces the first in `sys.modules` -- and a dozen
test files across the suite do `from conftest import scan_to_json`. A package
gets its own name, runs this once when the first test in the folder is
imported, and touches nothing else.

One consequence to know before writing a test here: pytest names this package
after its folder, so `sys.modules["web"]` is *this* file and not the wrapper
being tested. Import the wrapper's modules by bare name -- `import api`, `from
audit_request import AuditRequest` -- which is how `web/serve.py` imports them
too. `from web.api import ...` would look in this directory.

**The run history is moved out of the repository before anything imports the
wrapper**, and that is the one thing this file does beyond the path. See below
for why it has to happen here and not in a fixture.

Nothing here imports fastapi or uvicorn. The files that need them say so with
`pytest.importorskip`, so a clean checkout without the server packages
installed skips those and still runs the rest. `api_stubs.py` is the exception
and not a gap: it imports fastapi outright, and every file that imports it
skips first.
"""

import atexit
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"

if not WEB_DIR.is_dir():
    raise RuntimeError("the web wrapper's modules are not where these tests expect them: "
                       f"{WEB_DIR}")

# Appended, never inserted, so `src/` and `tests/` -- already on the path from
# the root conftest -- win a name collision here, and a file added to the
# wrapper can never shadow a module of the tool under test. The append is what
# keeps `web/` last: `api.py` inserts both its own directory and `src/` at
# position 0, but only when they are missing, so under pytest both inserts are
# no-ops. Measured after `import api` in this suite: `src/` at index 0, `web/`
# at the end. Launched instead by `web/serve.py` or `uvicorn web.api:app` the
# inserts do run, and they too leave `src/` ahead of `web/`.
if str(WEB_DIR) not in sys.path:
    sys.path.append(str(WEB_DIR))

import history_store  # noqa: E402  - only reachable once `web/` is on the path

# Where this folder's throwaway history goes, so `runs/history.sqlite3` in the
# checkout is never touched by a test run.
#
# **Why here.** `web/api.py` opens the store *at import*, with `create=True`,
# and `history_store.STORE_DIR` is anchored to this repository -- asserted by
# `test_history_store_location.py`, which has to read that constant in a
# subprocess because the line below has already rebound it in this one. So
# merely importing `api` creates a database in the checkout, and by the time any
# fixture runs the file exists and the routes have already been handed the
# store that owns it (`downloads.register` captures it in a closure, so a later
# `api.STORE = ...` would not reach it).
# The only moment before that is this package's own import, which pytest runs
# once, before the first test module in the folder. That is the mechanism the
# other option -- monkeypatching `api.REGISTRY.store` per test -- cannot cover:
# it redirects the four run routes, because they read `registry.store` on every
# call, and leaves the file in the repository already made.
#
# Every test that actually stores a row builds its own store under `tmp_path`
# (`api_stubs.open_a_store`) and drives a fresh application over it, so this
# directory normally ends up holding one empty database and nothing else. It is
# a design cost, not a tidy-up: a module that makes durable state at import
# time can only be kept off the real path by getting in first.
#
# One assignment is the whole redirection: `open_store` resolves `STORE_DIR` at
# *call* time rather than binding it as a default argument, so rebinding the
# module constant reaches the caller that passes no directory -- `api.py`, the
# only one that matters here. Nothing is wrapped, so
# `test_history_store_open.py` still exercises the real `open_store`, and one
# test there holds that this assignment alone moves the file.
STORE_DIR = Path(tempfile.mkdtemp(prefix="auditor-test-run-history-"))
history_store.STORE_DIR = STORE_DIR

# Left behind otherwise: `mkdtemp` does not clean up, and a suite that litters
# `/tmp` with databases of its own is the kind of thing this project asserts
# about the auditor and should hold itself to.
atexit.register(shutil.rmtree, STORE_DIR, ignore_errors=True)
