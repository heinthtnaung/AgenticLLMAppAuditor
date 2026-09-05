"""The one probe that decides a run's `knowledge_base`, and what each finding then retrieves.

Every test runs against an index the real command built into `tmp_path` from a
fake clone with the embedder stubbed, so every reason the probe can write -- no
index, stale index, unreachable embedder, unpulled model -- is produced by the
code path that would produce it in an audit, never by constructing the block.
The pure helpers are in test_passages.py.

The last three tests cover the one failure that needs no index and no server:
chromadb uninstalled while a built index sits on disk. `_opened_index` catches
`ImportError` beside `StoreError` for exactly that case, because both are an
index this code cannot read, and no knowledge-base problem may fail an audit.
"""

import json
import sys
from pathlib import Path

import pytest

import model_client
import retrieval
from artifacts.remediation import (
    EMBED_MODEL_MISSING,
    EMBED_UNAVAILABLE,
    INDEX_STALE,
    KNOWLEDGE_INDEXED,
    KNOWLEDGE_NOT_INDEXED,
    NO_INDEX,
    OWASP_CHEATSHEETS,
    SOURCE_FIELDS,
)
from knowledge_fixtures import FAKE_EMBED_DIGEST, FAKE_EMBED_MODEL, build_fake_index, fake_embed
from remediation_fixtures import finding_record
from retrieval import retrieve, store
from retrieval.manifest import MANIFEST_NAME, manifest_digest
from retrieval.passages import TOP_K, query_text
from retrieval.retrieve import Grounding, probe


def knowledge_block(grounding: Grounding) -> tuple[str, str | None]:
    """The (status, reason) pair a grounding would write."""
    return grounding.knowledge["status"], grounding.knowledge["reason"]


def refuse_embedding(monkeypatch, error: Exception) -> None:
    """Make every embedding call fail with the given error."""
    def refuse(texts, model=None):
        """Raise instead of embedding."""
        raise error
    monkeypatch.setattr(model_client, "embed", refuse)


def record_embedding(monkeypatch) -> list[list[str]]:
    """Embed like the fake, and return the list every request's texts land in."""
    asked = []

    def record(texts, model=None):
        """Note what was embedded and answer like the fake."""
        asked.append(list(texts))
        return fake_embed(texts)
    monkeypatch.setattr(model_client, "embed", record)
    return asked


def test_a_directory_with_no_manifest_is_not_indexed(tmp_path: Path) -> None:
    """The first check: no manifest means no index, and no client is opened to find out."""
    grounding = probe(tmp_path, FAKE_EMBED_MODEL)
    assert knowledge_block(grounding) == (KNOWLEDGE_NOT_INDEXED, NO_INDEX)
    assert grounding.store is None


def test_a_manifest_without_an_index_is_not_indexed(tmp_path: Path) -> None:
    """Both files must exist; a manifest alone is a record of an index that is not here."""
    (tmp_path / MANIFEST_NAME).write_text("{}", encoding="utf-8")
    assert knowledge_block(probe(tmp_path, FAKE_EMBED_MODEL)) == (KNOWLEDGE_NOT_INDEXED, NO_INDEX)


def test_probing_a_missing_index_creates_nothing(tmp_path: Path) -> None:
    """Read-only at audit time: a probe on an empty directory leaves it empty."""
    probe(tmp_path, FAKE_EMBED_MODEL)
    assert list(tmp_path.iterdir()) == []


def test_a_freshly_built_index_is_indexed(monkeypatch, tmp_path: Path) -> None:
    """The happy path: manifest and index agree, the embedder answers, the store is open."""
    grounding = probe(build_fake_index(monkeypatch, tmp_path), FAKE_EMBED_MODEL)
    assert knowledge_block(grounding) == (KNOWLEDGE_INDEXED, None)
    assert grounding.store is not None


def test_an_indexed_run_pins_the_manifest_it_read_and_counts_its_sources(monkeypatch, tmp_path) -> None:
    """The block restates the manifest's digest and source count, so the artifact names its input."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    text = (knowledge_dir / MANIFEST_NAME).read_text(encoding="utf-8")
    block = probe(knowledge_dir, FAKE_EMBED_MODEL).knowledge
    assert block["manifest_digest"] == manifest_digest(text)
    assert block["source_count"] == json.loads(text)["source_count"] == 1
    assert (block["embed_model"], block["embed_model_digest"]) == (FAKE_EMBED_MODEL, FAKE_EMBED_DIGEST)


def test_an_index_built_for_another_embed_model_is_stale(monkeypatch, tmp_path: Path) -> None:
    """Vectors from one model mean nothing to another, so the index is unusable, not merely old."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    assert knowledge_block(probe(knowledge_dir, "another-model")) == (KNOWLEDGE_NOT_INDEXED, INDEX_STALE)


def test_a_hand_edited_manifest_is_stale(monkeypatch, tmp_path: Path) -> None:
    """The index recorded the manifest's digest; an edit to the file on disk breaks the pair."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    manifest_path = knowledge_dir / MANIFEST_NAME
    manifest_path.write_text(manifest_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert knowledge_block(probe(knowledge_dir, FAKE_EMBED_MODEL)) == (KNOWLEDGE_NOT_INDEXED, INDEX_STALE)


def test_an_index_built_by_another_chromadb_version_is_stale(monkeypatch, tmp_path: Path) -> None:
    """The on-disk format follows the library; an index from another version is not trusted."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    monkeypatch.setattr(store, "chromadb_version", lambda: "0.0.0-other")
    assert knowledge_block(probe(knowledge_dir, FAKE_EMBED_MODEL)) == (KNOWLEDGE_NOT_INDEXED, INDEX_STALE)


def test_an_unreachable_embedder_leaves_the_run_ungrounded(monkeypatch, tmp_path: Path) -> None:
    """Index fine, server down: the reason is the server, and the audit goes on."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    refuse_embedding(monkeypatch, RuntimeError("connection refused"))
    grounding = probe(knowledge_dir, FAKE_EMBED_MODEL)
    assert knowledge_block(grounding) == (KNOWLEDGE_NOT_INDEXED, EMBED_UNAVAILABLE)
    assert grounding.store is None


def test_an_unpulled_embed_model_is_named_as_the_reason(monkeypatch, tmp_path: Path) -> None:
    """A 404 is a model to pull, not a server to start; the block tells the reader which."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    refuse_embedding(monkeypatch, model_client.ModelNotPulled("no such model"))
    assert knowledge_block(probe(knowledge_dir, FAKE_EMBED_MODEL)) == (
        KNOWLEDGE_NOT_INDEXED, EMBED_MODEL_MISSING)


def test_the_probe_embeds_exactly_one_constant_text(monkeypatch, tmp_path: Path) -> None:
    """One `/api/embed` call per run, with a fixed text, so reachability is measured once."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    asked = record_embedding(monkeypatch)
    probe(knowledge_dir, FAKE_EMBED_MODEL)
    assert asked == [[retrieve.PROBE_TEXT]]


def test_an_unreadable_model_listing_leaves_the_digest_null_but_the_run_indexed(monkeypatch, tmp_path) -> None:
    """The digest is a record, not a gate: a run that can embed is grounded even unrecorded."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)

    def refuse(model=None):
        """Fail the listing the way an unreachable server does."""
        raise RuntimeError("cannot list models")
    monkeypatch.setattr(model_client, "model_digest", refuse)
    block = probe(knowledge_dir, FAKE_EMBED_MODEL).knowledge
    assert (block["status"], block["embed_model_digest"]) == (KNOWLEDGE_INDEXED, None)


def test_an_ungrounded_run_retrieves_nothing_for_any_finding(tmp_path: Path) -> None:
    """No store, no query: the reference is empty and so is the attribution."""
    assert probe(tmp_path, FAKE_EMBED_MODEL).passages_for(finding_record()) == ("", [])


def test_a_per_finding_embedding_failure_costs_only_that_findings_grounding(monkeypatch, tmp_path, capsys) -> None:
    """The run stays indexed; this entry is advised ungrounded, and stderr names the finding."""
    grounding = probe(build_fake_index(monkeypatch, tmp_path), FAKE_EMBED_MODEL)
    refuse_embedding(monkeypatch, RuntimeError("server went away"))
    finding = finding_record()
    assert grounding.passages_for(finding) == ("", [])
    assert f"warning: {finding['finding_id']} advised ungrounded" in capsys.readouterr().err


def test_a_store_failure_is_caught_the_same_way(monkeypatch, tmp_path, capsys) -> None:
    """StoreError is a RuntimeError raised at the store's boundary, so no chromadb name reaches here."""
    grounding = probe(build_fake_index(monkeypatch, tmp_path), FAKE_EMBED_MODEL)

    def refuse(vector, k):
        """Fail the query the way a corrupt index would."""
        raise store.StoreError("could not query the index")
    monkeypatch.setattr(grounding.store, "query", refuse)
    assert grounding.passages_for(finding_record()) == ("", [])
    assert "advised ungrounded" in capsys.readouterr().err


def test_a_grounded_finding_cites_at_most_top_k_well_formed_sources(monkeypatch, tmp_path) -> None:
    """Each attribution is exactly the schema's four fields, from the registered source, over https."""
    grounding = probe(build_fake_index(monkeypatch, tmp_path), FAKE_EMBED_MODEL)
    reference, sources = grounding.passages_for(finding_record())
    assert reference and 1 <= len(sources) <= TOP_K
    for source in sources:
        assert set(source) == SOURCE_FIELDS
        assert source["source"] == OWASP_CHEATSHEETS
        assert source["url"].startswith("https://")


def test_a_grounded_finding_embeds_its_own_query_text(monkeypatch, tmp_path) -> None:
    """What is embedded per finding is the finding's query, and only that."""
    grounding = probe(build_fake_index(monkeypatch, tmp_path), FAKE_EMBED_MODEL)
    asked = record_embedding(monkeypatch)
    finding = finding_record()
    grounding.passages_for(finding)
    assert asked == [[query_text(finding)]]


def test_a_grounded_findings_sources_match_its_reference_block(monkeypatch, tmp_path) -> None:
    """The passages the prompt carried are the passages the entry attributes, in the same order."""
    grounding = probe(build_fake_index(monkeypatch, tmp_path), FAKE_EMBED_MODEL)
    reference, sources = grounding.passages_for(finding_record())
    labels = [line for line in reference.splitlines() if line.startswith("[")]
    assert [label.split(" ")[2] for label in labels] == [source["path"] for source in sources]


def test_a_grounding_is_immutable() -> None:
    """Decided once per run; nothing downstream may swap the store or rewrite the block."""
    grounding = retrieve.ungrounded(NO_INDEX, FAKE_EMBED_MODEL)
    with pytest.raises(AttributeError):
        grounding.store = object()


def import_the_store() -> object:
    """Run the one import statement `_opened_index` runs, and return what it bound."""
    from retrieval import store as imported
    return imported


def refuse_the_store_import(monkeypatch) -> None:
    """Make importing the store raise, the way an uninstalled chromadb would.

    Both halves are needed. The package already holds `store` as an attribute
    from an earlier import, so the machinery would hand that back without
    importing anything; and `None` in `sys.modules` is what makes it refuse
    rather than read the module off disk a second time.
    """
    monkeypatch.delattr(retrieval, "store", raising=False)
    monkeypatch.setitem(sys.modules, "retrieval.store", None)


def test_the_simulated_missing_chromadb_really_breaks_the_import(monkeypatch) -> None:
    """Guard on the two tests below: a simulation that still imported would prove nothing."""
    refuse_the_store_import(monkeypatch)
    with pytest.raises(ImportError):
        import_the_store()


def test_an_index_that_cannot_be_opened_at_all_is_stale_rather_than_fatal(monkeypatch, tmp_path) -> None:
    """chromadb gone under a built index: the run degrades, and the audit goes on."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    refuse_the_store_import(monkeypatch)
    grounding = probe(knowledge_dir, FAKE_EMBED_MODEL)
    assert knowledge_block(grounding) == (KNOWLEDGE_NOT_INDEXED, INDEX_STALE)
    assert grounding.store is None


def test_a_run_that_could_not_open_the_index_retrieves_nothing(monkeypatch, tmp_path) -> None:
    """The degraded grounding is a normal ungrounded one, so every finding is advised without it."""
    knowledge_dir = build_fake_index(monkeypatch, tmp_path)
    refuse_the_store_import(monkeypatch)
    assert probe(knowledge_dir, FAKE_EMBED_MODEL).passages_for(finding_record()) == ("", [])
