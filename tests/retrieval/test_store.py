"""What the knowledge store does: its shape, its errors, and how it ranks, rebuilds and reopens.

Two halves. The first needs no index at all -- the fields a hit carries, the
error type callers degrade on, and the embedding function that refuses text.
The second builds a real index in `tmp_path` from the synthetic vectors in
`knowledge_fixtures`, because ranking, attribution and what survives a rebuild
are only checkable against a database that really holds something.

What the store must never *do* -- open a socket, or write a file at audit time
-- is the offline guarantee, and lives beside this file in
`test_store_offline.py`; that it must not import chromadb outside the one
module, or leave a third-party default switched on, is read off the source in
`tests/parsing/test_offline_containment.py`.
"""

import dataclasses

import pytest

from knowledge_fixtures import NEAR_FIRST, SAMPLE_VECTORS, build_index, sample_passages, stub_pins
from retrieval import manifest, store
from retrieval.store import Hit, RefusingEmbedding, StoreError

HIT_FIELDS = ("id", "source", "path", "heading", "text", "distance")


def test_a_hit_carries_exactly_the_fields_the_retriever_reads() -> None:
    """The attribution and the ordering both read from these; nothing else is exposed."""
    assert tuple(field.name for field in dataclasses.fields(Hit)) == HIT_FIELDS


def test_a_hit_is_immutable() -> None:
    """Sorted and filtered, never edited: a hit is a record of what the index said."""
    hit = Hit("id", "src", "path", "h", "text", 0.1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        hit.distance = 0.0


def test_the_store_error_is_a_runtime_error() -> None:
    """Callers degrade on RuntimeError, so the store's failures must be one without naming chromadb."""
    assert issubclass(StoreError, RuntimeError)


def test_the_refusing_embedding_refuses() -> None:
    """Text in is the one thing the store must never accept; the function attached to it raises."""
    with pytest.raises(StoreError, match="embeds nothing"):
        RefusingEmbedding()(["some text"])


def test_the_refusing_embedding_survives_the_round_trip_chroma_persists() -> None:
    """Chroma stores the function by name and config and rebuilds it on reopen; the rebuilt one still refuses."""
    rebuilt = RefusingEmbedding.build_from_config(RefusingEmbedding().get_config())
    with pytest.raises(StoreError):
        rebuilt(["some text"])


def test_the_collection_is_named_and_the_batch_is_bounded() -> None:
    """Two constants the index command relies on; neither may drift to a value Chroma refuses."""
    assert store.COLLECTION_NAME == "knowledge"
    assert 0 < store.ADD_BATCH <= 5000


def test_the_three_pin_keys_are_distinct_names() -> None:
    """The probe reads all three from the collection's metadata; a shared key would shadow one.

    Named on `manifest.py`, which owns them: comparing three strings must not
    cost a chromadb import, so the store reads them from there rather than the
    other way round.
    """
    keys = (manifest.MANIFEST_DIGEST_KEY, manifest.CHROMADB_VERSION_KEY, manifest.EMBED_MODEL_KEY)
    assert len(set(keys)) == 3


def test_querying_returns_the_nearest_passage_first(tmp_path) -> None:
    """The store ranks by cosine distance; a query near one axis names that passage first."""
    hits = build_index(tmp_path).query(NEAR_FIRST, k=3)
    assert [hit.text for hit in hits] == ["passage 0", "passage 1", "passage 2"]
    assert [hit.distance for hit in hits] == sorted(hit.distance for hit in hits)


def test_a_hit_carries_the_passages_origin(tmp_path) -> None:
    """Source, path and heading come back with the text, so the attribution needs no second lookup."""
    [hit] = build_index(tmp_path).query(NEAR_FIRST, k=1)
    expected = sample_passages()[0]
    assert (hit.id, hit.source, hit.path, hit.heading) == (
        expected.id, expected.source, expected.path, expected.heading)


def test_a_built_index_reopens_with_its_pins_and_its_passages(tmp_path) -> None:
    """A later open, the way an audit opens it, finds what the build recorded."""
    build_index(tmp_path)
    reopened = store.open_store(tmp_path)
    assert reopened.count() == len(SAMPLE_VECTORS)
    assert reopened.pins() == stub_pins()


def test_a_rebuild_with_mismatched_lengths_is_refused(tmp_path) -> None:
    """One vector per passage, or the index would silently misalign them."""
    opened = store.open_store(tmp_path, create=True)
    with pytest.raises(StoreError, match="3 passages but 2 vectors"):
        opened.rebuild(sample_passages(), SAMPLE_VECTORS[:2], stub_pins())


def test_a_second_rebuild_replaces_the_first(tmp_path) -> None:
    """A duplicate add keeps the old passage (measured), so a rebuild drops the collection first."""
    opened = build_index(tmp_path)
    opened.rebuild(sample_passages()[:2], SAMPLE_VECTORS[:2], stub_pins())
    assert opened.count() == 2
