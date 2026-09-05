"""The index command: chunk a clone, embed, store, pin -- and write nowhere else.

A one-time command, so unlike an audit it does not degrade: an embedder it
cannot reach is an error, because an index half built is worse than none. Every
test runs it against a fake clone under `tmp_path` with the embedder stubbed;
none touches the real `knowledge/` directory.
"""

import json
import sys
from pathlib import Path

import pytest

import index_knowledge
import model_client
from artifacts.remediation import OWASP_CHEATSHEETS
from knowledge_fixtures import (
    CHEATSHEETS,
    FAKE_COMMIT,
    FAKE_EMBED_DIGEST,
    FAKE_EMBED_MODEL,
    build_fake_index,
    stub_embedding,
    write_fake_clone,
)
from retrieval import manifest, store
from retrieval.chunks import chunk_markdown
from retrieval.manifest import (
    MANIFEST_NAME,
    SOURCES,
    content_digest,
    manifest_digest,
    matched_files,
)
from test_no_mutation import hash_tree

# What the fake clone should yield, computed by the same chunker the command uses.
EXPECTED_PASSAGES = sum(len(chunk_markdown(text, OWASP_CHEATSHEETS, path))
                        for path, text in CHEATSHEETS.items())


def files_outside(root: Path, knowledge_dir: Path) -> set[str]:
    """Every file under a tree that is not under the knowledge directory."""
    return {path.relative_to(root).as_posix() for path in root.rglob("*")
            if path.is_file() and knowledge_dir not in path.parents}


def test_the_command_writes_only_under_the_knowledge_directory(monkeypatch, tmp_path: Path) -> None:
    """A sibling directory is hashed before and after; the build leaves it byte-identical and adds nothing beside it."""
    sibling = tmp_path / "elsewhere"
    sibling.mkdir()
    (sibling / "keep.txt").write_text("untouched\n", encoding="utf-8")
    knowledge_dir = tmp_path / "knowledge"
    write_fake_clone(knowledge_dir)
    before = (hash_tree(sibling), files_outside(tmp_path, knowledge_dir))
    stub_embedding(monkeypatch)
    index_knowledge.build(knowledge_dir, FAKE_EMBED_MODEL)
    assert (hash_tree(sibling), files_outside(tmp_path, knowledge_dir)) == before


def test_the_command_returns_the_manifest_path_and_the_passage_count(monkeypatch, tmp_path) -> None:
    """Both results are what the CLI prints, so a reader knows what was written and how much."""
    knowledge_dir = tmp_path / "knowledge"
    write_fake_clone(knowledge_dir)
    stub_embedding(monkeypatch)
    assert index_knowledge.build(knowledge_dir, FAKE_EMBED_MODEL) == (
        knowledge_dir / MANIFEST_NAME, EXPECTED_PASSAGES)


def test_the_manifest_pins_the_clones_commit_and_content(monkeypatch, tmp_path: Path) -> None:
    """The commit is read from `.git` without a process, and the digest covers the indexed files."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    clone = knowledge_dir / OWASP_CHEATSHEETS
    [source] = json.loads((knowledge_dir / MANIFEST_NAME).read_text(encoding="utf-8"))["sources"]
    assert source["upstream_commit"] == FAKE_COMMIT
    assert source["content_digest"] == content_digest(clone, matched_files(clone, SOURCES[OWASP_CHEATSHEETS]))
    assert (source["file_count"], source["indexed_passage_count"]) == (len(CHEATSHEETS), EXPECTED_PASSAGES)


def test_the_manifest_pins_the_embed_model_and_the_database_version(monkeypatch, tmp_path) -> None:
    """The model, its digest and the chromadb that wrote the index are what the probe compares."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    manifest = json.loads((knowledge_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert (manifest["embed_model"], manifest["embed_model_digest"], manifest["chromadb_version"]) == (
        FAKE_EMBED_MODEL, FAKE_EMBED_DIGEST, store.chromadb_version())


def test_the_index_records_the_digest_of_the_manifest_as_written(monkeypatch, tmp_path) -> None:
    """Digested first, written last: the pin in the index matches the file on disk exactly."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    text = (knowledge_dir / MANIFEST_NAME).read_text(encoding="utf-8")
    pins = store.open_store(knowledge_dir).pins()
    assert pins == {manifest.MANIFEST_DIGEST_KEY: manifest_digest(text),
                    manifest.CHROMADB_VERSION_KEY: store.chromadb_version(),
                    manifest.EMBED_MODEL_KEY: FAKE_EMBED_MODEL}


def test_the_built_index_reopens_holding_every_passage(monkeypatch, tmp_path: Path) -> None:
    """What the command counted is what a later open finds."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    assert store.open_store(knowledge_dir).count() == EXPECTED_PASSAGES


def test_a_missing_clone_is_refused(monkeypatch, tmp_path: Path) -> None:
    """No `.git` under the source's name means the user has not cloned it; the error names the path."""
    stub_embedding(monkeypatch)
    with pytest.raises(FileNotFoundError, match=str(tmp_path / OWASP_CHEATSHEETS)):
        index_knowledge.build(tmp_path, FAKE_EMBED_MODEL)


def test_a_clone_matching_no_files_is_refused(monkeypatch, tmp_path: Path) -> None:
    """A clone with none of the included files is incomplete, not an empty knowledge base."""
    write_fake_clone(tmp_path, files={"README.md": "not a cheat sheet"})
    stub_embedding(monkeypatch)
    with pytest.raises(ValueError, match="matches none of"):
        index_knowledge.build(tmp_path, FAKE_EMBED_MODEL)


def test_an_unreachable_embedder_is_an_error_not_a_degraded_index(monkeypatch, tmp_path) -> None:
    """The one-time command raises; a half-built index would be mistaken for a whole one."""
    write_fake_clone(tmp_path)
    monkeypatch.setattr(model_client, "model_digest", lambda model=None: FAKE_EMBED_DIGEST)

    def refuse(texts, model=None):
        """Fail the way an unreachable server does."""
        raise RuntimeError("cannot reach the local model server")
    monkeypatch.setattr(model_client, "embed", refuse)
    with pytest.raises(RuntimeError, match="cannot reach"):
        index_knowledge.build(tmp_path, FAKE_EMBED_MODEL)
    assert not (tmp_path / MANIFEST_NAME).exists()


def test_the_cli_reports_success_with_the_count(monkeypatch, tmp_path: Path, capsys) -> None:
    """Exit 0, and the count and the manifest path on stdout."""
    knowledge_dir = tmp_path / "knowledge"
    write_fake_clone(knowledge_dir)
    stub_embedding(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["index_knowledge.py", "--knowledge-dir", str(knowledge_dir)])
    assert index_knowledge.main() == 0
    assert f"indexed {EXPECTED_PASSAGES} passages" in capsys.readouterr().out


def test_the_cli_reports_a_missing_clone_and_exits_nonzero(monkeypatch, tmp_path: Path, capsys) -> None:
    """The refusal reaches the user on stderr as an error line, not a traceback."""
    stub_embedding(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["index_knowledge.py", "--knowledge-dir", str(tmp_path)])
    assert index_knowledge.main() == 1
    assert capsys.readouterr().err.startswith("error: no clone at")
