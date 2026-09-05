"""The vector store the knowledge base is kept in: ChromaDB, local, vectors only.

The one module in this project that imports chromadb. It is built so the
database can never do two things its defaults would do. Its default embedding
function fetches a model from the internet the first time it is asked to embed
text -- so a function that refuses is always attached, and this module's API
takes vectors computed elsewhere, never text to embed. And its client sends
usage telemetry unless told not to, so it is told not to, and a test asserts
the setting the way the SBOM generator's update check is asserted.

Measured before writing: with those two closed, importing, opening, adding and
querying open no socket at all, and opening then querying an existing index
leaves its files byte-identical.
"""

from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings
from chromadb.errors import ChromaError

from retrieval.chunks import Passage
from retrieval.manifest import (
    CHROMADB_VERSION_KEY,
    EMBED_MODEL_KEY,
    INDEX_DIR,
    MANIFEST_DIGEST_KEY,
    index_present,
)

CLIENT_SETTINGS = Settings(anonymized_telemetry=False)
# Chroma requires 3-512 characters of [a-zA-Z0-9._-].
COLLECTION_NAME = "knowledge"
SPACE = "cosine"
DISTANCE = {"hnsw:space": SPACE}
# Under Chroma's own batch cap of a few thousand, and a sensible embedding
# request size besides.
ADD_BATCH = 256

# The pin keys are `manifest.py`'s, imported because `pins()` below writes them.


class StoreError(RuntimeError):
    """Anything the store cannot do, raised at its boundary so callers never import chromadb."""


class RefusingEmbedding(EmbeddingFunction[Documents]):
    """An embedding function that embeds nothing, so Chroma can never fetch one that does."""

    def __init__(self) -> None:
        """Nothing to configure: refusing needs no state."""

    def __call__(self, input: Documents) -> Embeddings:
        """Refuse: vectors are computed by the model client and handed in."""
        raise StoreError("the knowledge store embeds nothing; pass precomputed vectors")

    @staticmethod
    def name() -> str:
        """The name Chroma persists with the collection."""
        return "refusing"

    def get_config(self) -> dict:
        """No configuration to persist."""
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "RefusingEmbedding":
        """Rebuild from the persisted (empty) configuration."""
        return RefusingEmbedding()

    def default_space(self) -> str:
        """Cosine, matching the collection."""
        return SPACE

    def supported_spaces(self) -> list[str]:
        """Cosine only."""
        return [SPACE]


@dataclass(frozen=True)
class Hit:
    """One retrieved passage and how far it sat from the query."""

    id: str
    source: str
    path: str
    heading: str
    text: str
    distance: float


def chromadb_version() -> str:
    """The installed chromadb's version, recorded so a mismatch is named, not opaque."""
    return chromadb.__version__


class Store:
    """A handle on the one collection, taking vectors only."""

    def __init__(self, client: chromadb.ClientAPI, collection: chromadb.Collection) -> None:
        """Hold the client too: a rebuild replaces the collection."""
        self._client = client
        self._collection = collection

    def pins(self) -> dict:
        """What the index recorded about itself when it was built."""
        metadata = dict(self._collection.metadata or {})
        return {key: metadata.get(key) for key in
                (MANIFEST_DIGEST_KEY, CHROMADB_VERSION_KEY, EMBED_MODEL_KEY)}

    def count(self) -> int:
        """How many passages the index holds."""
        return self._collection.count()

    def rebuild(self, passages: list[Passage], vectors: list[list[float]], pins: dict) -> int:
        """Replace the whole index: a duplicate `add` silently keeps the old passage (measured)."""
        if len(passages) != len(vectors):
            raise StoreError(f"{len(passages)} passages but {len(vectors)} vectors")
        try:
            self._client.delete_collection(COLLECTION_NAME)
            self._collection = self._client.create_collection(
                COLLECTION_NAME, metadata={**DISTANCE, **pins},
                embedding_function=RefusingEmbedding())
            for start in range(0, len(passages), ADD_BATCH):
                self._add(passages[start:start + ADD_BATCH], vectors[start:start + ADD_BATCH])
        except ChromaError as error:
            raise StoreError(f"could not rebuild the index: {error}") from error
        return len(passages)

    def _add(self, passages: list[Passage], vectors: list[list[float]]) -> None:
        """Add one batch, every metadata value a string or int (None is refused by Chroma)."""
        self._collection.add(
            ids=[passage.id for passage in passages],
            embeddings=vectors,
            documents=[passage.text for passage in passages],
            metadatas=[{"source": passage.source, "path": passage.path,
                        "heading": passage.heading, "index": passage.index}
                       for passage in passages])

    def query(self, vector: list[float], k: int) -> list[Hit]:
        """The k nearest passages to one query vector, nearest first."""
        try:
            got = self._collection.query(query_embeddings=[vector], n_results=k,
                                         include=["documents", "metadatas", "distances"])
        except ChromaError as error:
            raise StoreError(f"could not query the index: {error}") from error
        return [Hit(id=hit_id, source=meta["source"], path=meta["path"],
                    heading=meta["heading"], text=text, distance=distance)
                for hit_id, meta, text, distance in zip(
                    got["ids"][0], got["metadatas"][0], got["documents"][0], got["distances"][0])]


def open_store(knowledge_dir: Path, create: bool = False) -> Store:
    """Open the index under `knowledge_dir`; only a rebuild may create one."""
    index_dir = knowledge_dir / INDEX_DIR
    if not create and not index_present(knowledge_dir):
        raise StoreError(f"no index under {index_dir}: build one with src/index_knowledge.py")
    try:
        client = chromadb.PersistentClient(path=str(index_dir), settings=CLIENT_SETTINGS)
        collection = client.get_or_create_collection(
            COLLECTION_NAME, metadata=DISTANCE, embedding_function=RefusingEmbedding())
    except ChromaError as error:
        raise StoreError(f"could not open the index under {index_dir}: {error}") from error
    return Store(client, collection)
