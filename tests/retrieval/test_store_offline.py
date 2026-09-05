"""What the knowledge store must never do: reach the network, or write at audit time.

ChromaDB's defaults would do two things this project forbids -- fetch an
embedding model from the internet the first time it is handed text, and report
telemetry -- so the store is held to the same guarantee as the audit itself.
Every test here performs a real store operation (open, build from precomputed
vectors, query, reopen) with the socket type replaced by one that refuses and
records, and the count of recorded attempts is the assertion.

Split from `tests/parsing/test_offline.py`, which holds the same guarantee for
the audit path -- extract, serialise, map, run the checks. The two files share
the refusing socket, which lives in `tests/offline_fixtures.py`. What the store
*does* -- ranking, hit fields, rebuild, reopen -- is `test_store.py` beside
this file; what it must never do is here. What neither file can see, because a
blocked socket in this process cannot watch a third-party default, is read off
the source instead by `tests/parsing/test_offline_containment.py`.

The index is built by `knowledge_fixtures` from three synthetic vectors, so
nothing here needs Ollama, the network, or the real clone under `knowledge/`.
"""

import pytest

from knowledge_fixtures import NEAR_FIRST, SAMPLE_VECTORS, build_index
from offline_fixtures import no_network  # noqa: F401  (used as a fixture)
from retrieval import store
from test_no_mutation import hash_tree


def test_opening_a_missing_index_refuses_and_creates_nothing(tmp_path, no_network) -> None:
    """An audit that merely looks for an index must not write one: the refusal comes first."""
    with pytest.raises(store.StoreError, match="no index under"):
        store.open_store(tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert no_network.attempts == []


def test_building_an_index_from_vectors_touches_no_network(tmp_path, no_network) -> None:
    """Create, add precomputed vectors, count: every step local."""
    assert build_index(tmp_path).count() == len(SAMPLE_VECTORS)
    assert no_network.attempts == []


def test_querying_a_built_index_touches_no_network(tmp_path, no_network) -> None:
    """The operation an audit performs per finding, so the one that most has to open nothing."""
    assert build_index(tmp_path).query(NEAR_FIRST, k=len(SAMPLE_VECTORS))
    assert no_network.attempts == []


def test_a_reopened_store_refuses_text_on_add_without_a_socket(tmp_path, no_network) -> None:
    """The load-bearing one: text in would make Chroma fetch a model, and the
    refusing function is attached on reopen too."""
    build_index(tmp_path)
    reopened = store.open_store(tmp_path)
    with pytest.raises(store.StoreError, match="embeds nothing"):
        reopened._collection.add(ids=["text-in"], documents=["some text to embed"])
    assert no_network.attempts == []


def test_a_reopened_store_refuses_a_text_query_without_a_socket(tmp_path, no_network) -> None:
    """The same for a query by text, the other route to an embedding function."""
    build_index(tmp_path)
    reopened = store.open_store(tmp_path)
    with pytest.raises(store.StoreError, match="embeds nothing"):
        reopened._collection.query(query_texts=["some text"], n_results=1)
    assert no_network.attempts == []


def test_reopening_and_querying_leaves_the_index_byte_identical(tmp_path, no_network) -> None:
    """Read-only at audit time: what an audit does to the index changes no file under it."""
    build_index(tmp_path)
    before = hash_tree(tmp_path)
    store.open_store(tmp_path).query(NEAR_FIRST, k=2)
    assert hash_tree(tmp_path) == before
    assert no_network.attempts == []
