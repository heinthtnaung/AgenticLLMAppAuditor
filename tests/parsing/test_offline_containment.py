"""The ways a socket could open that running the audit would not reveal.

The sibling of `test_offline.py`, and a different kind of assertion. That file
performs the audit with every socket refused and counts the attempts, which
proves the paths it walks. This one closes the gap it cannot: a new module
importing `urllib` on a path no test walks, a new module importing chromadb, or
a third-party default left switched on in a process this one cannot watch.

Nothing here runs an audit. Every test reads the source or a setting, so each
answers "could it?" rather than "did it?" -- and the two files together are the
guarantee.
"""

import importlib.util
import os
from pathlib import Path

from ast_scan import imported_modules, module_name, parse, source_files
from conftest import SRC_DIR
from deps import syft_runner
from retrieval import store

WORKFLOW_SOURCE = SRC_DIR / "checks" / "workflow.py"

# The two settings that would send a trace of the audit to LangSmith.
TRACING_VARIABLES = ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2")

# The only module that opens a network connection *in this process*, and it
# talks to Ollama on this machine. `fetch_repo` is deliberately absent: it
# reaches a remote, but it does so by launching git, so the connection is a
# child process's and never this one's. Which programs may be launched is
# asserted by test_no_write_commands.py, so the two guards meet without
# overlapping -- and together they say the auditor's own process opens nothing
# but a local model socket.
NETWORK_MODULES = frozenset({"model_client.py"})

# What a module would have to import to open one. `subprocess` is absent on
# purpose: it starts a program, and which programs may be started is asserted
# by test_no_write_commands.py rather than duplicated here.
NETWORK_IMPORTS = frozenset({"urllib.request", "socket", "http.client", "requests"})


# The one module that may import chromadb, and the package name that counts as
# importing it. Named because `store.py`'s docstring, `requirements.txt`,
# `docs/HISTORY.md` and `knowledge/README.md` all make this claim, and until
# now none of them was backed by a test.
CHROMADB = "chromadb"
CHROMADB_MODULES = frozenset({"retrieval/store.py"})

# A second importer, planted in a fake tree, to prove the search still fires.
PLANTED_IMPORTER = "importer.py"
PLANTED_CHROMADB = "from chromadb.config import Settings\n"

# The other direction: modules that may *not* import the model client. Named
# rather than allowlisted, because the modules that legitimately call the model
# grow with each phase while these two must never join them.
#
# `checks/planner.py` turns a model's opinion into a check order, which is
# exactly the shape of a module that would call one. It does not: the model
# arrives as an argument and is called at the edge in `run_checks`, the way
# `checks/advise.py` takes its retriever. `checks/workflow.py` is the graph that
# order is walked by, and a model call inside a node would fail
# `test_offline.py`, which counts socket *attempts* -- but only along the paths
# it walks. This says the same thing on every path, including ones no test runs.
#
# `checks/semantic_probe.py` is the third and the sharpest case, because it is
# the only check whose whole job is asking the model a question. Its purity is
# what makes that safe: `model_ask_fn` is a parameter, `main.probe_inputs` is
# the one place `model_client.ask` is handed to it, and absent that argument the
# check returns nothing at all. An import here would let the module reach the
# server on its own -- from inside `workflow.audit`, where the graph must
# attempt no socket -- whatever its callers pass.
MODEL_CLIENT = "model_client"
MODEL_CLIENT_FREE_MODULES = frozenset({"checks/planner.py", "checks/workflow.py",
                                       "checks/semantic_probe.py"})
PLANTED_MODEL_CLIENT = "import model_client\n"


def test_the_vector_store_is_told_not_to_phone_home() -> None:
    """Chroma's telemetry is a setting, so it is asserted like Syft's update check above."""
    assert store.CLIENT_SETTINGS.anonymized_telemetry is False


def modules_importing(package: str, root: Path = SRC_DIR) -> set[str]:
    """The modules under a tree that import a package, by its name or any submodule."""
    return {module_name(path, root) for path in source_files(root)
            if any(name == package or name.startswith(f"{package}.")
                   for name in imported_modules(parse(path)))}


def modules_importing_chromadb(root: Path = SRC_DIR) -> set[str]:
    """The modules under a tree that import chromadb, by the package or any submodule."""
    return modules_importing(CHROMADB, root)


def test_only_the_named_module_imports_chromadb() -> None:
    """The containment four documents claim, asserted the way the socket one above is.

    It is what lets `retrieval/retrieve.py` import the store inside a function:
    an audit with no index never pays chromadb's half-second import, and no
    caller ever handles a chromadb error, because `StoreError` is raised at
    this one boundary.
    """
    assert modules_importing_chromadb() == set(CHROMADB_MODULES)


def test_that_containment_would_notice_a_second_importer(tmp_path) -> None:
    """Mutation check: plant a module that imports chromadb and see the search name it."""
    (tmp_path / PLANTED_IMPORTER).write_text(PLANTED_CHROMADB, encoding="utf-8")
    assert modules_importing_chromadb(tmp_path) == {PLANTED_IMPORTER}


def test_only_the_named_modules_can_open_a_network_connection() -> None:
    """Structural, so "nothing else opens a socket" is asserted, not arranged.

    The socket tests above prove the paths they exercise; this one closes the
    gap they cannot -- a new module importing urllib on a path no test walks.
    The AST scanners come from ast_scan.py rather than being copied, because
    two copies of a scanner is how the two copies come to disagree.
    """
    reaching = {module_name(path) for path in source_files()
                if imported_modules(parse(path)) & NETWORK_IMPORTS}
    assert reaching == set(NETWORK_MODULES)


def test_the_sbom_generator_is_told_not_to_phone_home() -> None:
    """Syft runs in its own process, so its update check is disabled by environment.

    A blocked socket in this process would prove nothing about a subprocess;
    this setting is what actually keeps the SBOM step offline.
    """
    assert syft_runner.SYFT_ENV["SYFT_CHECK_FOR_APP_UPDATE"] == "false"


def reimport_the_workflow() -> None:
    """Re-run the module's import-time tracing opt-out, whatever the environment now says."""
    spec = importlib.util.spec_from_file_location("workflow_reimported", WORKFLOW_SOURCE)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))


def test_importing_the_workflow_leaves_langsmith_tracing_off() -> None:
    """The opt-out is taken by importing the module, not by anything a caller must remember."""
    reimport_the_workflow()
    assert [os.environ[name] for name in TRACING_VARIABLES] == ["false", "false"]


def test_the_tracing_opt_out_overrules_an_environment_that_asked_for_tracing(monkeypatch) -> None:
    """Offline is the tool's guarantee, so an inherited `true` must not switch tracing back on.

    A machine that develops LangChain apps commonly exports these already. If
    one of them survives into an audit, langsmith uploads each node's input and
    output -- the audited repository's paths and code identifiers -- to
    api.smith.langchain.com, which is exactly the breach this file exists to
    prevent.
    """
    for name in TRACING_VARIABLES:
        monkeypatch.setenv(name, "true")
    reimport_the_workflow()
    assert [os.environ[name] for name in TRACING_VARIABLES] == ["false", "false"]


def test_the_planner_the_graph_and_the_probe_never_import_the_model_client() -> None:
    """The structural half of "the model is consulted at the edge, never inside the loop".

    A planner that imported the client could call it from a graph node, and the
    audit would open a socket on a path no test happens to walk. Injection is
    what keeps `checks/planner.py` a pure function of its arguments, and this is
    what keeps injection from quietly becoming optional. The semantic probe is
    held to it too: the check that most obviously wants the model is the one
    that must never fetch it for itself.
    """
    assert modules_importing(MODEL_CLIENT) & MODEL_CLIENT_FREE_MODULES == set()


def test_that_the_model_client_search_would_notice_an_importer(tmp_path) -> None:
    """Mutation check: plant a module importing the client and see the search name it."""
    (tmp_path / PLANTED_IMPORTER).write_text(PLANTED_MODEL_CLIENT, encoding="utf-8")
    assert modules_importing(MODEL_CLIENT, tmp_path) == {PLANTED_IMPORTER}


def test_the_modules_barred_from_the_model_client_are_modules_that_exist() -> None:
    """Guard: a renamed module would make the bar above pass by naming nothing."""
    assert {module_name(path) for path in source_files()} >= MODEL_CLIENT_FREE_MODULES
