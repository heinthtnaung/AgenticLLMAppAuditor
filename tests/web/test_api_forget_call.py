"""The request `forgetRun` really makes, run as the page's own code under node.

One line of `api.js` decides whether the history page destroys a row or reads
one, and the failure is silent in the worst direction: `ask(path)` with no
second argument is a **GET**, so a `forgetRun` that forgot its options object
would fetch the run, get a 200 with the record in it, resolve happily, and the
page would count it as forgotten. The run would still be there on the next
re-read, and nothing anywhere would have said no.

So the method is read off a request rather than off the source. `api.js` imports
nothing, so it lifts whole into a `.mjs` under a `fetch` stub that records what
it was asked for -- the arrangement `test_api_verify_call.py` established and
`test_theme_resolution.py` before it. Nothing here opens a socket.

**The sibling is asserted beside it on purpose**, exactly as the save and the
verify are: `fetchRun` and `forgetRun` build the *same path* and differ only in
the method. A delete written by copying the read is the one mistake that leaves
both functions looking right.

**And it sends no body.** `DELETE /api/runs/{run_id}` takes none -- the id is in
the path and the run's status is the server's to check -- so a body would be
data the route does not read, on the one endpoint that destroys something.

What this cannot show: that anything calls `forgetRun`, or what the page does
with the answer. `test_jsx_forget_report.py` reads the page; **no test in this
suite renders React**, and that gap is recorded rather than papered over.

Skipped when node is absent, as the theme and verify-call tests skip. Needs no
fastapi, no network and no rebuilt bundle.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API = REPO_ROOT / "frontend" / "src" / "api.js"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# A `fetch` that records the request and answers as the backend would. `ask`
# reads `response.ok` and `response.json()`, so the stub keeps both.
FETCH_STUB = """
const calls = [];
globalThis.fetch = async (path, options) => {
  calls.push({ path, method: (options && options.method) || "GET",
               body: (options && options.body) || null });
  return { ok: true, status: 200, json: async () => ({ forgotten: "ok" }) };
};
"""

# One expression per run, then everything the stub was asked for.
DRIVER = """
const answer = await (%s);
console.log(JSON.stringify({ calls, answer }));
"""

# A real run id: 32 lowercase hex, which is the only shape the route accepts.
RUN_ID = "0123456789abcdef0123456789abcdef"

RUN_PATH = f"/api/runs/{RUN_ID}"

# What the server answered, so the reply is shown to reach the caller rather
# than being swallowed.
THE_REPLY = {"forgotten": "ok"}


def call(expression: str, tmp_path: Path) -> dict:
    """Run one expression against the real module, and return what fetch was asked for."""
    script = tmp_path / "api_probe.mjs"
    script.write_text(FETCH_STUB + API.read_text(encoding="utf-8") + DRIVER % expression,
                      encoding="utf-8")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused {expression}:\n{done.stderr}"
    return json.loads(done.stdout)


def one_call(expression: str, tmp_path: Path) -> dict:
    """The single request one call made, insisting there was exactly one."""
    made = call(expression, tmp_path)["calls"]
    assert len(made) == 1, f"expected one request, got {len(made)}"
    return made[0]


def forget_call(tmp_path: Path) -> dict:
    """The request `forgetRun(runId)` makes."""
    return one_call(f"forgetRun({json.dumps(RUN_ID)})", tmp_path)


# --- the request it makes -------------------------------------------------------

def test_the_method_is_delete(tmp_path) -> None:
    """The one assertion this file exists for: without an options object `ask` defaults to GET."""
    assert forget_call(tmp_path)["method"] == "DELETE"


def test_it_addresses_the_runs_own_path(tmp_path) -> None:
    """`/api/runs/{id}`: the same path the poll uses, which is why the method carries everything."""
    assert forget_call(tmp_path)["path"] == RUN_PATH


def test_it_sends_no_body(tmp_path) -> None:
    """The id is in the path and the status is the server's to check; a body is data nobody reads."""
    assert forget_call(tmp_path)["body"] is None


# --- and the read beside it is still a read ------------------------------------

def test_reading_a_run_is_a_get_to_the_same_path(tmp_path) -> None:
    """The sibling: two functions, one path, and the method is the entire difference."""
    read = one_call(f"fetchRun({json.dumps(RUN_ID)})", tmp_path)
    assert (read["path"], read["method"]) == (RUN_PATH, "GET")


def test_the_two_calls_differ_only_in_their_method(tmp_path) -> None:
    """Non-vacuity on the pair: a delete written by copying the read is what this catches."""
    forget = forget_call(tmp_path)
    read = one_call(f"fetchRun({json.dumps(RUN_ID)})", tmp_path)
    assert forget["path"] == read["path"]
    assert forget["method"] != read["method"]


def test_the_reply_is_handed_back_to_the_caller(tmp_path) -> None:
    """The page reads nothing out of it, but a function that swallowed it could not be used."""
    assert call(f"forgetRun({json.dumps(RUN_ID)})", tmp_path)["answer"] == THE_REPLY
