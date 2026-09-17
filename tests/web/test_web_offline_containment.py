"""The ways the web wrapper could open a socket that running it would not reveal.

The sibling of `tests/parsing/test_offline_containment.py`, for the second tree.
That file states an exact set for `src/` -- two modules may open a connection --
and it is read as a statement about the whole tool. `web/` was outside it, and
outside it is where a `urllib.request` would now be least noticed: the wrapper
already talks to the outside world by *serving*, so one more import would not
look out of place in a diff.

**`GET /api/model` is the case that makes this worth asserting.** It reports
whether Ollama is up, which is a question with an obvious wrong answer: parse
`/api/tags` here. `model_client.py` already parses it, it is one of the two
modules in `src/` allowed to connect at all, and a second copy of that format in
a second tree is the defect this project already records about the JSX
rebuilding a probe id. So the route calls `model_client.list_models`, and the
two directions are asserted together below -- nothing here opens a connection,
and the module that needs one imports the client that may.

Nothing here runs the server or imports fastapi. Every test reads the source, so
each answers "could it?" rather than "did it?" -- which is the only way to ask
about a path no test walks.
"""

from pathlib import Path

from ast_scan import (
    imported_modules, module_name, modules_importing, parse, source_files)

from . import WEB_DIR

# What a module would have to import to open one, copied from the `src/` guard
# on purpose: two trees held to one rule should be held to the same spelling of
# it. `subprocess` is absent for the same reason there -- starting a program is
# `test_no_write_commands.py`'s subject.
NETWORK_IMPORTS = frozenset({"urllib.request", "socket", "http.client", "requests"})

# The exact set, and it is empty. `web/` serves; it never fetches. Every fact it
# reports about something outside this process is read through a module in
# `src/` that is already allowed to ask.
WEB_NETWORK_MODULES: frozenset[str] = frozenset()

# The client that may, and the one module here that needs it. Stated as an
# exact set in both directions: an empty guard above is satisfied by a wrapper
# that reports nothing at all, and this is what says it reports something.
MODEL_CLIENT = "model_client"
MODEL_CLIENT_READERS = frozenset({"model_routes.py"})

# The function the route calls, rather than a second parse of `/api/tags`.
LISTING_FUNCTION = "list_models"

# A second importer, planted in a fake tree, to prove the search still fires.
PLANTED_IMPORTER = "importer.py"
PLANTED_NETWORK = "import urllib.request\n"

# A floor under the scan: an empty file list satisfies every exact set above
# perfectly. Measured at twelve modules today, well above this.
LEAST_WEB_MODULES = 8

# Modules the wrapper is built from, named so a renamed tree cannot make the
# scan pass by finding nothing.
KNOWN_WEB_MODULES = frozenset({"api.py", "run_routes.py", "model_routes.py",
                               "uploads.py"})


def web_modules() -> list[Path]:
    """Every Python module of the HTTP wrapper."""
    return source_files(WEB_DIR)


def modules_reaching_the_network() -> set[str]:
    """The wrapper's modules that import something able to open a connection."""
    return {module_name(path, WEB_DIR) for path in web_modules()
            if imported_modules(parse(path)) & NETWORK_IMPORTS}


# --- the scan is looking at something ------------------------------------------

def test_the_wrapper_was_actually_scanned() -> None:
    """Guard: the exact sets below say nothing at all if the file list came back empty."""
    found = {module_name(path, WEB_DIR) for path in web_modules()}
    assert len(found) >= LEAST_WEB_MODULES
    assert KNOWN_WEB_MODULES <= found


# --- nothing here opens a connection -------------------------------------------

def test_no_module_of_the_wrapper_can_open_a_network_connection() -> None:
    """Structural, so "the wrapper never fetches" is asserted and not arranged."""
    assert modules_reaching_the_network() == set(WEB_NETWORK_MODULES)


def test_that_search_would_notice_a_module_that_did(tmp_path) -> None:
    """Mutation check: plant one that imports urllib and see the search name it."""
    (tmp_path / PLANTED_IMPORTER).write_text(PLANTED_NETWORK, encoding="utf-8")
    reaching = {module_name(path, tmp_path) for path in source_files(tmp_path)
                if imported_modules(parse(path)) & NETWORK_IMPORTS}
    assert reaching == {PLANTED_IMPORTER}


# --- and the one that needs one asks the client that may ------------------------

def test_the_model_client_is_the_only_way_the_wrapper_reaches_ollama() -> None:
    """One module reads it, and the empty set above is what makes that the *only* route."""
    assert modules_importing(MODEL_CLIENT, WEB_DIR) == set(MODEL_CLIENT_READERS)


def test_the_status_route_asks_for_the_listing_rather_than_parsing_it() -> None:
    """The positive half: it calls the shared function, so there is one parse of `/api/tags`."""
    source = (WEB_DIR / "model_routes.py").read_text(encoding="utf-8")
    assert f"{MODEL_CLIENT}.{LISTING_FUNCTION}(" in source
