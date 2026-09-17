"""Only a `finished` run moves the page, and it moves to the run it was polling.

The audit form watches one run and, when it is over, shows the report. The rule
this file holds is which "over" counts: **`finished` and nothing else**. A run
that `failed` stays on the audit page, where the URL that produced it is still
in the form and the failure is reported beside it -- navigating off a failure
before it is read is how a reason gets lost. A check that only asked "does it
call `navigate`" would pass a regression that redirected on any terminal status,
so what is asserted here is the answer for **every** status in the server's
vocabulary, `RUN_STATUSES`, which is one loop and covers a fourth status the day
`src/` gains one.

**It runs the page's own condition.** The effect is lifted out of
`AuditPage.jsx` by text and evaluated under node against a real run body, with
two of the page's own modules inlined: `runStatus.js` for the words, and the
browser-free half of `router.js` for `runPath` and `routeOf`. Only `navigate` is
stubbed -- it pushes browser history -- and it records what it was handed.

**That is why the second half of the redirect is checkable at all.** The page
navigates with `runId`, the id the 202 answered with, and not with
`record.run_id`: `runPath(undefined)` matches no route, so `routeOf` answers
`audit` and the reader is bounced back to the page they were already on with
nothing said. Both halves are asserted -- the pushed path resolves to the `run`
page, and its id is the one being polled -- against the real `routeOf` rather
than a pattern written here.

**No test in this suite renders React**, a recorded defect this does not close.
Nothing here proves React *runs* the effect, or runs it at the right moment, or
that the dependency array is the one React needs; that last is asserted as text,
which is all text can reach. What is proven is the condition's arithmetic over
every status a run can be in.

Skipped when node is absent, as `test_jsx_stage_states.py` skips. Needs no
fastapi -- `run_record.py` is free of it -- no network and no rebuilt bundle.
"""

import json
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from run_record import FAILED, FINISHED, RUN_STATUSES, RUNNING, body, now, started

from .jsx_sweep import FRONTEND_SRC, strip_comments

PAGE = FRONTEND_SRC / "pages" / "AuditPage.jsx"
VOCABULARY = FRONTEND_SRC / "runStatus.js"
ROUTER = FRONTEND_SRC / "router.js"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# One effect: its body, and the dependency array after it. Neither group may
# cross the `}, [` that closes the body, so the innermost effect is what matches.
EFFECT = re.compile(r"useEffect\(\(\) => \{(.*?)\}, \[([^\]]*)\]\)", re.DOTALL)

# Where `router.js` stops being plain JavaScript: `navigate` is the first
# function in it that touches the browser, and everything above it -- the route
# table, `routeOf`, `runPath` -- is pure.
FIRST_BROWSER_USE = re.compile(r"^export function navigate", re.MULTILINE)

# Import lines, the one the router's pure half is allowed to carry (its hooks,
# which only the part below `navigate` uses), and the `export` keyword that is a
# syntax error in a lifted script.
IMPORT_LINE = re.compile(r"^import .*$", re.MULTILINE)
REACT_IMPORT = 'import { useEffect, useState } from "react";'
EXPORT_KEYWORD = re.compile(r"^export ", re.MULTILINE)

# The page whose name a path resolves to, and the one a bad id would fall back
# to -- `routeOf` answers `audit` for anything it cannot match.
RUN_PAGE = "run"
FALLBACK_PAGE = "audit"

# The run this page is watching, as the 202 answered it: a different id from the
# one inside the record, so a redirect reading the wrong one is visible.
POLLED_RUN_ID = "c0ffee" + "0" * 26
URL = "https://example.invalid/owner/demo-app"
AUDITOR = "Quokka Reviewer"
REASON = "the repository could not be fetched"

# What the probe prints per navigation: the path pushed, and what the page's own
# router makes of it.
PROBE = """
const [record, runId] = JSON.parse(process.argv[2]);
const pushed = [];
const navigate = (path) => pushed.push(path);
(() => {{BODY}})();
console.log(JSON.stringify(pushed.map((path) => ({ path, route: routeOf(path) }))));
"""


def page() -> str:
    """The audit page's own source, comments stripped: they name every status in prose."""
    return strip_comments(PAGE.read_text(encoding="utf-8"))


def effects() -> list[tuple[str, str]]:
    """Every effect the page declares, as its body and its dependency array."""
    found = EFFECT.findall(page())
    assert len(found) == page().count("useEffect("), (
        f"{PAGE.name} declares effects this test's pattern did not read")
    return found


def the_navigating_effect() -> tuple[str, str]:
    """The one effect that moves the page, or say how many there really are."""
    found = [effect for effect in effects() if "navigate(" in effect[0]]
    assert len(found) == 1, f"expected one navigating effect in {PAGE.name}, found {len(found)}"
    return found[0]


def as_script(path: Path, keep_above: re.Pattern | None = None) -> str:
    """One of the page's modules as a plain script: cut, de-imported, de-exported."""
    text = path.read_text(encoding="utf-8")
    if keep_above:
        found = keep_above.search(text)
        assert found, f"{path.name} no longer has the function this lift cuts at"
        text = text[:found.start()]
    assert IMPORT_LINE.findall(text) in ([], [REACT_IMPORT]), (
        f"{path.name} now imports something this lift cannot stand in for")
    return EXPORT_KEYWORD.sub("", IMPORT_LINE.sub("", text))


def probe(record: dict | None, run_id: str | None, tmp_path: Path) -> list[dict]:
    """Run the page's own effect over one run body and return what it pushed."""
    program = (f"{as_script(VOCABULARY)}\n{as_script(ROUTER, FIRST_BROWSER_USE)}\n"
               + PROBE.replace("{BODY}", the_navigating_effect()[0]))
    script = tmp_path / "redirect_probe.mjs"
    script.write_text(program, encoding="utf-8")
    done = subprocess.run([NODE, str(script), json.dumps([record, run_id])],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused the page's own effect:\n{done.stderr}"
    return json.loads(done.stdout)


def a_run(status: str, run_id: str = POLLED_RUN_ID) -> dict:
    """One run body on the wire in the status asked for, built through the record itself."""
    record = replace(started(URL, AUDITOR, {}), run_id=run_id)
    if status != RUNNING:
        failure = {"error": REASON} if status == FAILED else {}
        record = replace(record, status=status, finished_at=now(), seconds=1.0, **failure)
    return body(record, artifacts_present=False, artifacts_current=False, result=None)


# --- which runs move the page -------------------------------------------------

def test_a_finished_run_moves_the_page_to_its_own_run(tmp_path) -> None:
    """The behaviour asked for: the report opens itself once the audit is over."""
    pushed = probe(a_run(FINISHED), POLLED_RUN_ID, tmp_path)
    assert [one["route"] for one in pushed] == [{"page": RUN_PAGE, "runId": POLLED_RUN_ID}]


def test_a_running_run_leaves_the_page_where_it_is(tmp_path) -> None:
    """Every poll while the audit works would otherwise push a history entry."""
    assert probe(a_run(RUNNING), POLLED_RUN_ID, tmp_path) == []


def test_a_failed_run_leaves_the_page_where_it_is(tmp_path) -> None:
    """The decision: a failure is reported where the URL that caused it is still shown."""
    assert probe(a_run(FAILED), POLLED_RUN_ID, tmp_path) == []


def test_no_status_but_finished_moves_the_page(tmp_path) -> None:
    """Over the server's whole vocabulary, so "any terminal status" is not the rule."""
    moved = [status for status in RUN_STATUSES
             if probe(a_run(status), POLLED_RUN_ID, tmp_path)]
    assert moved == [FINISHED]


# --- and never to a run it cannot name ----------------------------------------

def test_a_page_with_no_run_yet_moves_nowhere(tmp_path) -> None:
    """Before the first audit there is no record at all, and `record?.status` is undefined."""
    assert probe(None, None, tmp_path) == []


def test_a_finished_run_whose_id_the_page_never_got_moves_nowhere(tmp_path) -> None:
    """The guard clause: `/runs/undefined` matches no route, so this would bounce silently."""
    assert probe(a_run(FINISHED), None, tmp_path) == []


def test_the_page_moves_to_the_run_it_polled_and_not_to_the_id_in_the_record(
        tmp_path) -> None:
    """Two ids on purpose: the 202's is the one being watched, and the one to open."""
    other = "dec0de" + "1" * 26
    pushed = probe(a_run(FINISHED, run_id=other), POLLED_RUN_ID, tmp_path)
    assert [one["route"]["runId"] for one in pushed] == [POLLED_RUN_ID]


def test_the_path_the_page_pushes_is_one_its_own_router_resolves(tmp_path) -> None:
    """Non-vacuity for the routes above: an unmatched path answers `audit`, not nothing."""
    pushed = probe(a_run(FINISHED), POLLED_RUN_ID, tmp_path)
    assert [one["route"]["page"] for one in pushed] == [RUN_PAGE]
    assert probe(a_run(FINISHED), "not-a-run-id", tmp_path)[0]["route"]["page"] == (
        FALLBACK_PAGE)


# --- the probe really ran the page's own effect -------------------------------

def test_the_page_declares_one_effect_and_it_is_the_one_that_moves_the_page() -> None:
    """Non-vacuity: a body that never called `navigate` would make every check above empty."""
    body_text, _ = the_navigating_effect()
    assert "navigate(" in body_text
    assert len(effects()) >= 1


def test_the_effect_re_reads_both_values_its_condition_rests_on() -> None:
    """Text, not React: an effect that does not depend on the id can fire against a stale one."""
    _, dependencies = the_navigating_effect()
    assert "status" in dependencies
    assert "runId" in dependencies


def test_the_router_half_this_probe_inlines_is_the_browser_free_one() -> None:
    """Guard on the lift: `navigate` and `useRoute` touch `window`, which node has not."""
    lifted = as_script(ROUTER, FIRST_BROWSER_USE)
    assert "window" not in lifted
    assert "function routeOf" in lifted and "function runPath" in lifted
