"""`web/` is outside `src/`, and nothing under `src/` imports it.

The HTTP wrapper in `web/` is the one place in this repository that *accepts* a
connection. It is not part of the tool -- it drives the auditor from outside,
through `main.run`, the same direction `experiments/` runs in -- and `web/api.py`
states both halves of that as a claim. This file is the test that claim says
exists.

Why it must be outside `src/` at all, rather than merely tidy there: `src/`
makes four exact-set promises -- four modules may start a process, two may open
a connection, nine are commands, none imports the study -- and each is read as a
statement about the whole tree. A module under `src/` that listened on a socket
would make "nothing else opens a socket" false in fact while
`test_offline_containment.py` stayed green, because that guard names import
spellings and not behaviour. A guarantee that degrades silently is worse than
one narrowed deliberately.

Why it is not folded into `test_experiments_containment.py`, whose shape this
copies: that file's subject is the study and its cloud client, and two subjects
in one file is how a reader stops knowing what either one promises. The sibling
claim -- that no module under `src/` imports anything that could serve HTTP,
fastapi and the standard library's own `http.server` alike -- lives in
`test_web_framework_containment.py`, because a module could import a server
without ever writing the word "web".

The set of forbidden names is read out of `web/` rather than written down, and
that is the point. `web/serve.py` puts `web/` on `sys.path` and then imports its
own modules by bare name (`from api import app`, `from audit_request import
AuditRequest`), so a module under `src/` could reach them the same way and never
write the word "web". Deriving the names from the files actually present means a
new file dropped into `web/` is guarded from the moment it lands.

The cost of deriving them: a name collision would be reported as a violation. If
a file named `config.py` were ever added to `web/`, a `src/` module importing its
own `config` would fail this sweep. That is the safe direction to be wrong in,
and the fix is to rename the wrapper's file.

Nothing here starts a server, imports fastapi or opens anything. Every test
reads the source or the directory listing, so each answers "could it?" rather
than "did it?".
"""

from pathlib import Path

from ast_scan import imported_modules, module_name, parse, source_files
from conftest import REPO_ROOT, SRC_DIR

# The wrapper, and the package name a `from web import ...` would spell.
WEB_DIR = REPO_ROOT / "web"
WEB_PACKAGE = "web"

# The five modules present when this guard was written, named so the sweep
# cannot pass by finding an empty or moved directory. `web/` holds ten as of
# 2026-09-09, and `tests/web/test_import_path_bootstrap.py` is where the whole
# folder is read off disk rather than listed. This is a floor, not the whole
# set: a further file is covered by the derivation above without editing the
# list -- which is why `page` went unlisted here for a while, and why the
# comparison stays `>=`.
KNOWN_WEB_MODULES = frozenset({"api", "artifacts_read", "audit_request", "page", "serve"})

# A floor under the walk of `src/`, so an emptied or mis-rooted sweep cannot
# pass by looking at nothing. The same guard `test_web_framework_containment.py`
# carries, and for the same reason: every claim in this file below is an empty
# set, and an empty set is what a walk of no files returns. `src/` is 90-odd
# modules; this only rules out a walk of one, or none.
MINIMUM_SRC_MODULES = 50
SCANNED_MODULE = "main.py"

# Two planted importers, one per spelling, to prove the sweep fires on a real
# violation rather than on nothing at all.
PLANTED_FILE = "planted.py"
PLANTED_BARE_IMPORT = "import audit_request\n"
PLANTED_PACKAGE_IMPORT = "from web.artifacts_read import read_documents\n"


def web_import_names(root: Path = WEB_DIR) -> set[str]:
    """Every name a module could import the wrapper by: the package, and each file's stem."""
    return {WEB_PACKAGE} | {path.stem for path in source_files(root)}


def modules_reaching_the_web_wrapper(root: Path = SRC_DIR,
                                     names: frozenset[str] | None = None) -> set[str]:
    """The modules under a tree that import the wrapper, by package name or by bare stem."""
    forbidden = names if names is not None else frozenset(web_import_names())
    return {module_name(path, root) for path in source_files(root)
            if any(name.split(".")[0] in forbidden
                   for name in imported_modules(parse(path)))}


def test_web_is_a_directory_at_the_repository_root() -> None:
    """The structural half of the claim: the wrapper exists where the README says it does."""
    assert WEB_DIR.is_dir()
    assert WEB_DIR.parent == REPO_ROOT


def test_web_is_not_inside_src() -> None:
    """The other structural half: the wrapper is not part of the tool's source tree."""
    assert SRC_DIR not in WEB_DIR.parents
    assert WEB_DIR != SRC_DIR


def test_the_web_modules_guarded_against_are_present() -> None:
    """Non-vacuity: the sweep below has the five named modules to find, not an empty folder."""
    assert web_import_names() >= KNOWN_WEB_MODULES


def test_the_launcher_that_binds_the_socket_is_one_of_the_names_derived() -> None:
    """A module really present is really derived, so the sweep cannot pass on nothing.

    `serve.py` is the sharpest one to name: it is the module that calls
    `uvicorn.run`, so it is the file whose reachability from `src/` would turn
    the tool's own offline promise into a statement about spelling.
    """
    assert (WEB_DIR / "serve.py").is_file()
    assert "serve" in web_import_names()


def test_no_source_module_imports_anything_from_the_web_wrapper() -> None:
    """The import half of the claim, asserted as an exact empty set over all of `src/`."""
    assert modules_reaching_the_web_wrapper() == set()


def test_the_whole_source_tree_was_walked() -> None:
    """Guard: an empty set proves nothing if the sweep looked at one file, or none."""
    walked = {module_name(path) for path in source_files()}
    assert len(walked) >= MINIMUM_SRC_MODULES
    assert SCANNED_MODULE in walked


def test_that_the_sweep_would_notice_a_bare_name_import(tmp_path) -> None:
    """Mutation check: `import audit_request` names no folder, and must still be caught."""
    (tmp_path / PLANTED_FILE).write_text(PLANTED_BARE_IMPORT, encoding="utf-8")
    assert modules_reaching_the_web_wrapper(tmp_path) == {PLANTED_FILE}


def test_that_the_sweep_would_notice_a_package_qualified_import(tmp_path) -> None:
    """Mutation check: the other spelling, `from web.artifacts_read import ...`."""
    (tmp_path / PLANTED_FILE).write_text(PLANTED_PACKAGE_IMPORT, encoding="utf-8")
    assert modules_reaching_the_web_wrapper(tmp_path) == {PLANTED_FILE}


def test_that_a_new_file_in_web_is_guarded_without_editing_this_test(tmp_path) -> None:
    """The derivation earns its keep: a stem that is not in the named five is still forbidden."""
    wrapper = tmp_path / WEB_PACKAGE
    wrapper.mkdir()
    (wrapper / "websocket_stream.py").write_text("CHUNK = 4096\n", encoding="utf-8")
    assert "websocket_stream" in web_import_names(wrapper)
