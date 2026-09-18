"""Grouping runs by repository, run as the page's own code under node.

`repoGroup.js` is thirty lines with no imports and two exported functions, and
both are wrong in ways a text sweep cannot see. `test_repo_group_join.py` holds
that the module derives no key of its own -- it groups on the server's
`canonical_repo_url` and never re-implements `canonical_url` in JavaScript --
and this holds what it does with that key.

Three behaviours, each with a consequence:

**Runs of one repository land in one group.** That is the whole feature: the
screenshot that prompted it had thirteen runs of one repository under two
spellings of its URL, which is a page of rows saying the same thing.

**Group order is the server's order, which is newest first.** A `Map` keeps
insertion order, so the group a reader sees first is the one with the most
recent run in it. Sorting by anything else -- a URL alphabetically, say -- would
bury the run somebody has just started at the bottom of the page.

**And a run with no `app` still groups.** A run that failed before it resolved a
tree has no app name at all, and those are exactly the rows a reader wants
beside the successful runs of the same repository rather than in a group of
their own. Keying on `app` would put every failed run of every repository into
one group headed `null`.

`failedIn` is the other half: the runs a group may offer to forget. It takes the
status word as an argument rather than importing it, and the reason is **this
file**: the module has to import nothing at all to lift whole into a `.mjs`, and
an `import { FAILED } from "./runStatus.js"` would end that. Keeping the page to
one copy of the vocabulary is *not* the reason -- importing the constant would
do that too. A test shaping a production signature is worth doing and worth
saying plainly, and `repoGroup.js`'s own docstring now says the same. The words
this file hands it come from `web/run_record.py`, which is where they start.

The module imports nothing, so it lifts whole into a `.mjs`, the way `api.js`
does in `test_api_verify_call.py`. Nothing here renders React or opens a socket.

Skipped when node is absent, as the theme and hook tests skip. Needs no fastapi
and no rebuilt bundle.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from run_record import FAILED, FINISHED

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "frontend" / "src" / "repoGroup.js"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Reads the runs off argv, groups them, and reports each group's key, the run
# ids in it, and which of them `failedIn` selects.
DRIVER = """
const runs = JSON.parse(process.argv[2]);
const status = process.argv[3];
console.log(JSON.stringify(groupRuns(runs).map((group) => ({
  key: group.key,
  runs: group.runs.map((run) => run.run_id),
  failed: failedIn(group, status).map((run) => run.run_id),
}))));
"""

# One repository, and another owned by somebody else with the same last segment
# -- the collision `canonical_url` deliberately does not normalise away.
ONE_REPO = "https://github.com/owner/demo"
ANOTHER_REPO = "https://github.com/somebody-else/demo"


def a_run(run_id: str, repo: str = ONE_REPO, status: str = FINISHED,
          app: str | None = "demo") -> dict:
    """One history row, in the shape `GET /api/runs` serves it."""
    return {"run_id": run_id, "canonical_repo_url": repo, "status": status, "app": app}


def grouped(runs: list[dict], tmp_path: Path, status: str = FAILED) -> list[dict]:
    """Run the real module over these rows and return what it made of them."""
    script = tmp_path / "group_probe.mjs"
    script.write_text(MODULE.read_text(encoding="utf-8") + DRIVER, encoding="utf-8")
    done = subprocess.run([NODE, str(script), json.dumps(runs), status],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused the module:\n{done.stderr}"
    return json.loads(done.stdout)


# --- runs of one repository are one group --------------------------------------

def test_three_runs_of_one_repository_make_one_group(tmp_path) -> None:
    """The feature: thirteen rows saying the same thing become one line a reader can open."""
    made = grouped([a_run("a"), a_run("b"), a_run("c")], tmp_path)
    assert len(made) == 1
    assert made[0]["runs"] == ["a", "b", "c"]


def test_the_group_is_keyed_by_the_served_repository_url(tmp_path) -> None:
    """The header shows this, and it is the value the server sent rather than a derived one."""
    assert grouped([a_run("a")], tmp_path)[0]["key"] == ONE_REPO


def test_two_owners_of_one_name_stay_two_groups(tmp_path) -> None:
    """The collision `canonical_url` refuses to normalise, carried through to the page."""
    made = grouped([a_run("a"), a_run("b", repo=ANOTHER_REPO)], tmp_path)
    assert [group["key"] for group in made] == [ONE_REPO, ANOTHER_REPO]


def test_the_group_order_is_the_order_the_runs_arrived_in(tmp_path) -> None:
    """The server's order is newest first, so the first group holds the most recent run."""
    made = grouped([a_run("a", repo=ANOTHER_REPO), a_run("b"),
                    a_run("c", repo=ANOTHER_REPO)], tmp_path)
    assert [group["key"] for group in made] == [ANOTHER_REPO, ONE_REPO]
    assert made[0]["runs"] == ["a", "c"]


def test_a_run_that_never_resolved_an_app_groups_with_its_repository(tmp_path) -> None:
    """Keyed on the URL, not the app: those rows are the ones a reader most wants together."""
    made = grouped([a_run("a"), a_run("b", status=FAILED, app=None)], tmp_path)
    assert len(made) == 1
    assert made[0]["runs"] == ["a", "b"]


def test_no_runs_make_no_groups(tmp_path) -> None:
    """An empty history is not an error, and the page renders its own empty notice."""
    assert grouped([], tmp_path) == []


# --- and the failed runs are the ones a group may offer to forget --------------

def test_only_the_failed_runs_are_selected(tmp_path) -> None:
    """Every other status is refused 409, so a control offered on one offers a refusal."""
    made = grouped([a_run("a"), a_run("b", status=FAILED),
                    a_run("c", status=FAILED)], tmp_path)
    assert made[0]["failed"] == ["b", "c"]


def test_a_group_with_nothing_failed_selects_nothing(tmp_path) -> None:
    """`[]` is what the header's `failed.length > 0` gate reads, so it has to be empty."""
    assert grouped([a_run("a"), a_run("b")], tmp_path)[0]["failed"] == []


def test_the_selection_follows_the_status_it_is_handed(tmp_path) -> None:
    """Non-vacuity: a function returning every run would satisfy the first check above.

    The word comes from `runStatus.js` in the page. Handing a different one here
    shows the argument is read, rather than a status matched inside the module.
    """
    made = grouped([a_run("a"), a_run("b", status=FAILED)], tmp_path, status=FINISHED)
    assert made[0]["failed"] == ["a"]
