"""The auditor reports; it never edits, patches or runs the code it audits.

`.claude/AGENTS.md` and `README.md` have promised this in prose since Phase 1,
and `docs/PHASE_3_PLAN.md` adds that nothing executes the audited app. Both are
asserted here by running the real CLI and hashing the repository underneath it
before and after. A grep over `src/` would miss a write through a path added
later; hashing the tree cannot. The structural half -- that no source module can
commit, merge or install anything -- is in test_no_write_commands.py.
"""

import hashlib
import runpy
import shutil
from pathlib import Path

import pytest

from cli_helpers import EMPTY_SCAN, forbid_subprocesses, read_artifact, run_cli, stub_syft
from conftest import CORPUS_APPS, app_path, require_corpus
from main import SURFACES_NAME

# A repository's own history is not audited content, so it is skipped if a
# downloaded fixture happens to carry one.
GIT_DIR = ".git"

# The synthetic app: one file holding a surface to find, and one that would
# leave a mark on disk if anything ever executed it.
AGENT_FILE = "agent.py"
AGENT_SOURCE = """from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
"""
AGENT_SURFACE_NAME = "AgentExecutor.from_agent_and_tools"

TRIPWIRE_FILE = "tripwire.py"
TRIPWIRE_MARKER = "the-app-was-executed"
TRIPWIRE_SOURCE = f"""from pathlib import Path

Path(__file__).with_name({TRIPWIRE_MARKER!r}).write_text("ran", encoding="utf-8")
"""

TRIPWIRE_APP = "tripwire-app"

# What an auto-fixing tool would leave behind, used to prove the hashes notice.
PATCH_FILE = "auditor.patch"


def hash_tree(root: Path) -> dict[str, str]:
    """Return one SHA-256 per file under a directory, keyed by relative path."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and GIT_DIR not in path.parts
    }


def audit(monkeypatch: pytest.MonkeyPatch, repo: Path, tmp_path: Path) -> int:
    """Run a whole audit over a repository, with the SBOM generator stubbed out."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    return run_cli(monkeypatch, repo, tmp_path / "artifacts")


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_auditing_a_corpus_app_leaves_it_byte_identical(app, monkeypatch, tmp_path) -> None:
    """The load-bearing one: a full audit adds, removes and changes no file in corpus/."""
    require_corpus(app)
    repo = app_path(app)
    before = hash_tree(repo)
    assert before, f"{app} hashed to nothing, so this proves nothing"
    assert audit(monkeypatch, repo, tmp_path) == 0
    assert hash_tree(repo) == before


def test_a_write_into_a_copy_of_a_corpus_app_is_detected(tmp_path) -> None:
    """Mutation check: the test above only means something if a write breaks it.

    Done on a copy, never on `corpus/` itself, which no test may write to.
    """
    app = CORPUS_APPS[0]
    require_corpus(app)
    copy = tmp_path / app
    shutil.copytree(app_path(app), copy)
    before = hash_tree(copy)
    (copy / PATCH_FILE).write_text("patched by the auditor", encoding="utf-8")
    assert hash_tree(copy) != before


def test_hash_tree_notices_a_new_file(tmp_path) -> None:
    """A file the audit left behind changes the hashes, even if nothing was edited."""
    (tmp_path / "kept.py").write_text("kept\n", encoding="utf-8")
    before = hash_tree(tmp_path)
    (tmp_path / "patch.diff").write_text("added\n", encoding="utf-8")
    assert hash_tree(tmp_path) != before


def test_hash_tree_notices_a_removed_file(tmp_path) -> None:
    """A deletion changes the hashes too, so a destructive run cannot pass either."""
    (tmp_path / "kept.py").write_text("kept\n", encoding="utf-8")
    (tmp_path / "removed.py").write_text("gone soon\n", encoding="utf-8")
    before = hash_tree(tmp_path)
    (tmp_path / "removed.py").unlink()
    assert hash_tree(tmp_path) != before


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_auditing_a_corpus_app_starts_no_process(app, monkeypatch, tmp_path) -> None:
    """With the generator stubbed, a full audit launches nothing at all."""
    require_corpus(app)
    forbid_subprocesses(monkeypatch)
    assert audit(monkeypatch, app_path(app), tmp_path) == 0


def write_tripwire_app(tmp_path: Path) -> Path:
    """Write a repository holding one surface to find and one file that marks disk if run."""
    repo = tmp_path / TRIPWIRE_APP
    repo.mkdir()
    (repo / AGENT_FILE).write_text(AGENT_SOURCE, encoding="utf-8")
    (repo / TRIPWIRE_FILE).write_text(TRIPWIRE_SOURCE, encoding="utf-8")
    return repo


def test_the_audited_app_is_read_and_never_executed(monkeypatch, tmp_path) -> None:
    """Phase 3 is static: the audited app's own code never runs, so no marker appears."""
    repo = write_tripwire_app(tmp_path)
    assert audit(monkeypatch, repo, tmp_path) == 0
    assert not (repo / TRIPWIRE_MARKER).exists()


def test_the_unexecuted_app_still_had_its_surface_found(monkeypatch, tmp_path) -> None:
    """Reading beats running: the agent surface is reported without the file being run."""
    repo = write_tripwire_app(tmp_path)
    audit(monkeypatch, repo, tmp_path)
    document = read_artifact(tmp_path / "artifacts", TRIPWIRE_APP, SURFACES_NAME)
    assert [(r["file"], r["name"]) for r in document["surfaces"]] == [
        (AGENT_FILE, AGENT_SURFACE_NAME)
    ]


def test_the_tripwire_marks_disk_when_it_really_is_executed(tmp_path) -> None:
    """Mutation check: the absent marker is evidence only if running the file writes one."""
    repo = write_tripwire_app(tmp_path)
    runpy.run_path(str(repo / TRIPWIRE_FILE))
    assert (repo / TRIPWIRE_MARKER).read_text(encoding="utf-8") == "ran"
