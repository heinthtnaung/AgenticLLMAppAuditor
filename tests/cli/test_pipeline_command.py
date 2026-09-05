"""A link runs the whole pipeline through main(); a local path never publishes.

Everything past the audit itself is stubbed at the pipeline's seams: the fetch
answers a planted tree, publish is a recorder, Syft and the model come from
cli_helpers. No test clones, launches a process, or opens a socket.
"""

from pathlib import Path

from advisory_fixtures import stub_trivy
from cli_helpers import EMPTY_SCAN, run_cli, stub_syft
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from fetch_helpers import NAME, URL
from pipeline_helpers import (
    point_download_root, record_fetch, record_publish, stub_ai_report, stub_export,
    stub_vex,
)

# One agent surface importing langchain, so a dependency run has a real join.
AGENT_SOURCE = """from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
"""

# What the stubbed generator finds: exactly the one declared package.
SCAN = {"components": [{"type": "library", "name": "langchain", "version": "0.3.25"}]}


def write_app(directory: Path, with_manifest: bool) -> Path:
    """Write the tiny LLM app into `directory`, declaring its package if asked."""
    directory.mkdir(parents=True)
    (directory / "main.py").write_text(AGENT_SOURCE, encoding="utf-8")
    if with_manifest:
        (directory / PYPI_MANIFEST).write_text("langchain==0.3.25\n", encoding="utf-8")
    return directory


def fetched_app(monkeypatch, tmp_path: Path, with_manifest: bool) -> Path:
    """Plant the tree a fetch would return, and stub the fetch to hand it back."""
    root = point_download_root(monkeypatch, tmp_path)
    tree = write_app(root / NAME, with_manifest)
    record_fetch(monkeypatch, result=tree)
    return tree


def test_a_link_publishes_once_with_no_advisory_pin(monkeypatch, tmp_path) -> None:
    """No advisory data was read, so publish is told advisories_read=False, once."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    fetched_app(monkeypatch, tmp_path, with_manifest=False)
    publishes = record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts) == 0
    assert publishes == [(artifacts / NAME, False)]


def test_a_link_publishes_with_advisories_read_when_a_pin_exists(monkeypatch,
                                                                 tmp_path) -> None:
    """With Trivy's snapshot stubbed in, the pin exists and publish is told so."""
    stub_syft(monkeypatch, SCAN)
    stub_trivy(monkeypatch)
    fetched_app(monkeypatch, tmp_path, with_manifest=True)
    publishes = record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts) == 0
    assert publishes == [(artifacts / NAME, True)]


def test_a_local_path_never_publishes(monkeypatch, tmp_path) -> None:
    """A directory argument stays the pure offline audit: publish is never reached."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    repo = write_app(tmp_path / "local-app", with_manifest=False)
    publishes = record_publish(monkeypatch)
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts") == 0
    assert publishes == []


def test_a_refused_refetch_is_a_message_not_a_traceback(monkeypatch, tmp_path,
                                                        capsys) -> None:
    """fetch's FileExistsError reaches main() as exit 1 and one line on stderr."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    point_download_root(monkeypatch, tmp_path)
    record_fetch(monkeypatch, error=FileExistsError(
        f"{tmp_path / 'fetched' / NAME} already exists; a fetch never writes "
        "over anything it did not create. Remove it, or fetch somewhere else"))
    assert run_cli(monkeypatch, URL, tmp_path / "artifacts") == 1
    printed = capsys.readouterr().err
    assert "error:" in printed
    assert "already exists" in printed
    assert "Traceback" not in printed


def test_a_local_run_still_writes_eleven_artifacts(monkeypatch, tmp_path, capsys) -> None:
    """The local contract test_main_dependencies owns survives the pipeline stubs."""
    stub_syft(monkeypatch, SCAN)
    repo = write_app(tmp_path / "tiny-app", with_manifest=True)
    publishes = record_publish(monkeypatch)
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts") == 0
    assert "wrote 11 artifacts" in capsys.readouterr().out
    assert publishes == []


def test_a_failing_ai_report_stage_cannot_change_the_runs_exit_code(monkeypatch,
                                                                    tmp_path) -> None:
    """The whole claim of that stage being a bonus, held through main() rather than asserted.

    Publish runs for real here -- the other tests replace it with a recorder --
    so the last stage's refusal has to travel the same path a user's would.
    """
    stub_syft(monkeypatch, EMPTY_SCAN)
    fetched_app(monkeypatch, tmp_path, with_manifest=False)
    stub_vex(monkeypatch)
    exported = stub_export(monkeypatch)
    stub_ai_report(monkeypatch, error=ValueError("page names advisories not in the report"))
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts) == 0
    assert exported == [artifacts / NAME], "the authoritative export still ran"
