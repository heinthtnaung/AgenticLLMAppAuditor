"""Running the auditor's CLI from a test, and stubbing the generator it calls.

Several test files drive the CLI or its dependency rules. The argv shim, the
`<artifacts-dir>/<app>/<name>` layout, the Syft stub and the subprocess ban are
spelled once here, so a change to any of them is a change in one place.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import model_client
from artifacts.remediation import KNOWLEDGE_NOT_INDEXED, NO_INDEX, knowledge_provenance
from deps import syft_runner, trivy_runner
from main import main
from retrieval import retrieve

# A snapshot's pin, for tests that hand build_findings advisory data directly.
STUB_ADVISORY_PIN = {
    "advisory_generator_name": "trivy",
    "advisory_generator_version": "0.0.0-stub",
    "advisory_db_updated_at": "2026-01-01T00:00:00Z",
}

# What the stubbed generator reports its own version as. Any string would do;
# this is the one the recorded corpus scans were taken from.
STUB_GENERATOR_VERSION = "1.51.0"

# A scan that found nothing, for the tests that never get as far as scanning.
EMPTY_SCAN = {"components": []}


def run_cli(monkeypatch: pytest.MonkeyPatch, repo_path: Path, artifacts_dir: Path,
            advice: str | None = None, flags: tuple[str, ...] = ()) -> int:
    """Run the CLI once with the given repo, artifacts directory and optional flags.

    The model is stubbed by default. An audit asks it to advise on every
    finding, so leaving it real would make each CLI test wait on a server, and
    make the suite depend on whether Ollama is up and what it said today --
    the same trap `stub_syft` records having fallen into. Pass `advice=None`
    after stubbing the model yourself to exercise a different path.

    `flags` is how an opt-in reaches the parser -- `--semantic-probe` is the
    only one today, and it is the one flag that changes what the audit asks a
    server for, so a test drives it through argparse rather than around it.
    """
    if advice is not None or not _model_already_stubbed():
        stub_model(monkeypatch, advice if advice is not None else STUB_ADVICE)
    stub_knowledge(monkeypatch)
    argv = ["main.py", str(repo_path), "--artifacts-dir", str(artifacts_dir), *flags]
    monkeypatch.setattr(sys, "argv", argv)
    return main()


def _model_already_stubbed() -> bool:
    """Say whether a caller has replaced the model call before running the CLI."""
    return getattr(model_client.ask, "__name__", "") != "ask"


def stub_knowledge(monkeypatch: pytest.MonkeyPatch, knowledge: dict | None = None,
                   store: object | None = None) -> None:
    """Force every CLI run to advise ungrounded, whatever this machine has indexed.

    The same lesson as `stub_syft`: left real, these tests would depend on
    whether the person running them happens to have built a knowledge index,
    and a grounded run cites passages a fixture cannot predict.

    A caller may name its own `knowledge` block instead -- an indexed one, for
    a test about what an index-present run records. The store stays None by
    default, which is a legal grounding rather than a shortcut: the index was
    open for the run and this finding retrieved nothing from it, so no ChromaDB
    and no embedding server are needed to produce that state.

    A caller wanting a run that really retrieves passes a `store` -- anything
    with the one method the retriever calls, `query(vector, k)`. Then the two
    arguments have to agree, because the document builder refuses an entry
    citing a passage no index was open for, and `stub_model` has to be in place
    too, since a grounded finding embeds its own query text.
    """
    block = knowledge if knowledge is not None else knowledge_provenance(
        KNOWLEDGE_NOT_INDEXED, NO_INDEX)
    monkeypatch.setattr(retrieve, "probe", lambda *_args, **_kwargs: retrieve.Grounding(
        store, block, "stub-embed-model"))


def stub_syft(monkeypatch: pytest.MonkeyPatch, scan_result: dict) -> None:
    """Replace every Syft call, so no subprocess runs and no tool is required.

    All three are patched, `is_available` included. An earlier copy of this
    stub left that one real, which quietly made six offline tests depend on
    whether the machine running them happened to have Syft installed.
    """
    monkeypatch.setattr(syft_runner, "is_available", lambda: True)
    monkeypatch.setattr(syft_runner, "scan", lambda app_dir: scan_result)
    monkeypatch.setattr(syft_runner, "generator_version", lambda: STUB_GENERATOR_VERSION)
    # And the advisory generator OFF, for the same recorded lesson: left real,
    # every one of these tests would depend on whether this machine has Trivy
    # and a cached database -- and would start a real subprocess to boot.
    monkeypatch.setattr(trivy_runner, "is_available", lambda: False)


def read_artifact(artifacts_dir: Path, app: str, name: str) -> dict:
    """Read one artifact a run left under <artifacts-dir>/<app>/."""
    return json.loads((artifacts_dir / app / name).read_text(encoding="utf-8"))


def forbid_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to start a process fail the test."""
    def boom(*args, **kwargs) -> None:
        """Fail the test rather than let a real process start."""
        raise AssertionError(f"the auditor started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)


# What the stubbed model answers: prose and one generic snippet, so the accepted
# path is exercised without a server.
STUB_ADVICE = ("Treat the value as data rather than as instruction, and put any "
               "tool it can reach behind a check.\n\n```python\nsafe = validate(value)\n```")
# Bare hex, the way Ollama's `/api/tags` reports a digest and so the way
# `model_client.model_digest` hands one back. A `sha256:` prefix here would
# make the report's twelve-character shortening render as the prefix plus five
# hex characters, and invite a "fix" to code that is already right.
STUB_MODEL_DIGEST = "9f2c4d1a8b3e7605" + "0" * 48

# What the stubbed embedding call answers with, one vector per text. Its value
# never matters: the fake stores these tests query ignore the vector and answer
# with a fixed passage, so nothing depends on where it points.
STUB_EMBEDDING = [1.0, 0.0, 0.0]


def stub_model(monkeypatch: pytest.MonkeyPatch, answer: str = STUB_ADVICE) -> None:
    """Replace the model call, so no server is required and no test waits on one.

    The same lesson as `stub_syft` above: an unstubbed call makes a test depend
    on whether the machine running it happens to have Ollama up, and on what a
    model said that day. The contract's refusal rules are tested directly
    against `judge`, so nothing here needs a real answer to be meaningful.
    """
    # All three take the optional `model` the real signatures take: the AI report
    # asks a different local model, and the retriever asks for the embedding
    # model's digest and for vectors, so a stub that accepted neither would fail
    # on the call rather than on the answer. `embed` is stubbed here because it
    # is the third call this client makes to the server, and a grounded run
    # makes it once per finding.
    monkeypatch.setattr(model_client, "ask", lambda prompt, model=None: answer)
    monkeypatch.setattr(model_client, "model_digest", lambda model=None: STUB_MODEL_DIGEST)
    monkeypatch.setattr(model_client, "embed",
                        lambda texts, model=None: [STUB_EMBEDDING for _ in texts])


def stub_model_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every model call fail the way an unreachable server does."""
    def refuse(*_args, **_kwargs):
        raise RuntimeError("cannot reach the local model server (stubbed)")
    monkeypatch.setattr(model_client, "ask", refuse)
    monkeypatch.setattr(model_client, "model_digest", refuse)
    # `embed` too, or "every model call" would be three calls minus one, and a
    # grounded run would reach a real server from a test about an absent one.
    monkeypatch.setattr(model_client, "embed", refuse)
