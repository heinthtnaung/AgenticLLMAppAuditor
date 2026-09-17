"""A name in the URL never becomes a path of the caller's choosing.

`web/key_draft_store.py` is the one place `DRAFTED_KEYS_DIR` is joined, and it
is joined with a name that arrived over the wire. That is the whole subject
here: `grading_keys/` holds the answers this tool is scored against, so a name
that escaped the drafts folder would let anyone reaching the port read or
rewrite the project's own measurements.

**The traversal case is not what it looks like, and the tests say which is which.**
A percent-encoded `../` never reaches the store at all: Starlette matches one
path segment, and a decoded `/` means no route matches, so it is a routing 404
carrying Starlette's own `Not Found`. What *does* reach `APP_NAME` is a
single-segment name with characters the pattern excludes -- a backslash
traversal is the example with teeth, since it is a path separator on the
platform `pathlib` would join it on. Both are asserted by the *detail* they
answer with, because a test that only counted 404s could not tell a guard that
fired from a route that was never matched.

**Two 404s that are not the same fact.** A name the pattern excludes never
reaches a join at all -- "no draft has that name", the guard. A well-formed name
nobody drafted is 404 naming the app: looked, found nothing. Read as one, a
guard that stopped firing would look like an app nobody had drafted.

A draft that is *there* and unreadable is a 400 and a different file:
`test_key_draft_corruption.py`.

**And a "draft" is a file, which is not the same as a name that matches.** Both
the listing and the read test `is_file()`, because a *directory* called
`<app>.ground_truth.json` matches the glob exactly as a key does -- it would be
offered as a draft to correct and then fail on being opened. The same filter and
the same reason as `grading_keys.discover_graded_apps`.

**The folder it joins is a claim about the module, not about a value.**
`DRAFTED_KEYS_DIR` is bound here and nowhere else under `web/`. It was bound in
two places for a day -- the listing globbed `key_routes`' copy while every read
and write used this one -- and a fixture redirecting one of the two would have
listed a temporary folder and written into a real draft. So what is asserted is
the count, by parsing the imports: a second binding coming back fails here.

Driven through the routes rather than by calling the store directly: it raises
`HTTPException`, so its refusals only mean something as the status and detail a
caller actually sees.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import ast
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import key_draft_store                                        # noqa: E402
from keys import grading_keys                                 # noqa: E402
from keys.grading_keys import GROUND_TRUTH_SUFFIX              # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    APP, KEYS_ENDPOINT, NO_SUCH_DRAFT, client_over, plant, planted_client)

# Two 404s that mean different things. The first is the store's own guard; the
# second is Starlette answering that nothing matched at all.
NO_SUCH_NAME = "no draft has that name"
NOT_FOUND = "Not Found"

# Names that reach the handler and are refused by `APP_NAME`. The backslash is
# the one with teeth: it is a path separator where `pathlib` would join it.
BACKSLASH_TRAVERSAL = "..%5C..%5Csecret"
A_NAME_WITH_A_SPACE = "demo app"
OVER_LONG_NAME = "a" * 101

# A percent-encoded `../`, which is decoded to a path with a separator in it and
# so matches no route. It never reaches the guard.
ENCODED_TRAVERSAL = "%2e%2e%2f%2e%2e%2fsecret"

# A name that matches the glob and is not a key: a directory somebody made, or
# a checkout left behind. The listing and the read both have to skip it.
A_DIRECTORY_APP = "not-really-a-draft"

# Where the one binding of the drafts folder has to live, and the name of it.
OWNING_MODULE = "key_draft_store.py"
DRAFTS_FOLDER = "DRAFTED_KEYS_DIR"
WEB = Path(__file__).resolve().parents[2] / "web"


def modules_binding(name: str) -> list[str]:
    """Every module under `web/` that imports one name into its own namespace.

    Parsed rather than grepped: a name in a docstring or a comment is not a
    binding, and it is the binding a `monkeypatch.setattr` has to find.
    """
    found = []
    for path in sorted(WEB.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = any(alias.name == name
                       for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                       for alias in node.names)
        if imported:
            found.append(path.name)
    return found


# --- the names that are not drafts ---------------------------------------------

def test_an_app_with_no_draft_is_a_404_naming_it(monkeypatch, tmp_path) -> None:
    """A well-formed name for a key nobody drafted: found nothing, rather than refused."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    response = client.get(f"{KEYS_ENDPOINT}/never-drafted")
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == "no drafted key for never-drafted"


@pytest.mark.parametrize("name", [BACKSLASH_TRAVERSAL, A_NAME_WITH_A_SPACE, OVER_LONG_NAME])
def test_a_name_the_pattern_excludes_is_refused_before_any_path_is_joined(
        monkeypatch, tmp_path, name: str) -> None:
    """`APP_NAME` is checked first, so the name never reaches `key_path` at all."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    response = client.get(f"{KEYS_ENDPOINT}/{name}")
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == NO_SUCH_NAME


def test_an_encoded_traversal_never_reaches_the_guard_because_no_route_matches(
        monkeypatch, tmp_path) -> None:
    """Asserted by the detail, not the status: this is Starlette, not `APP_NAME`.

    A decoded `%2f` is a path separator, and `/api/keys/{app_name}` matches one
    segment. Worth pinning as a separate fact, because "the traversal was
    refused" reads as though the guard had run, and a change to the route's
    path -- to `{app_name:path}`, say -- would silently make that the only
    thing standing in front of a filesystem join.
    """
    client, _drafts = planted_client(monkeypatch, tmp_path)
    response = client.get(f"{KEYS_ENDPOINT}/{ENCODED_TRAVERSAL}")
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == NOT_FOUND


def test_a_name_of_dots_alone_stays_inside_the_drafts_folder(
        monkeypatch, tmp_path) -> None:
    """`..` does match `APP_NAME` -- dots are legal in an app name -- and joins to a filename.

    Not a hole, and worth saying why: `key_path` appends the suffix, so the
    name reached is `...ground_truth.json` inside the folder, not its parent.
    """
    client, drafts = planted_client(monkeypatch, tmp_path)
    response = client.get(f"{KEYS_ENDPOINT}/%2e%2e")
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == "no drafted key for .."
    assert sorted(path.name for path in drafts.parent.iterdir()) == ["demo-app", "drafts"]


# --- the folder it joins, and the fact that only it joins it -------------------

def test_exactly_one_module_under_web_binds_the_drafts_folder() -> None:
    """The cause, not the symptom: two bindings is what unhooks a test's redirection.

    A fixture points one module's copy at `tmp_path`; a second module reading
    its own copy goes on reading `grading_keys/drafts/` in the checkout, where
    real drafts live. That happened, and what caught it was an `AttributeError`
    -- a symptom of the shape, not the shape itself.
    """
    assert modules_binding(DRAFTS_FOLDER) == [OWNING_MODULE]


def test_the_scan_can_see_a_binding_at_all() -> None:
    """Guard: a parser that found nothing would make the equality above a claim about zero."""
    assert modules_binding("HTTPException") != []
    assert DRAFTS_FOLDER in (WEB / OWNING_MODULE).read_text(encoding="utf-8")


def test_the_folder_it_joins_is_not_the_published_one() -> None:
    """The feature's whole boundary: a published key is never what these routes open."""
    assert key_draft_store.DRAFTED_KEYS_DIR.parent == grading_keys.KEYS_DIR
    assert key_draft_store.DRAFTED_KEYS_DIR.name == "drafts"


# --- a name that matches and is not a file -------------------------------------

def test_a_directory_named_like_a_key_is_not_listed_as_a_draft(
        monkeypatch, tmp_path) -> None:
    """The glob matches a directory too, so the listing filters on `is_file`.

    Listed, it would be offered as a draft to correct and every route would then
    fail on opening it -- a name in the page that leads nowhere.
    """
    drafts = plant(tmp_path)
    (drafts / f"{A_DIRECTORY_APP}{GROUND_TRUTH_SUFFIX}").mkdir()
    client = client_over(monkeypatch, drafts)
    assert client.get(KEYS_ENDPOINT).json()["drafts"] == [APP]


def test_a_directory_named_like_a_key_is_not_readable_as_one_either(
        monkeypatch, tmp_path) -> None:
    """The other half of the same filter: 404, not a traceback out of `read_text`."""
    drafts = plant(tmp_path)
    (drafts / f"{A_DIRECTORY_APP}{GROUND_TRUTH_SUFFIX}").mkdir()
    client = client_over(monkeypatch, drafts)
    response = client.get(f"{KEYS_ENDPOINT}/{A_DIRECTORY_APP}")
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == f"no drafted key for {A_DIRECTORY_APP}"


def test_the_real_draft_beside_it_is_still_listed(monkeypatch, tmp_path) -> None:
    """Non-vacuity: the filter drops the directory and keeps the file."""
    drafts = plant(tmp_path)
    client = client_over(monkeypatch, drafts)
    assert client.get(KEYS_ENDPOINT).json()["drafts"] == [APP]
