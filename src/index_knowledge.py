"""Builds the knowledge base index: chunk the clones, embed, store, pin.

A command of its own, run once after the clones are in place and again after
they change. It is the one step that needs the embedding model, so unlike an
audit it does not degrade: a server it cannot reach is an error, because an
index half built is worse than none. It writes only under the knowledge
directory -- the index, and the manifest that pins it.

The manifest is written last but digested first: the index records the digest
of the manifest text, so the text must be final before the index is built.
"""

import argparse
import sys
from pathlib import Path

import config
import model_client
from retrieval import store
from retrieval.chunks import CHUNK_CHARS, CHUNK_OVERLAP_CHARS, Passage, chunk_markdown
from retrieval.manifest import (
    GIT_DIR,
    MANIFEST_NAME,
    SOURCES,
    Source,
    build_manifest,
    commit_from_git_dir,
    manifest_digest,
    manifest_to_json,
    matched_files,
    source_entry,
)


def passages_for(clone: Path, source: Source) -> tuple[list[Passage], list[Path]]:
    """Every passage of one source, and the files they were cut from."""
    files = matched_files(clone, source)
    if not files:
        raise ValueError(f"{clone} matches none of {source.include}; is the clone complete?")
    passages = [passage for path in files
                for passage in chunk_markdown(path.read_text(encoding="utf-8"), source.name,
                                              path.relative_to(clone).as_posix())]
    return passages, files


def embed_all(passages: list[Passage], embed_model: str) -> list[list[float]]:
    """Embed every passage in batches, reporting progress on stderr."""
    vectors: list[list[float]] = []
    for start in range(0, len(passages), store.ADD_BATCH):
        batch = passages[start:start + store.ADD_BATCH]
        vectors += model_client.embed([passage.text for passage in batch], embed_model)
        print(f"  embedded {len(vectors)} of {len(passages)}", file=sys.stderr)
    return vectors


def build(knowledge_dir: Path, embed_model: str) -> tuple[Path, int]:
    """Chunk, embed, rebuild the index and write the manifest; return both results."""
    entries, passages = [], []
    for name, source in sorted(SOURCES.items()):
        clone = knowledge_dir / name
        if not (clone / GIT_DIR).is_dir():
            raise FileNotFoundError(f"no clone at {clone}; see the README for the command")
        found, files = passages_for(clone, source)
        entries.append(source_entry(source, commit_from_git_dir(clone / GIT_DIR), files,
                                    clone, len(found)))
        passages += found
    if not passages:
        raise ValueError("the sources yielded no passages, so there is nothing to index")
    vectors = embed_all(passages, embed_model)
    text = manifest_to_json(build_manifest(
        entries, embed_model, model_client.model_digest(embed_model),
        store.chromadb_version(), CHUNK_CHARS, CHUNK_OVERLAP_CHARS))
    pins = {store.MANIFEST_DIGEST_KEY: manifest_digest(text),
            store.CHROMADB_VERSION_KEY: store.chromadb_version(),
            store.EMBED_MODEL_KEY: embed_model}
    count = store.open_store(knowledge_dir, create=True).rebuild(passages, vectors, pins)
    manifest_path = knowledge_dir / MANIFEST_NAME
    manifest_path.write_text(text, encoding="utf-8")
    return manifest_path, count


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Build the knowledge base index the remediation advice is grounded on.")
    parser.add_argument(
        "--knowledge-dir", type=Path, default=config.get_path("AUDITOR_KNOWLEDGE_DIR"),
        help="the directory holding the clones; the index and manifest go beside them")
    return parser


def main() -> int:
    """Build the index once. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        manifest_path, count = build(args.knowledge_dir, model_client.EMBED_MODEL)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"indexed {count} passages; wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
