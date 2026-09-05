"""Pins the knowledge base: which clones, at which commit, holding which bytes.

Pure functions over paths and text. The manifest is what makes "the advice was
grounded on these documents" checkable rather than hoped for: a clone can be
edited without moving its commit, so the commit alone is not a pin, and the
content digest is what catches that. It mirrors `vex/manifest.json`, and the
same rule holds -- `note` is required, so a reader meeting an empty
`knowledge/` learns why rather than assuming an oversight.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from artifacts.remediation import KNOWLEDGE_SOURCES, OWASP_CHEATSHEETS

SCHEMA_VERSION = 1

# The knowledge directory's layout: the manifest, the clones (one per source
# name) and the index beside them. Defined here, not in the store, so an audit
# can tell whether an index exists without importing chromadb to ask.
MANIFEST_NAME = "manifest.json"
INDEX_DIR = "index"
DATABASE_FILE = "chroma.sqlite3"
GIT_DIR = ".git"
HEAD_FILE = "HEAD"
PACKED_REFS = "packed-refs"
REF_PREFIX = "ref: "
COMMIT = re.compile(r"^[0-9a-f]{40}$")

# What a built index records about itself, so an audit can tell it is the index
# the committed manifest describes. Here rather than in `store.py` for the same
# reason `index_present` is: comparing these three strings must not cost a
# chromadb import.
MANIFEST_DIGEST_KEY = "manifest_digest"
CHROMADB_VERSION_KEY = "chromadb_version"
EMBED_MODEL_KEY = "embed_model"

DIGEST_PREFIX = "sha256:"
SEPARATOR = b"\0"

NOTE = ("The remediation advice is grounded on passages from these sources. Each "
        "is an upstream clone under knowledge/<name>/, fetched out-of-band and "
        "gitignored; the ChromaDB index built from them is gitignored too. This "
        "manifest is the one committed record: rebuild the index from the same "
        "commits with src/index_knowledge.py and the digests must match.")


@dataclass(frozen=True)
class Source:
    """One upstream corpus: where it comes from, its licence, and what to index."""

    name: str
    upstream_url: str
    license: str
    include: tuple[str, ...]
    url_template: str

    def public_url(self, path: str) -> str:
        """The upstream page a clone-relative path is published at, for attribution."""
        return self.url_template.format(stem=Path(path).stem)


# The registry: one entry per source, and the only place its licence, URL and
# file selection are written. The Cheat Sheets repository also carries its own
# README and index pages, which `include` leaves out.
SOURCES = {
    OWASP_CHEATSHEETS: Source(
        name=OWASP_CHEATSHEETS,
        upstream_url="https://github.com/OWASP/CheatSheetSeries",
        license="CC-BY-SA-4.0",
        include=("cheatsheets/*.md",),
        url_template="https://cheatsheetseries.owasp.org/cheatsheets/{stem}.html",
    ),
}

if set(SOURCES) != set(KNOWLEDGE_SOURCES):
    raise ValueError(f"SOURCES {sorted(SOURCES)} must match the schema's "
                     f"KNOWLEDGE_SOURCES {sorted(KNOWLEDGE_SOURCES)}")


def index_present(knowledge_dir: Path) -> bool:
    """Say whether an index exists, checked before any database client is opened.

    Opening a client on a missing path creates the database file (measured), so
    an audit that merely *looked* for an index would otherwise write one.
    """
    return (knowledge_dir / INDEX_DIR / DATABASE_FILE).is_file()


def commit_from_git_dir(git_dir: Path) -> str:
    """Read the commit a clone is at, from its own files, without starting a program.

    Three shapes: a detached HEAD holding the commit itself; a symbolic HEAD
    naming a ref kept as a loose file; the same ref kept only in packed-refs.
    Anything else is refused, because a pin that might be wrong is worse than
    none.
    """
    head = (git_dir / HEAD_FILE).read_text(encoding="utf-8").strip()
    if COMMIT.match(head):
        return head
    if not head.startswith(REF_PREFIX):
        raise ValueError(f"{git_dir / HEAD_FILE} holds neither a commit nor a ref: {head!r}")
    ref = head[len(REF_PREFIX):]
    loose = git_dir / ref
    if loose.is_file():
        return _checked_commit(loose.read_text(encoding="utf-8").strip(), ref)
    return _from_packed_refs(git_dir / PACKED_REFS, ref)


def _from_packed_refs(packed: Path, ref: str) -> str:
    """Find one ref's commit in packed-refs, refusing a ref that is not there."""
    if not packed.is_file():
        raise ValueError(f"ref {ref!r} has no loose file and there is no {packed}")
    for line in packed.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == ref:
            return _checked_commit(parts[0], ref)
    raise ValueError(f"ref {ref!r} is not in {packed}")


def _checked_commit(value: str, ref: str) -> str:
    """A commit id, or a clear refusal naming the ref that held something else."""
    if not COMMIT.match(value):
        raise ValueError(f"ref {ref!r} holds {value!r}, not a commit id")
    return value


def matched_files(clone: Path, source: Source) -> list[Path]:
    """Every file a source's `include` globs select, in sorted path order."""
    return sorted({path for pattern in source.include for path in clone.glob(pattern)
                   if path.is_file()})


def content_digest(clone: Path, files: list[Path]) -> str:
    """One digest over the indexed files: each path, NUL, its bytes, NUL, in sorted order.

    The path is fed too, so renaming a file changes the digest as editing one
    does. Spelled out here because two implementations of "digest of the files"
    would otherwise disagree.
    """
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(clone).as_posix().encode("utf-8"))
        digest.update(SEPARATOR)
        digest.update(path.read_bytes())
        digest.update(SEPARATOR)
    return DIGEST_PREFIX + digest.hexdigest()


def source_entry(source: Source, commit: str, files: list[Path], clone: Path,
                 passage_count: int) -> dict:
    """One manifest record for a source, every field recomputable from the clone."""
    return {
        "name": source.name,
        "upstream_url": source.upstream_url,
        "upstream_commit": commit,
        "license": source.license,
        "include": sorted(source.include),
        "file_count": len(files),
        "content_digest": content_digest(clone, files),
        "indexed_passage_count": passage_count,
    }


def build_manifest(entries: list[dict], embed_model: str, embed_model_digest: str | None,
                   chromadb_version: str, chunk_chars: int, chunk_overlap_chars: int) -> dict:
    """Assemble the manifest, sources sorted by name and the count restated."""
    ordered = sorted(entries, key=lambda entry: entry["name"])
    names = [entry["name"] for entry in ordered]
    if len(set(names)) != len(names):
        raise ValueError(f"two sources share a name: {names}")
    return {
        "schema_version": SCHEMA_VERSION,
        "embed_model": embed_model,
        "embed_model_digest": embed_model_digest,
        "chromadb_version": chromadb_version,
        "chunk_chars": chunk_chars,
        "chunk_overlap_chars": chunk_overlap_chars,
        "source_count": len(ordered),
        "sources": ordered,
        "note": NOTE,
    }


def manifest_to_json(document: dict) -> str:
    """The manifest's on-disk form: sorted keys, one trailing newline, like every producer."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def manifest_digest(text: str) -> str:
    """The digest of the manifest as written, which is what the index records."""
    return DIGEST_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()
