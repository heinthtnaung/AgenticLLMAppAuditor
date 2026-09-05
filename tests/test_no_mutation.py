"""The auditor reports; it never edits, patches or runs the code it audits.

`.claude/AGENTS.md` and `README.md` have promised this in prose since Phase 1,
and `docs/PHASE_3_PLAN.md` adds that nothing executes the audited app. Both are
asserted here by running the real CLI and hashing the repository underneath it
before and after. A grep over `src/` would miss a write through a path added
later; hashing the tree cannot. The structural half -- that no source module can
commit, merge or install anything -- is in test_no_write_commands.py.

**The audited tree is written by this test**, by `mixed_app_fixtures` plus one
extra file. It used to be the pinned corpus, which was removed, so its inputs
were chosen by the same author as the code. What that gives up: no oversized
file, no non-UTF-8 source, no malformed source of either language, no read-only
file, no symlink, no dependency manifest -- the generator is stubbed, so
nothing here exercises what a real Syft run does to a tree -- and no unforeseen
code shape, so a write triggered only by one of those would not be caught here.
What remains is the guarantee itself, exercised end to end over a real
mixed-language tree: both parsing backends run, and one file would mark disk if
anything ever executed it.
"""

import hashlib
import runpy
import shutil
from pathlib import Path

import pytest

from cli_helpers import EMPTY_SCAN, forbid_subprocesses, read_artifact, run_cli, stub_syft
from mixed_app_fixtures import (
    AGENT_SURFACE_LINE,
    AGENT_SURFACE_NAME,
    APP_NAME,
    MIXED_APP_SURFACES,
    PYTHON_FILE,
    write_mixed_app,
)
from outputs import SURFACES_NAME
from parsing.languages import PYTHON, TYPESCRIPT

# A repository's own history is not audited content, so it is skipped if the
# tree under test happens to carry one.
GIT_DIR = ".git"

# The one file added to the mixed-language app: it would leave a mark on disk
# if anything ever executed it.
TRIPWIRE_FILE = "tripwire.py"
TRIPWIRE_MARKER = "the-app-was-executed"
TRIPWIRE_SOURCE = f"""from pathlib import Path

Path(__file__).with_name({TRIPWIRE_MARKER!r}).write_text("ran", encoding="utf-8")
"""

# The mixed app's Python and TypeScript files plus the tripwire, so a tree that
# hashed to nothing cannot pass as unchanged.
TRIPWIRE_APP_FILES = 3

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


def write_tripwire_app(tmp_path: Path) -> Path:
    """Write the mixed-language app plus one file that marks disk if it is ever run."""
    repo = write_mixed_app(tmp_path)
    (repo / TRIPWIRE_FILE).write_text(TRIPWIRE_SOURCE, encoding="utf-8")
    return repo


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


def test_auditing_a_repository_leaves_it_byte_identical(monkeypatch, tmp_path) -> None:
    """The load-bearing one: a full audit adds, removes and changes no file under the tree."""
    repo = write_tripwire_app(tmp_path)
    before = hash_tree(repo)
    assert len(before) == TRIPWIRE_APP_FILES, "the tree hashed to nothing: this proves nothing"
    assert audit(monkeypatch, repo, tmp_path) == 0
    assert hash_tree(repo) == before


def test_a_write_into_the_audited_repository_is_detected(tmp_path) -> None:
    """Mutation check: the test above only means something if a write breaks it."""
    repo = write_tripwire_app(tmp_path)
    before = hash_tree(repo)
    (repo / PATCH_FILE).write_text("patched by the auditor", encoding="utf-8")
    assert hash_tree(repo) != before


def test_a_write_into_a_copy_of_the_repository_is_detected(tmp_path) -> None:
    """The same over a copied tree, so a deep write is caught and not only a top-level one."""
    copy = tmp_path / "copied"
    shutil.copytree(write_tripwire_app(tmp_path), copy)
    before = hash_tree(copy)
    assert len(before) == TRIPWIRE_APP_FILES
    (copy / PYTHON_FILE).write_text("# edited by the auditor\n", encoding="utf-8")
    assert hash_tree(copy) != before


def test_auditing_a_repository_starts_no_process(monkeypatch, tmp_path) -> None:
    """With the generator stubbed, a full audit launches nothing at all."""
    repo = write_tripwire_app(tmp_path)
    forbid_subprocesses(monkeypatch)
    assert audit(monkeypatch, repo, tmp_path) == 0


def test_the_audit_that_started_no_process_still_reported_its_surfaces(
        monkeypatch, tmp_path) -> None:
    """Guard: launching nothing is only evidence if the audit did the work anyway."""
    repo = write_tripwire_app(tmp_path)
    forbid_subprocesses(monkeypatch)
    audit(monkeypatch, repo, tmp_path)
    document = read_artifact(tmp_path / "artifacts", APP_NAME, SURFACES_NAME)
    assert len(document["surfaces"]) == MIXED_APP_SURFACES


def test_the_audit_that_started_no_process_read_both_language_backends(
        monkeypatch, tmp_path) -> None:
    """The tree-sitter backend is reached too, so the ban covers more than `ast`."""
    repo = write_tripwire_app(tmp_path)
    forbid_subprocesses(monkeypatch)
    audit(monkeypatch, repo, tmp_path)
    document = read_artifact(tmp_path / "artifacts", APP_NAME, SURFACES_NAME)
    assert {record["language"] for record in document["surfaces"]} == {PYTHON, TYPESCRIPT}


def test_the_audited_app_is_read_and_never_executed(monkeypatch, tmp_path) -> None:
    """Phase 3 is static: the audited app's own code never runs, so no marker appears."""
    repo = write_tripwire_app(tmp_path)
    assert audit(monkeypatch, repo, tmp_path) == 0
    assert not (repo / TRIPWIRE_MARKER).exists()


def test_the_unexecuted_app_still_had_its_agent_surface_found(monkeypatch, tmp_path) -> None:
    """Reading beats running: the agent is reported at its line without the file being run."""
    repo = write_tripwire_app(tmp_path)
    audit(monkeypatch, repo, tmp_path)
    document = read_artifact(tmp_path / "artifacts", APP_NAME, SURFACES_NAME)
    located = {(r["file"], r["line"], r["name"]) for r in document["surfaces"]}
    assert (PYTHON_FILE, AGENT_SURFACE_LINE, AGENT_SURFACE_NAME) in located


def test_the_tripwire_marks_disk_when_it_really_is_executed(tmp_path) -> None:
    """Mutation check: the absent marker is evidence only if running the file writes one."""
    repo = write_tripwire_app(tmp_path)
    runpy.run_path(str(repo / TRIPWIRE_FILE))
    assert (repo / TRIPWIRE_MARKER).read_text(encoding="utf-8") == "ran"
