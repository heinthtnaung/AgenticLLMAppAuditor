"""What the model pill says in each of its four states, run as the page's own code.

`ModelStatus.jsx` reduces the whole `/api/model` reply to a state, a label and a
detail. Four states, and two of the distinctions are ones this project cares
about elsewhere and would not want a page blurring. **`asking` is not `down`**:
a page that has not heard back yet must not claim the server is stopped, and
there is a moment on every load where that is the answer. **`incomplete` is not
`down` either**: a reachable server missing the configured model is still
online, and it is worth its own state because that failure lands mid-run, after
the repository has already been cloned.

**The label goes bare when it is working** and names the state otherwise -- a
control labelled with its own good news is noise, one silent about bad news is
worse. Which is why `aria-label` carries both halves either way: the visible
text no longer says "Online", so a reader who cannot see the dot's colour has
only that attribute and the tooltip.

**It runs the module's head, not the whole file.** Everything above the
component is plain JavaScript -- the state names, the tone map and `reading` --
and the component itself is JSX, which node cannot read. So the lift is the text
before `export default function` with the imports dropped, and the slice is
asserted to still hold `reading` rather than assumed to. What it cannot show:
whether the component calls `reading` at all, and what the `useEffect` does with
a failed fetch -- which is what the `asking` state stands for here.

Skipped when node is absent, as `test_theme_resolution.py` skips. Needs no
fastapi, no network, no Ollama and no rebuilt bundle.
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from .jsx_sweep import strip_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_STATUS = REPO_ROOT / "frontend" / "src" / "components" / "ModelStatus.jsx"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Where the plain JavaScript ends and the JSX begins, and the imports that have
# to go with it. Both are asserted to have matched, so a rearranged module fails
# here rather than being run as a slice that no longer holds `reading`.
COMPONENT_STARTS = "export default function"
IMPORT_LINE = re.compile(r"^import .*$", re.MULTILINE)

# The four states, spelled as the module spells them.
ASKING = "asking"
UP = "up"
INCOMPLETE = "incomplete"
DOWN = "down"

# What the label says when the server is fine. The other three add to it.
SERVER = "Ollama server"

# The element the component renders, and the attribute a reader who cannot see
# the dot depends on.
ARIA_LABEL = re.compile(r'aria-label=\{`([^`]*)`\}')
TITLE = re.compile(r'title=\{([^}]*)\}')

# A reply from a server that is up and has everything. The three below it each
# break exactly one thing.
HEALTHY = {"reachable": True, "configured_model": "qwen2.5-coder:7b-instruct",
           "configured_model_pulled": True, "models": [{"name": "qwen2.5-coder:7b-instruct"}],
           "embed_model": "nomic-embed-text:latest", "embed_model_pulled": True}

# What a stopped server answers with: the endpoint is still 200, and the
# sentence is the server's own, which is why it is shown rather than replaced.
SERVER_ERROR = "connection refused to http://localhost:11434"

# The command a reader has to run when the model is missing.
THE_FIX = "ollama pull"


@dataclass(frozen=True)
class Said:
    """What `reading` answered for one reply: the state, the label and the detail."""

    state: str
    label: str
    detail: str


def module_head() -> str:
    """The plain-JavaScript part of the component, with its imports dropped."""
    text = MODEL_STATUS.read_text(encoding="utf-8")
    assert COMPONENT_STARTS in text, f"{MODEL_STATUS.name} declares no component to cut at"
    head, dropped = IMPORT_LINE.subn("", text[: text.index(COMPONENT_STARTS)])
    assert dropped >= 1, f"{MODEL_STATUS.name} no longer imports anything; check this lift"
    assert "function reading" in head, "the lifted head no longer holds `reading`"
    return head


def read(status: dict | None, tmp_path: Path) -> Said:
    """Ask the real `reading` what it would say about one reply from `/api/model`."""
    script = tmp_path / "model_status_probe.mjs"
    script.write_text(
        module_head()
        + "\nconst given = JSON.parse(process.argv[2]);\n"
        "console.log(JSON.stringify(reading(given)));\n",
        encoding="utf-8")
    done = subprocess.run([NODE, str(script), json.dumps(status)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused the module head:\n{done.stderr}"
    return Said(**json.loads(done.stdout))


def reply(**changed) -> dict:
    """A healthy `/api/model` reply with named fields changed."""
    return {**HEALTHY, **changed}


# --- the four states ----------------------------------------------------------

def test_a_page_that_has_not_heard_back_is_asking(tmp_path) -> None:
    """Not `down`: claiming a stopped server before asking is a claim about nothing."""
    assert read(None, tmp_path).state == ASKING


def test_a_reachable_server_with_its_model_is_up(tmp_path) -> None:
    """Non-vacuity for the three below: something has to reach the good state."""
    assert read(reply(), tmp_path).state == UP


def test_a_server_that_did_not_answer_is_down(tmp_path) -> None:
    """The only state that says the server is stopped, and it needs `reachable: false`."""
    assert read(reply(reachable=False, error=SERVER_ERROR), tmp_path).state == DOWN


def test_a_server_missing_the_configured_model_is_incomplete_and_not_down(
        tmp_path) -> None:
    """Up, and unable to finish an audit: two different facts, and the page keeps both."""
    said = read(reply(configured_model_pulled=False), tmp_path)
    assert said.state == INCOMPLETE
    assert said.state != DOWN


def test_all_four_states_are_reachable_and_distinct(tmp_path) -> None:
    """A branch that collapsed into another would leave a state nothing can produce."""
    states = [read(None, tmp_path).state,
              read(reply(), tmp_path).state,
              read(reply(configured_model_pulled=False), tmp_path).state,
              read(reply(reachable=False, error=SERVER_ERROR), tmp_path).state]
    assert sorted(states) == sorted({ASKING, UP, INCOMPLETE, DOWN})


# --- what the label says ------------------------------------------------------

def test_the_label_is_bare_when_the_server_is_working(tmp_path) -> None:
    """Nothing to act on, so nothing is said: a coloured dot is the whole report."""
    assert read(reply(), tmp_path).label == SERVER


def test_every_other_state_names_itself_in_the_label(tmp_path) -> None:
    """The states with something to act on keep their word, since a dot is not actionable."""
    for status in (None, reply(configured_model_pulled=False),
                   reply(reachable=False, error=SERVER_ERROR)):
        label = read(status, tmp_path).label
        assert label.startswith(SERVER)
        assert label != SERVER, status


# --- and what the detail behind it says ---------------------------------------

def test_a_stopped_server_shows_its_own_sentence(tmp_path) -> None:
    """The server names the fix; a friendlier sentence written here would say less."""
    assert SERVER_ERROR in read(reply(reachable=False, error=SERVER_ERROR), tmp_path).detail


def test_a_stopped_server_with_no_sentence_still_says_something(tmp_path) -> None:
    """`error` is nullable, and `undefined` rendered into a tooltip is an empty tooltip."""
    assert read(reply(reachable=False), tmp_path).detail


def test_a_missing_model_is_told_how_to_pull_it(tmp_path) -> None:
    """The one state a reader can clear themselves, so the detail is the command."""
    said = read(reply(configured_model_pulled=False), tmp_path)
    assert THE_FIX in said.detail
    assert HEALTHY["configured_model"] in said.detail


def test_a_working_server_reports_the_model_and_the_embeddings(tmp_path) -> None:
    """Two models decide whether a run can finish, so the healthy detail names both."""
    said = read(reply(), tmp_path).detail
    assert HEALTHY["configured_model"] in said
    assert HEALTHY["embed_model"] in said


def test_an_unpulled_embedding_model_is_said_without_changing_the_state(tmp_path) -> None:
    """Retrieval degrades to ungrounded advice; the audit still runs, so the state stays `up`."""
    said = read(reply(embed_model_pulled=False), tmp_path)
    assert said.state == UP
    assert "not pulled" in said.detail


# --- the state reaches a reader who cannot see the colour ---------------------

def test_the_element_carries_both_halves_in_its_aria_label() -> None:
    """The visible text no longer names the state, so this attribute is the only place it is."""
    found = ARIA_LABEL.search(strip_comments(MODEL_STATUS.read_text(encoding="utf-8")))
    assert found, f"{MODEL_STATUS.name} builds no aria-label this test can read"
    assert "said.label" in found.group(1)
    assert "said.detail" in found.group(1)


def test_the_tooltip_carries_the_detail() -> None:
    """For a reader who can see it: the same sentence, by hover rather than by screen reader."""
    found = TITLE.search(strip_comments(MODEL_STATUS.read_text(encoding="utf-8")))
    assert found, f"{MODEL_STATUS.name} sets no title this test can read"
    assert "said.detail" in found.group(1)
