"""Puts the study's own modules on the import path for the tests in this folder.

`experiments/` is not part of the tool. It sits outside `src/`, imports its own
modules by bare name (`import exposure`), and `tests/test_experiments_containment.py`
holds that nothing under `src/` may reach it. So the root `tests/conftest.py`
deliberately leaves it off: adding it there would put the cloud client within
reach of every test in the suite, for the sake of six files.

This is a package rather than a second `conftest.py` for a plain reason. With
no `__init__.py` anywhere else under `tests/`, pytest imports every conftest as
the top-level module `conftest`, so a second one replaces the first in
`sys.modules` -- and a dozen test files across the suite do
`from conftest import scan_to_json`. A package gets its own name, runs this
once when the first test in the folder is imported, and touches nothing else.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "experiments"

if not EXPERIMENTS_DIR.is_dir():
    raise RuntimeError("the study's modules are not where these tests expect them: "
                       f"{EXPERIMENTS_DIR}")

# Appended, never inserted: `src/` and `tests/` must win any name collision, so
# a file added to the study can never shadow a module of the tool under test.
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.append(str(EXPERIMENTS_DIR))
