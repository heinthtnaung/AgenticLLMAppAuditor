"""Grounds the advice: whether the knowledge base can be used, and what each finding retrieves.

Two edges that talk to the world; the pure choosing and citing of passages is
`passages.py`. `probe()` runs once per audit and is the one producer of the
`knowledge_base` block -- every reason a run is ungrounded is
decided here, so a reader of `remediation.json` never meets a reason no code
can write. `Grounding.passages_for()` runs once per finding and returns
passages or nothing; a per-finding failure costs that finding its grounding,
is said on stderr, and never fails the audit.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import model_client
from artifacts.remediation import (
    EMBED_MODEL_MISSING,
    EMBED_UNAVAILABLE,
    INDEX_STALE,
    KNOWLEDGE_INDEXED,
    KNOWLEDGE_NOT_INDEXED,
    NO_INDEX,
    knowledge_provenance,
)
from retrieval.passages import (
    OVERSAMPLE,
    TOP_K,
    as_source,
    one_per_section,
    drop_foreign_owasp,
    query_text,
    reference_block,
    stable_order,
    within_budget,
)
from retrieval.manifest import (
    CHROMADB_VERSION_KEY,
    MANIFEST_DIGEST_KEY,
    MANIFEST_NAME,
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    index_present,
    manifest_digest,
)

if TYPE_CHECKING:
    # Types only, so the annotations below are real without importing chromadb:
    # `store` is imported at runtime by `_opened_index` alone; see it for why.
    # Nothing else in this module names chromadb, directly or through it.
    from retrieval.store import Store

# Embedded once by the probe, so "the embedding model is reachable" is a
# measured fact of the run rather than a hope per finding.
PROBE_TEXT = "how to mitigate a security weakness in an LLM application"

@dataclass(frozen=True)
class Grounding:
    """What one run may ground its advice on: an open store, or the reason there is none."""

    store: Store | None
    knowledge: dict
    embed_model: str

    def passages_for(self, finding: dict) -> tuple[str, list[dict]]:
        """The reference text and attributions for one finding; empty when it cannot be grounded."""
        if self.store is None:
            return "", []
        try:
            vector = model_client.embed([query_text(finding)], self.embed_model)[0]
            hits = self.store.query(vector, TOP_K * OVERSAMPLE)
        except (OSError, RuntimeError) as error:
            print(f"warning: {finding['finding_id']} advised ungrounded: {error}",
                  file=sys.stderr)
            return "", []
        ranked = drop_foreign_owasp(hits, finding["owasp_id"])
        chosen = within_budget(one_per_section(stable_order(ranked)))
        chosen = chosen[:TOP_K]
        return reference_block(chosen), [as_source(hit) for hit in chosen]


def ungrounded(reason: str, embed_model: str) -> Grounding:
    """A run with nothing to retrieve from, and the one reason why."""
    return Grounding(None, knowledge_provenance(KNOWLEDGE_NOT_INDEXED, reason), embed_model)


def _read_manifest(path: Path) -> tuple[str, dict] | None:
    """The manifest's text and the two fields the block needs, or None when unusable.

    Hand-edited or truncated is exactly the drift `index_stale` exists for, so
    a broken file degrades the run rather than raising: `main.py` treats a
    ValueError as fatal, and an unusable knowledge base must never be.

    Every field is checked here rather than trusted downstream, because
    `knowledge_provenance` raises on a source count below one -- so a manifest
    saying `0` would kill the audit that merely looked at it. A future schema
    version degrades the same way, deliberately.
    """
    try:
        text = path.read_text(encoding="utf-8")
        document = json.loads(text)
        embed_model, count = document["embed_model"], document["source_count"]
        version = document["schema_version"]
    except (ValueError, KeyError, TypeError, OSError):
        return None
    if version != MANIFEST_SCHEMA_VERSION or not isinstance(count, int) or count < 1:
        return None
    if not isinstance(embed_model, str) or not embed_model:
        return None
    return text, {"embed_model": embed_model, "source_count": count}


def _is_stale(pins: dict, manifest: dict, text: str, embed_model: str,
              chromadb_version: str) -> bool:
    """Three ways a built index no longer matches what would be built today.

    The manifest moved under it, chromadb changed, or the embedding model did.
    Any of them means the vectors in the index and the vectors a query would
    produce are not comparable, so retrieving from it would answer nonsense.
    Pure: the installed version is passed in, because the pin keys live in
    `manifest.py` precisely so comparing them costs no chromadb import.
    """
    return (pins[MANIFEST_DIGEST_KEY] != manifest_digest(text)
            or pins[CHROMADB_VERSION_KEY] != chromadb_version
            or manifest["embed_model"] != embed_model)


def _opened_index(knowledge_dir: Path) -> tuple[Store, str] | None:
    """The open index and the chromadb version reading it, or None when it will not open.

    The version comes back with the store so this stays the only place the
    store module is imported: `probe` compares it and never touches chromadb.

    A lazy import that earns its keep: importing chromadb costs about half a
    second and every audit imports this module through the advice path, so an
    audit with no index must never pay for it.

    Two failures, one answer. chromadb uninstalled while an index sits on disk
    is handled beside a database that will not open, because both are an index
    this code cannot read -- and `_read_manifest`'s promise, that no
    knowledge-base problem may fail an audit, has to hold here too.
    """
    try:
        from retrieval import store
    except ImportError:
        return None
    try:
        return store.open_store(knowledge_dir), store.chromadb_version()
    except store.StoreError:
        return None


def _embed_reason(embed_model: str) -> str | None:
    """Embed once to prove the server is there; the reason it is not, or None."""
    try:
        model_client.embed([PROBE_TEXT], embed_model)
    except model_client.ModelNotPulled:
        return EMBED_MODEL_MISSING
    except RuntimeError:
        return EMBED_UNAVAILABLE
    return None


def probe(knowledge_dir: Path, embed_model: str = model_client.EMBED_MODEL) -> Grounding:
    """Decide once per run whether the knowledge base is usable, and open it if so."""
    manifest_path = knowledge_dir / MANIFEST_NAME
    if not manifest_path.is_file() or not index_present(knowledge_dir):
        return ungrounded(NO_INDEX, embed_model)
    read = _read_manifest(manifest_path)
    if read is None:
        return ungrounded(INDEX_STALE, embed_model)
    text, manifest = read
    read_index = _opened_index(knowledge_dir)
    if read_index is None:
        return ungrounded(INDEX_STALE, embed_model)
    opened, chromadb_version = read_index
    if _is_stale(opened.pins(), manifest, text, embed_model, chromadb_version):
        return ungrounded(INDEX_STALE, embed_model)
    reason = _embed_reason(embed_model)
    if reason:
        return ungrounded(reason, embed_model)
    return Grounding(opened, knowledge_provenance(
        KNOWLEDGE_INDEXED, None, embed_model, _safe_digest(embed_model),
        manifest_digest(text), manifest["source_count"]), embed_model)


def _safe_digest(embed_model: str) -> str | None:
    """The embedding model's digest, or None when the listing cannot be read -- never fatal."""
    try:
        return model_client.model_digest(embed_model)
    except RuntimeError:
        return None
