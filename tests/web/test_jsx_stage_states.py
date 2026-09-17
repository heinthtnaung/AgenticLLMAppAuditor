"""A stage that will never run may not read as a stage still to come.

`StageProgress.stateOf` showed every unannounced stage as `pending` whenever the
run was no longer going. A finished run therefore rendered steps it had already
skipped as work about to happen, and a `--compare-models` run -- which announces
no stages at all -- rendered all eight that way for ever. That is the same kind
of lie as showing `0` for a count with no document behind it, which is the
defect the dash in `ResultsDashboard` exists to avoid. It answers `unreached`
for any status but `running` now, and this file is that fix's test.

**It runs the page's own code.** Everything above the component in
`StageProgress.jsx` is lifted and evaluated under node -- and the *call* is
lifted too, from the one line in the component that makes it, so a reordering of
`stateOf`'s parameters cannot leave this file quietly passing against the old
order.

**One import is resolved by the lift, and exactly one.** The status vocabulary
moved out of the five modules that each spelled it into
`frontend/src/runStatus.js`, which this component now imports `RUNNING` from.
That module is plain JavaScript with no import of its own, so its source is
prepended with `export ` stripped and the component's import line removed --
the value still comes from the module the component really reads. The
assertion narrowed from "no import at all" to "no import but that one" and no
further: its real job is a React or browser import the lift cannot stand in
for, and `test_a_helper_that_imports_anything_else_is_refused` plants one to
show it still fires.

**Both vocabularies come from the code that owns them.** The stages are
`reporting.progress.STAGES`, which is what `GET /api/stages` serves, and the
statuses are `run_record.RUN_STATUSES`, which is what the history stores -- so
the sweep over "every status that is not running" is over the real closed set,
and a fourth status is covered the day it lands rather than the day someone
remembers this file. The state words are read out of the component, so a
reworded state is a rename this follows and not a string it pins.
`test_jsx_stage_vocabulary.py` holds what those four words are shown with.

What this does not cover: the announcement list itself. Whether an audit really
announces `publish`, and whether a compare run really announces nothing, is
`src/`'s behaviour, and the CLI and reporting tests own it. Here the list is an
input.

Skipped when node is absent, as the vexctl and PDF-font tests skip. Nothing here
needs fastapi, the network, or a rebuilt bundle: it reads the component's
source, not `dist/`.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from reporting.progress import STAGES
from run_record import FINISHED, RUN_STATUSES, RUNNING

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENT = REPO_ROOT / "frontend" / "src" / "components" / "StageProgress.jsx"
VOCABULARY = REPO_ROOT / "frontend" / "src" / "runStatus.js"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Where the plain-JavaScript half of the component ends: at its first component,
# which here is the exported one -- unlike `AdvisoryComponents.jsx`, which
# defines a small one first.
FIRST_COMPONENT = re.compile(r"^(?:export default )?function [A-Z]", re.MULTILINE)

# The one line in the component that calls the helper, lifted so the probe below
# passes the arguments in the component's own order and not in one written here.
STATE_CALL = re.compile(r"const state = (stateOf\([^)]*\));")

# Any import line, and the one the lift can resolve by inlining the module it
# names. Matched as a whole line so a second name added to the same import is
# still recognised, and anything else -- `react`, a browser module -- is not.
IMPORT_LINE = re.compile(r"^import .*$", re.MULTILINE)
VOCABULARY_IMPORT = re.compile(r'import \{[^}]*\} from "\.\./runStatus\.js";')

# What turns the shared module into plain script: it exports its constants, and
# a lifted `export` is a syntax error outside a module.
EXPORT_KEYWORD = re.compile(r"^export ", re.MULTILINE)

# Planted below, because the narrowed guard above is an empty list either way.
IMPORT_THE_LIFT_CANNOT_RESOLVE = 'import { useState } from "react";'

# A local-path audit ends at `write`: nothing is fetched from a URL and nothing
# is published, so the last stage is the one that must not read as pending.
LOCAL_PATH_RUN = STAGES[:-1]

# How far a running run has got in the cases below, chosen so there is at least
# one stage on each side of the working one.
ANNOUNCED_SO_FAR = 2


def component() -> str:
    """The progress list's own source, as text."""
    return COMPONENT.read_text(encoding="utf-8")


def unresolvable_imports(text: str) -> list[str]:
    """Every import line the lift cannot stand in for -- the vocabulary is the one it can."""
    return [line for line in IMPORT_LINE.findall(text)
            if not VOCABULARY_IMPORT.fullmatch(line.strip())]


def vocabulary() -> str:
    """The shared status module as a plain script: its own source, `export` stripped."""
    text = VOCABULARY.read_text(encoding="utf-8")
    assert unresolvable_imports(text) == [], f"{VOCABULARY.name} now imports something itself"
    return EXPORT_KEYWORD.sub("", text)


def helpers() -> str:
    """The component's liftable half: its own plain JavaScript, vocabulary inlined."""
    found = FIRST_COMPONENT.search(component())
    assert found, f"{COMPONENT.name} has no component after its helpers"
    lifted = component()[:found.start()]
    assert unresolvable_imports(lifted) == [], "the helpers now import something node cannot resolve"
    assert VOCABULARY_IMPORT.search(lifted), (
        f"{COMPONENT.name} no longer reads the status vocabulary this lift inlines")
    assert "stateOf" in lifted, f"{COMPONENT.name} no longer declares stateOf above itself"
    return vocabulary() + VOCABULARY_IMPORT.sub("", lifted)


def state_call() -> str:
    """The call the component makes, with its arguments in the component's own order."""
    found = STATE_CALL.search(component())
    assert found, f"{COMPONENT.name} no longer calls stateOf on a line this test can lift"
    return found.group(1)


def word(name: str) -> str:
    """The value of a `const NAME = "..."` in the component, or name what is missing."""
    found = re.search(rf'const {name} = "([^"]*)";', component())
    assert found, f"{COMPONENT.name} declares no string constant {name}"
    return found.group(1)


def status_word(name: str) -> str:
    """The value of a status constant, read from the module that now owns the vocabulary."""
    found = re.search(rf'const {name} = "([^"]*)";', vocabulary())
    assert found, f"{VOCABULARY.name} declares no string constant {name}"
    return found.group(1)


def run_in_node(program: str, argument: object, tmp_path: Path) -> object:
    """Evaluate one program over a JSON argument and return the JSON it printed."""
    script = tmp_path / "stage_probe.mjs"
    script.write_text(program, encoding="utf-8")
    done = subprocess.run([NODE, str(script), json.dumps(argument)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused the component's helpers:\n{done.stderr}"
    return json.loads(done.stdout)


def states(announced: tuple[str, ...], status: str, tmp_path: Path) -> list[str]:
    """What the page makes of one run: the state of every stage, in order."""
    program = (f"{helpers()}\n"
               "const [stages, announced, status] = JSON.parse(process.argv[2]);\n"
               "console.log(JSON.stringify(stages.map((stage, index) =>\n"
               f"  {state_call()})));\n")
    return run_in_node(program, [list(STAGES), list(announced), status], tmp_path)


# --- a run that is still going -------------------------------------------------

def test_an_announced_stage_reads_as_done(tmp_path) -> None:
    """The list is a prefix: what the run has announced, it has finished."""
    shown = states(STAGES[:ANNOUNCED_SO_FAR], RUNNING, tmp_path)
    assert shown[:ANNOUNCED_SO_FAR] == [word("DONE")] * ANNOUNCED_SO_FAR


def test_the_first_unannounced_stage_of_a_running_run_is_the_working_one(tmp_path) -> None:
    """One stage is being worked on, and it is the one after the last announcement."""
    shown = states(STAGES[:ANNOUNCED_SO_FAR], RUNNING, tmp_path)
    assert shown[ANNOUNCED_SO_FAR] == word("WORKING")


def test_the_stages_after_the_working_one_are_pending_while_the_run_goes(tmp_path) -> None:
    """`pending` is a true claim here and only here: the run can still reach them."""
    shown = states(STAGES[:ANNOUNCED_SO_FAR], RUNNING, tmp_path)
    assert set(shown[ANNOUNCED_SO_FAR + 1:]) == {word("PENDING")}


def test_a_running_run_that_has_announced_everything_shows_no_work_left(tmp_path) -> None:
    """The end of a run: every row done, and none of them still to come."""
    assert states(STAGES, RUNNING, tmp_path) == [word("DONE")] * len(STAGES)


# --- and a run that is not ------------------------------------------------------

def test_a_finished_run_shows_the_stage_it_never_reached_as_unreached(tmp_path) -> None:
    """The regression: a local-path audit ends at `write`, so `publish` never happens."""
    shown = states(LOCAL_PATH_RUN, FINISHED, tmp_path)
    assert shown[-1] == word("UNREACHED")
    assert shown[-1] != word("PENDING")


def test_a_finished_run_that_announced_nothing_leaves_no_stage_pending(tmp_path) -> None:
    """The compare-models case, which announces nothing at all: eight rows, none pending."""
    assert states((), FINISHED, tmp_path) == [word("UNREACHED")] * len(STAGES)


def test_no_status_but_running_leaves_a_stage_looking_like_work_to_come(tmp_path) -> None:
    """Over the wrapper's whole status vocabulary, so a fourth status is covered too."""
    for status in RUN_STATUSES:
        if status == RUNNING:
            continue
        assert set(states((), status, tmp_path)) == {word("UNREACHED")}, status


def test_an_announced_stage_stays_done_on_a_run_that_did_not_finish(tmp_path) -> None:
    """The over-correction this must not be: a stage that ran did run, whatever came after."""
    for status in RUN_STATUSES:
        shown = states(STAGES[:ANNOUNCED_SO_FAR], status, tmp_path)
        assert shown[:ANNOUNCED_SO_FAR] == [word("DONE")] * ANNOUNCED_SO_FAR, status


# --- the probe really ran the component ----------------------------------------

def test_the_status_the_page_branches_on_is_the_one_the_server_writes() -> None:
    """The probe's own soundness: the word inlined above is the word the server writes.

    `test_jsx_run_status_vocabulary.py` owns the whole three-word vocabulary and
    holds it against `RUN_STATUSES`. This is the one value this file's programs
    branch on, so it is checked where it is used.
    """
    assert status_word("RUNNING") == RUNNING


def test_a_helper_that_imports_anything_else_is_refused() -> None:
    """The narrowed tripwire, planted: only the vocabulary import may be inlined."""
    planted = f'{IMPORT_THE_LIFT_CANNOT_RESOLVE}\nimport {{ RUNNING }} from "../runStatus.js";'
    assert unresolvable_imports(planted) == [IMPORT_THE_LIFT_CANNOT_RESOLVE]


def test_the_lift_really_inlined_the_module_the_component_imports() -> None:
    """Non-vacuity: a prepend of nothing would leave every program above undefined."""
    assert f'const RUNNING = "{RUNNING}";' in helpers()
    assert "import " not in helpers()


def test_the_probe_read_a_state_for_every_stage_the_server_serves(tmp_path) -> None:
    """Non-vacuity: a probe answering nothing would satisfy every set comparison above."""
    assert len(states((), FINISHED, tmp_path)) == len(STAGES)
    assert len(STAGES) > 1


def test_all_four_states_are_reachable_from_a_run_the_wrapper_can_store(tmp_path) -> None:
    """No declared state is dead, and the probe's answers really vary with its input."""
    seen = set(states(STAGES[:ANNOUNCED_SO_FAR], RUNNING, tmp_path))
    seen |= set(states(STAGES[:ANNOUNCED_SO_FAR], FINISHED, tmp_path))
    assert seen == {word("DONE"), word("WORKING"), word("PENDING"), word("UNREACHED")}
