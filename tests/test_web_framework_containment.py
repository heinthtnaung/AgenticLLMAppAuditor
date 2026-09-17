"""No module under `src/` imports anything that could serve HTTP.

The sibling of `test_web_containment.py`, and a different question. That file
asks whether anything under `src/` can reach the wrapper's *own* modules; this
one asks whether anything under `src/` can reach the *framework* those modules
are built on. A module that wrote `from fastapi import FastAPI` and served its
own routes would never spell the word "web", so it would pass that sweep without
a word while making `src/` a tree that accepts connections.

Why it is a file of its own rather than three more lines in
`tests/parsing/test_offline_containment.py`, whose subject is the same guarantee:
that file already runs to 186 lines and rule 18 puts the ceiling at roughly 200.
It also matches imports against a fixed set of *client* modules --
`urllib.request`, `socket`, `http.client`, `requests` -- which is the outbound
half. A server is the inbound half: `uvicorn` opens a listening socket without
any of those four appearing in the importing module.

Five package names, not one. `fastapi` is what a route would be declared with,
`starlette` is the ASGI layer underneath it that can serve an application on its
own, and `uvicorn` is the server that binds the port. The last two need no
install at all: `http.server` and `socketserver` are in the standard library,
and eight lines of either stand up a listening socket. Without them a module
could serve HTTP from `src/` and pass this sweep *and* the outbound one in
`tests/parsing/test_offline_containment.py`, whose `NETWORK_IMPORTS` names
`http.client` and not `http.server` -- while `README.md` says nothing under
`src/` accepts a connection. Any one of the five is the violation.

What the two stdlib names catch is the spelling, and the spellings are
`import http.server`, `from http.server import ...`, `import socketserver` and
`from socketserver import ...`. `from http import server` binds the same module
under a bare `http`, which the scanner reports as `http` and this list does not
name -- so that one spelling would pass. Naming `http` instead would forbid
`http.client` from this file too, which is the outbound half and already
`test_offline_containment.py`'s to refuse; the guards are kept to one subject
each rather than made to overlap.

Nothing here starts a server or imports a framework. Every test reads the
source, so each answers "could it?" rather than "did it?".
"""

from pathlib import Path

from ast_scan import modules_importing, module_name, source_files
from conftest import SRC_DIR

# What a module would have to import to accept a connection: the routing
# framework, the ASGI toolkit under it, the server that binds the port, and the
# two standard-library modules that need none of the three.
WEB_FRAMEWORK_PACKAGES = ("fastapi", "starlette", "uvicorn",
                          "http.server", "socketserver")

# A floor under the walk, so an emptied or mis-rooted sweep cannot pass by
# looking at nothing. `src/` is 90-odd modules; this only rules out a walk of
# one file, or none.
MINIMUM_SRC_MODULES = 50
SCANNED_MODULE = "main.py"

# One planted importer per package, to prove each name in the list really fires.
PLANTED_IMPORTER = "importer.py"
PLANTED_FASTAPI = "from fastapi import FastAPI\n"
PLANTED_STARLETTE = "from starlette.applications import Starlette\n"
PLANTED_UVICORN = "import uvicorn\n"
PLANTED_HTTP_SERVER = "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
PLANTED_SOCKETSERVER = "import socketserver\n"

# A floor under the list itself: an emptied tuple would make the sweep return
# an empty set over any tree at all, and every claim below would still pass.
MINIMUM_FORBIDDEN_PACKAGES = 5


def modules_serving_http(root: Path = SRC_DIR) -> set[str]:
    """The modules under a tree that import any of the five server packages."""
    found: set[str] = set()
    for package in WEB_FRAMEWORK_PACKAGES:
        found |= modules_importing(package, root)
    return found


def plant_importer(tmp_path: Path, source: str) -> Path:
    """Write a throwaway tree holding one module that imports a framework."""
    (tmp_path / PLANTED_IMPORTER).write_text(source, encoding="utf-8")
    return tmp_path


def test_no_source_module_imports_a_web_framework() -> None:
    """The claim, asserted as an exact empty set over all of `src/`."""
    assert modules_serving_http() == set()


def test_the_whole_source_tree_was_walked() -> None:
    """Guard: an empty set proves nothing if the sweep looked at one file, or none."""
    walked = {module_name(path) for path in source_files()}
    assert len(walked) >= MINIMUM_SRC_MODULES
    assert SCANNED_MODULE in walked


def test_that_the_sweep_would_notice_a_fastapi_importer(tmp_path) -> None:
    """Mutation check: plant a module that declares a route and see the sweep name it."""
    assert modules_serving_http(plant_importer(tmp_path, PLANTED_FASTAPI)) == {PLANTED_IMPORTER}


def test_that_the_sweep_would_notice_a_starlette_importer(tmp_path) -> None:
    """Mutation check: the ASGI layer underneath, which serves an application on its own."""
    assert modules_serving_http(plant_importer(tmp_path, PLANTED_STARLETTE)) == {PLANTED_IMPORTER}


def test_that_the_sweep_would_notice_a_uvicorn_importer(tmp_path) -> None:
    """Mutation check: the server that binds the port, imported by bare name."""
    assert modules_serving_http(plant_importer(tmp_path, PLANTED_UVICORN)) == {PLANTED_IMPORTER}


def test_that_the_sweep_would_notice_a_stdlib_http_server_importer(tmp_path) -> None:
    """Mutation check: `http.server` needs nothing installed, so nothing warns you first."""
    assert modules_serving_http(
        plant_importer(tmp_path, PLANTED_HTTP_SERVER)) == {PLANTED_IMPORTER}


def test_that_the_sweep_would_notice_a_socketserver_importer(tmp_path) -> None:
    """Mutation check: the layer `http.server` is built on, which listens on its own."""
    assert modules_serving_http(
        plant_importer(tmp_path, PLANTED_SOCKETSERVER)) == {PLANTED_IMPORTER}


def test_the_list_of_forbidden_packages_is_not_empty() -> None:
    """Guard: an emptied tuple returns an empty set over every tree, planted ones included."""
    assert len(WEB_FRAMEWORK_PACKAGES) >= MINIMUM_FORBIDDEN_PACKAGES
