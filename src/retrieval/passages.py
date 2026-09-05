"""Choosing and citing the passages one finding is grounded on: the pure half.

Split from `retrieve.py`, which decides whether a run *can* be grounded and
owns the two edges that talk to a server. Everything here takes hits and
returns hits, text or attributions -- no I/O, no chromadb, nothing to stub.

Two of these are safety rules rather than tidying, and both are asserted:
a passage naming a different risk class is dropped, because a passage about
one risk attached to a finding of another is an invitation to re-classify, and
re-classification is what Phase 4 scores; and the block is bounded in
characters, because Ollama silently truncates the *front* of a prompt that
overruns its context, and the front is where the instructions live.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from artifacts.advice_rules import evidence_line, foreign_owasp_ids
from artifacts.remediation import MAX_SOURCES_PER_FINDING
from retrieval.manifest import SOURCES

if TYPE_CHECKING:
    # Types only, so the annotations below are real without importing chromadb.
    from retrieval.store import Hit


# One limit, the schema's: a finding may cite at most this many passages.
TOP_K = MAX_SOURCES_PER_FINDING
# Ask for more than k, because a passage naming another risk class is dropped.
OVERSAMPLE = 2
# The reference block's size in the prompt. Ollama truncates the *front* of a
# prompt that overruns its context; the block sits before the instructions, so
# an overrun costs passages, but a bound keeps it from ever getting there.
MAX_REFERENCE_CHARS = 3000


def query_text(finding: dict) -> str:
    """What a finding asks the knowledge base: its title and the evidence behind it."""
    return f"{finding['title']}. {evidence_line(finding)}"


def drop_foreign_owasp(hits: list[Hit], owasp_id: str) -> list[Hit]:
    """Drop a passage naming another risk class, which would make the answer re-classify."""
    return [hit for hit in hits if not foreign_owasp_ids(hit.text, owasp_id)]


def stable_order(hits: list[Hit]) -> list[Hit]:
    """Nearest first, ties broken by id, so the same query always cites in the same order."""
    return sorted(hits, key=lambda hit: (hit.distance, hit.id))


def within_budget(hits: list[Hit], limit: int = MAX_REFERENCE_CHARS) -> list[Hit]:
    """The leading passages that fit the character budget together."""
    kept, used = [], 0
    for hit in hits:
        if used + len(hit.text) > limit:
            break
        kept.append(hit)
        used += len(hit.text)
    return kept


def as_source(hit: Hit) -> dict:
    """The attribution an advice entry records for one passage."""
    return {"source": hit.source, "path": hit.path, "heading": hit.heading or None,
            "url": SOURCES[hit.source].public_url(hit.path)}


def one_per_section(hits: list[Hit]) -> list[Hit]:
    """Keep the best-ranked hit from each section, dropping later chunks of the same one.

    A long section is indexed as several chunks, but the attribution
    `as_source` writes is the *section* -- source, path and heading -- so two
    chunks of one section produce the same citation twice, which
    `artifacts/remediation._check_sources` refuses as a producer bug. Deduping
    here rather than loosening that guard: citing one section twice is noise to
    a reader, and the guard is right.
    """
    seen: set[tuple] = set()
    kept = []
    for hit in hits:
        key = (hit.source, hit.path, hit.heading or None)
        if key in seen:
            continue
        seen.add(key)
        kept.append(hit)
    return kept


def reference_block(hits: list[Hit]) -> str:
    """The passages as the prompt carries them, each labelled with where it came from."""
    return "\n\n".join(
        f"[{number}] {hit.source} {hit.path}" + (f" - {hit.heading}" if hit.heading else "")
        + f"\n{hit.text}" for number, hit in enumerate(hits, 1))
