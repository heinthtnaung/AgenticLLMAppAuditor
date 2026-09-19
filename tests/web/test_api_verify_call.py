"""The request `verifyDraft` really makes, run as the page's own code under node.

`api.js` is the one place the UI talks to the backend, and a call in it is three
things that can be wrong independently: the path, the method, and the body. A
text scan can read all three as characters; running the function reads them as
the request a browser would send -- including what `JSON.stringify` and
`encodeURIComponent` do to them, which is where the `[object Object]` defect
`test_jsx_draft_fetch_key.py` records came from.

**It runs the module, it does not read it.** `api.js` imports nothing, so it
lifts whole into a `.mjs` exactly as `theme.js` does in
`test_theme_resolution.py`, under a `fetch` stub that records what it was asked
for instead of sending it. Nothing here opens a socket: a stub that tried would
fail rather than reach the network, and the assertion is on what was recorded.

**The sibling is asserted beside it on purpose.** `saveDraft` and `verifyDraft`
differ in method, path and body, and a verify that had been written by copying
the save would be a `PUT` to the key itself -- which is the request every frozen
field exists to refuse. Holding the two apart is what says they are two acts.

What this cannot show: whether any component calls `verifyDraft`, or what it
does with the answer. `test_jsx_key_verify.py` reads the component; **no test in
this suite renders React**, and that gap is recorded rather than papered over.

Skipped when node is absent, as the theme and vexctl tests skip. Needs no
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
               body: (options && options.body) || null,
               headers: (options && options.headers) || null });
  return { ok: true, status: 200, json: async () => ({ app: "demo-app" }) };
};
"""

# One expression per run, then everything the stub was asked for.
DRIVER = """
const answer = await (%s);
console.log(JSON.stringify({ calls, answer }));
"""

# The app the stubbed reply names. It comes back in the envelope because the
# server reads it off the run record -- it is never something the page sends.
ANSWERED_APP = "demo-app"

# A run id in the shape the server issues. A key is addressed by the run that
# drafted it, not by the app: the app name is read off the record, so a caller
# cannot name a run and some other app's key.
RUN_ID = "d" * 32
CHECKED_BY = "Quokka Reviewer"

# A run id with characters a URL path may not carry raw. No run the server
# issues looks like this and `key_scope` refuses it outright; the page must not
# be the thing that sends it, which is a guard on the page and not on the id.
AWKWARD_RUN_ID = "demo run/../secret"

VERIFY_PATH = f"/api/runs/{RUN_ID}/key/verify"
SAVE_PATH = f"/api/runs/{RUN_ID}/key"

# How many separators the path has when the name is one segment. An encoded name
# adds none; a raw one adds three and the route the request reaches is not this
# one at all.
PATH_SEPARATORS = VERIFY_PATH.count("/")


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


def verify_call(tmp_path: Path, run_id: str = RUN_ID, name: str = CHECKED_BY) -> dict:
    """The request `verifyDraft(runId, name)` makes."""
    return one_call(f'verifyDraft({json.dumps(run_id)}, {json.dumps(name)})', tmp_path)


# --- the request it makes -----------------------------------------------------

def test_it_posts_to_the_verify_path(tmp_path) -> None:
    """The route is `POST /api/runs/{id}/key/verify`, and nothing else answers there."""
    assert verify_call(tmp_path)["path"] == VERIFY_PATH


def test_it_is_a_post(tmp_path) -> None:
    """A save is a PUT to the key; recording a check is a POST to a path of its own."""
    assert verify_call(tmp_path)["method"] == "POST"


def test_the_body_carries_the_name_under_the_field_the_route_reads(tmp_path) -> None:
    """`Verification` has one field. A body under any other name is an empty claim, refused."""
    assert json.loads(verify_call(tmp_path)["body"]) == {"verified_by": CHECKED_BY}


def test_the_body_carries_nothing_else(tmp_path) -> None:
    """Said as an equality above, and why: a `verified_date` sent here would be ignored.

    The route stamps the date from the server's own clock, so a page that sent
    one would be writing a field that silently never lands -- a request whose
    author believes it does something.
    """
    assert list(json.loads(verify_call(tmp_path)["body"])) == ["verified_by"]


def test_it_announces_json(tmp_path) -> None:
    """FastAPI parses the body by content type; without this the claim is not read at all."""
    assert verify_call(tmp_path)["headers"]["Content-Type"] == "application/json"


def test_the_run_id_is_encoded_into_the_path(tmp_path) -> None:
    """An id stays one path segment, so it can never select a route of its own.

    The page is the first of two guards and `run_routes.RUN_ID` -- which
    `key_scope` checks against before any join -- is the second. Counted as
    separators rather than searched for as text: an id carrying `/` raw would
    still end in `/verify` and still not contain itself literally, and the
    request would be going somewhere else entirely.
    """
    path = verify_call(tmp_path, run_id=AWKWARD_RUN_ID)["path"]
    assert path.count("/") == PATH_SEPARATORS
    assert path.endswith("/verify")


def test_an_ordinary_id_is_not_mangled(tmp_path) -> None:
    """Guard on the encoding above: an id needing none comes through as itself."""
    assert verify_call(tmp_path)["path"] == VERIFY_PATH


def test_an_empty_name_is_still_sent_for_the_server_to_refuse(tmp_path) -> None:
    """The refusal is the server's, so the page does not decide what a name is.

    The button is disabled on an empty name -- `test_jsx_key_verify.py` holds
    that -- but a disabled button is a convenience and not a rule. The one place
    the rules live is `run_record.auditor_refusals`.
    """
    assert json.loads(verify_call(tmp_path, name="")["body"]) == {"verified_by": ""}


# --- and the sibling it is not ------------------------------------------------

def test_saving_a_draft_is_a_put_to_the_key_itself(tmp_path) -> None:
    """The contrast that makes the tests above mean something: two acts, two requests."""
    made = one_call(f'saveDraft({json.dumps(RUN_ID)}, {{ findings: [] }})', tmp_path)
    assert (made["path"], made["method"]) == (SAVE_PATH, "PUT")


def test_the_two_calls_send_different_bodies(tmp_path) -> None:
    """A verify written by copying the save would post the whole key, frozen fields and all."""
    saved = json.loads(one_call(f'saveDraft({json.dumps(RUN_ID)}, {{ findings: [] }})',
                                tmp_path)["body"])
    assert list(saved) == ["key"]
    assert "key" not in json.loads(verify_call(tmp_path)["body"])


def test_the_reply_is_handed_back_to_the_caller(tmp_path) -> None:
    """The route answers the whole envelope, and the editor re-renders the key from it."""
    assert call(f'verifyDraft({json.dumps(RUN_ID)}, {json.dumps(CHECKED_BY)})',
                tmp_path)["answer"] == {"app": ANSWERED_APP}
