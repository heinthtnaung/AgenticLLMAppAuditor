"""Which rows of a table are open, run as the page's own code under node.

`useExpanded.js` is shared by the findings table and the surfaces table, because
both grew the same three behaviours and two copies of them had already started
to differ. The one that is easy to get wrong, and the reason this file exists:

**`allOpen` is measured against the rows currently on screen.** The findings
table filters by risk class, so the set of ids handed in changes between
renders. Measured against every row ever opened, a filtered list could never say
"all of these are open" -- the button would offer to open rows that are already
open and the one it acts on would flip the wrong way. Measured against the rows
shown, it says something true about what the reader can see, and a row the
filter is hiding keeps whatever state it had. Four tests below are that
distinction and nothing else.

**It runs the module, it does not read it.** `theme.js` lifts whole because it
imports nothing; this one imports `useState`, so the import line is replaced
with a stub that keeps React's documented contract for it -- a lazy initialiser
called once, and a setter that takes a value or an updater. The stub is
asserted to have replaced a line that was really there, so a changed import is a
failure rather than a quietly wrong lift.

What that costs, said plainly: **this is not React.** The stub applies a state
update immediately where React batches and re-renders, so what is proven is the
module's own arithmetic -- the set, and what `allOpen` is measured against --
across a render loop the harness drives one step at a time. Each step has at
most one action, which is the case where the two are equivalent. Whether React
re-renders when it should is not shown here and is not this module's job.

Skipped when node is absent, as `test_theme_resolution.py` and the vexctl tests
skip. Needs no fastapi, no network and no rebuilt bundle.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPANDED = REPO_ROOT / "frontend" / "src" / "useExpanded.js"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The import the lift replaces. Matched exactly, so a module that starts
# importing something else fails here instead of being run against a stub that
# no longer stands for what it imports.
REACT_IMPORT = re.compile(r'^import \{ useState \} from "react";$', re.MULTILINE)

# React's `useState`, as much of it as this module uses: one cell, a lazy
# initialiser called once, and a setter taking a value or an updater.
USE_STATE_STUB = """
const steps = JSON.parse(process.argv[2]);
let cell;
let started = false;
function useState(initial) {
  if (!started) {
    cell = typeof initial === "function" ? initial() : initial;
    started = true;
  }
  return [cell, (next) => { cell = typeof next === "function" ? next(cell) : next; }];
}
"""

# One render per step: read what the hook says, then do the one thing a click
# would have done. The next step is the re-render that follows.
RENDER_LOOP = """
const seen = [];
for (const step of steps) {
  const rows = useExpanded(step.ids);
  seen.push({ allOpen: rows.allOpen, open: step.ids.filter((id) => rows.isOpen(id)) });
  if (step.act) rows[step.act[0]](...step.act.slice(1));
}
console.log(JSON.stringify(seen));
"""

# Three rows, and the two the filter leaves on screen.
ALL_ROWS = ["F-01", "F-02", "F-03"]
SHOWN_ROWS = ["F-01", "F-02"]
HIDDEN_ROW = "F-03"
ONE_ROW = ["F-01"]
NO_ROWS: list[str] = []

TOGGLE_ALL = ["toggleAll"]


def render(steps: list[dict], tmp_path: Path) -> list[dict]:
    """Drive the real module through one render per step, and return what each render saw."""
    module = EXPANDED.read_text(encoding="utf-8")
    lifted, replaced = REACT_IMPORT.subn("", module)
    assert replaced == 1, f"{EXPANDED.name} no longer imports useState the way this lift expects"
    script = tmp_path / "expanded_probe.mjs"
    script.write_text(USE_STATE_STUB + lifted + RENDER_LOOP, encoding="utf-8")
    done = subprocess.run([NODE, str(script), json.dumps(steps)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused the module:\n{done.stderr}"
    return json.loads(done.stdout)


def step(ids: list[str], act: list | None = None) -> dict:
    """One render: the rows on screen, and the click made during it."""
    return {"ids": ids, "act": act}


# --- one row at a time --------------------------------------------------------

def test_every_row_starts_closed(tmp_path) -> None:
    """A table opens folded: the state starts as an empty set, not as every id."""
    assert render([step(ALL_ROWS)], tmp_path)[0]["open"] == []


def test_toggling_a_row_opens_it(tmp_path) -> None:
    """Non-vacuity for everything below: a hook that never opened anything would pass a lot."""
    seen = render([step(ALL_ROWS, ["toggle", "F-02"]), step(ALL_ROWS)], tmp_path)
    assert seen[1]["open"] == ["F-02"]


def test_toggling_the_same_row_again_closes_it(tmp_path) -> None:
    """One control, two directions: a row that only ever opened would need a second control."""
    seen = render([step(ALL_ROWS, ["toggle", "F-02"]),
                   step(ALL_ROWS, ["toggle", "F-02"]),
                   step(ALL_ROWS)], tmp_path)
    assert seen[2]["open"] == []


def test_toggling_one_row_leaves_the_others_alone(tmp_path) -> None:
    """A set, not a single open row: the tables let a reader compare two findings."""
    seen = render([step(ALL_ROWS, ["toggle", "F-01"]),
                   step(ALL_ROWS, ["toggle", "F-03"]),
                   step(ALL_ROWS)], tmp_path)
    assert seen[2]["open"] == ["F-01", "F-03"]


# --- and the control that acts on all of them ---------------------------------

def test_opening_them_all_opens_every_row_on_screen(tmp_path) -> None:
    """What the one button does when nothing is open."""
    seen = render([step(ALL_ROWS, TOGGLE_ALL), step(ALL_ROWS)], tmp_path)
    assert seen[1]["open"] == ALL_ROWS
    assert seen[1]["allOpen"] is True


def test_pressing_it_again_closes_them_all(tmp_path) -> None:
    """The label says which it will do, so the action has to match: open, then closed."""
    seen = render([step(ALL_ROWS, TOGGLE_ALL), step(ALL_ROWS, TOGGLE_ALL),
                   step(ALL_ROWS)], tmp_path)
    assert seen[2]["open"] == []
    assert seen[2]["allOpen"] is False


def test_opening_them_all_when_some_are_open_opens_the_rest(tmp_path) -> None:
    """Not a flip of each row: a half-open table opens fully rather than inverting."""
    seen = render([step(ALL_ROWS, ["toggle", "F-02"]), step(ALL_ROWS, TOGGLE_ALL),
                   step(ALL_ROWS)], tmp_path)
    assert seen[2]["open"] == ALL_ROWS


# --- what the whole module is for: the rows on screen -------------------------

def test_a_filtered_list_can_say_all_of_these_are_open(tmp_path) -> None:
    """The distinction: two rows open out of three is `allOpen` when two are all there is."""
    seen = render([step(SHOWN_ROWS, TOGGLE_ALL), step(SHOWN_ROWS)], tmp_path)
    assert seen[1]["allOpen"] is True


def test_a_row_the_filter_is_hiding_does_not_make_that_false(tmp_path) -> None:
    """Measured against every row ever seen, the same state would read as not-all-open."""
    seen = render([step(SHOWN_ROWS, TOGGLE_ALL), step(ALL_ROWS)], tmp_path)
    assert seen[1]["allOpen"] is False
    assert seen[1]["open"] == SHOWN_ROWS


def test_opening_them_all_leaves_a_hidden_row_closed(tmp_path) -> None:
    """The button acts on what is on screen, which is what its label claims."""
    seen = render([step(SHOWN_ROWS, TOGGLE_ALL), step(ALL_ROWS)], tmp_path)
    assert HIDDEN_ROW not in seen[1]["open"]


def test_closing_them_all_leaves_a_hidden_row_open(tmp_path) -> None:
    """The same rule in the other direction, and the one a reader would notice losing."""
    seen = render([step(ALL_ROWS, TOGGLE_ALL),
                   step(SHOWN_ROWS, TOGGLE_ALL),
                   step(ALL_ROWS)], tmp_path)
    assert seen[2]["open"] == [HIDDEN_ROW]


# --- an empty table -----------------------------------------------------------

def test_an_empty_list_is_not_all_open(tmp_path) -> None:
    """Every id of none is vacuously true, and the button would offer to hide nothing."""
    assert render([step(NO_ROWS)], tmp_path)[0]["allOpen"] is False


def test_a_list_of_one_is_all_open_once_it_is_open(tmp_path) -> None:
    """The boundary beside it: one row is a real list, and the guard is on length zero."""
    seen = render([step(ONE_ROW, TOGGLE_ALL), step(ONE_ROW)], tmp_path)
    assert seen[1]["allOpen"] is True
