"""Either of `component_ref` and `mapping` may be imported first.

The two refer to each other: `mapping` builds a `ComponentRef`, and
`ComponentRef.__post_init__` validates its `reason` against `MAPPING_REASONS`.
That circle is opened by deferring one side -- the import sits *inside* the
method rather than at module scope -- and this file is the check that it stays
open.

**A fresh interpreter per order is the only honest way to test it.** Inside the
test session both modules are already in `sys.modules`, so an `import` statement
here would succeed whatever the module bodies do. Each order therefore runs in a
subprocess, which also *uses* a reference, so the deferred import is executed
rather than merely not crashing at import time.
"""

import subprocess
import sys
from pathlib import Path

from artifacts import component_ref as component_ref_module

# `src/` is a plain folder of modules, so it is the working directory the child
# imports from -- the same arrangement `tests/conftest.py` makes for this process.
SRC_DIR = Path(component_ref_module.__file__).resolve().parents[1]

PROBE = (
    "import {first}\n"
    "import {second}\n"
    "from artifacts.component_ref import ComponentRef\n"
    "print(ComponentRef('app.py:1:AGENT_DEF:X', '', None, None, None, None, 0,"
    " 'stdlib', 'none').as_entry()['reason'])\n"
)

IMPORT_ORDERS = (
    ("artifacts.component_ref", "artifacts.mapping"),
    ("artifacts.mapping", "artifacts.component_ref"),
)

EXPECTED_OUTPUT = "stdlib"


def import_in_order(first: str, second: str) -> subprocess.CompletedProcess:
    """Import the two modules in the given order in a fresh interpreter, and use one."""
    return subprocess.run(
        [sys.executable, "-c", PROBE.format(first=first, second=second)],
        cwd=SRC_DIR, capture_output=True, text=True, check=False)


def test_component_ref_may_be_imported_before_mapping() -> None:
    """The direction that fails if the `MAPPING_REASONS` import moves to module scope."""
    result = import_in_order(*IMPORT_ORDERS[0])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == EXPECTED_OUTPUT, result.stdout


def test_mapping_may_be_imported_before_component_ref() -> None:
    """The direction the audit actually takes, asserted so the pair is covered both ways."""
    result = import_in_order(*IMPORT_ORDERS[1])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == EXPECTED_OUTPUT, result.stdout


def test_the_probe_really_runs_a_fresh_interpreter() -> None:
    """Guards the two above: a probe that silently did nothing would pass them both."""
    result = import_in_order("artifacts.mapping", "artifacts.no_such_module")
    assert result.returncode != 0
    assert "no_such_module" in result.stderr
