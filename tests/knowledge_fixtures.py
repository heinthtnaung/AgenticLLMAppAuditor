"""Shared Phase 6 test data: a fake clone, a fake embedder, and synthetic vectors.

No retrieval test may need Ollama, the network, or the real clone
under `knowledge/`. So the clone is two small cheat sheets behind a hand-written
`.git/HEAD`, the embedder is a hash turned into three floats, and the vectors
handed to the store are axis-aligned so "nearest" has an answer a reader can
check by eye. Spelled once here, because four test files build the same index.

Two ways in, both shared: `build_fake_index` runs the real index command over
the fake clone, and `build_index` fills a store directly with the sample
vectors. `tests/retrieval/test_store.py` uses the second for what the store
does and `tests/retrieval/test_store_offline.py` uses it for what the store
must not do, so it lives here rather than in one of them with a copy in the
other.
"""

import hashlib
from pathlib import Path

import pytest

import index_knowledge
import model_client
from artifacts.remediation import OWASP_CHEATSHEETS
from retrieval import store
from retrieval.chunks import Passage
from retrieval.manifest import (
    CHROMADB_VERSION_KEY,
    EMBED_MODEL_KEY,
    GIT_DIR,
    HEAD_FILE,
    MANIFEST_DIGEST_KEY,
)

FAKE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
FAKE_EMBED_MODEL = "fake-embed-model"
# Bare hex, no `sha256:` prefix: that is how Ollama's `/api/tags` reports a
# model digest, and so what `model_client.model_digest` hands back.
FAKE_EMBED_DIGEST = "1" * 64
VECTOR_SIZE = 3

# Two files the registry's `include` glob selects, each with a heading and prose
# so chunking yields at least one passage per file.
CHEATSHEETS = {
    "cheatsheets/Alpha_Cheat_Sheet.md": (
        "# Alpha\n\nAlpha is about validating what an agent reads.\n\n"
        "## Mitigation\n\nTreat every retrieved text as data, never as instruction.\n"),
    "cheatsheets/Beta_Cheat_Sheet.md": (
        "# Beta\n\nBeta is about the tools an agent may reach.\n\n"
        "## Mitigation\n\nGive the agent the narrowest tool that does the job.\n"),
}

# Three passages on three axes: a query near one axis names its passage first.
SAMPLE_VECTORS = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
SAMPLE_PATH = "cheatsheets/Alpha_Cheat_Sheet.md"

# A query lying almost on the first sample axis, so the nearest passage is known.
NEAR_FIRST = [0.9, 0.1, 0.0]


def sample_passages() -> list[Passage]:
    """One passage per sample vector, in the same order."""
    return [Passage(OWASP_CHEATSHEETS, SAMPLE_PATH, "Mitigation", index, f"passage {index}")
            for index in range(len(SAMPLE_VECTORS))]


def fake_embed(texts: list[str], model: str = FAKE_EMBED_MODEL) -> list[list[float]]:
    """A deterministic stand-in for the embedding model: three bytes of a hash, as floats."""
    return [[(byte + 1) / 256 for byte in hashlib.sha256(text.encode("utf-8")).digest()[:VECTOR_SIZE]]
            for text in texts]


def stub_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the two model calls the index and the probe make, so no server is needed."""
    monkeypatch.setattr(model_client, "embed", fake_embed)
    monkeypatch.setattr(model_client, "model_digest", lambda model=None: FAKE_EMBED_DIGEST)


def write_fake_clone(knowledge_dir: Path, files: dict[str, str] = CHEATSHEETS) -> Path:
    """Lay out the one registered source as a detached-HEAD clone holding the given files."""
    clone = knowledge_dir / OWASP_CHEATSHEETS
    (clone / GIT_DIR).mkdir(parents=True)
    (clone / GIT_DIR / HEAD_FILE).write_text(f"{FAKE_COMMIT}\n", encoding="utf-8")
    for relative, text in files.items():
        path = clone / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return clone


def stub_pins() -> dict:
    """What a built index records about itself; stubbed, because no manifest is written here."""
    return {MANIFEST_DIGEST_KEY: "sha256:stub", CHROMADB_VERSION_KEY: store.chromadb_version(),
            EMBED_MODEL_KEY: "stub-model"}


def build_index(knowledge_dir: Path) -> store.Store:
    """Create an index under a directory and fill it with the sample passages and vectors."""
    opened = store.open_store(knowledge_dir, create=True)
    opened.rebuild(sample_passages(), SAMPLE_VECTORS, stub_pins())
    return opened


def build_fake_index(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A knowledge directory with a fake clone indexed by the real command, embedder stubbed."""
    knowledge_dir = tmp_path / "knowledge"
    write_fake_clone(knowledge_dir)
    stub_embedding(monkeypatch)
    index_knowledge.build(knowledge_dir, FAKE_EMBED_MODEL)
    return knowledge_dir
