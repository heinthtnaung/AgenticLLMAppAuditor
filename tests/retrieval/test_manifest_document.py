"""The manifest document: the registry it is built from, its assembly, and its on-disk form.

It mirrors `vex/manifest.json`: sorted sources, a restated count, a required note,
sorted keys and one trailing newline. Reading the commit and digesting the files
that feed it are in test_manifest.py.
"""

import hashlib
import json
from pathlib import Path

import pytest

from artifacts.remediation import KNOWLEDGE_SOURCES, OWASP_CHEATSHEETS
from retrieval import manifest
from retrieval.manifest import (
    DIGEST_PREFIX,
    NOTE,
    SOURCES,
    Source,
    build_manifest,
    content_digest,
    manifest_digest,
    manifest_to_json,
    matched_files,
    source_entry,
)

COMMIT = "0123456789abcdef0123456789abcdef01234567"
CHEATSHEETS = SOURCES[OWASP_CHEATSHEETS]


def entry(name: str) -> dict:
    """A manifest source record under a given name, other fields fixed."""
    return {"name": name, "upstream_commit": COMMIT, "file_count": 1}


def document(*names: str) -> dict:
    """A manifest over sources with these names, other pins fixed."""
    return build_manifest([entry(name) for name in names], "model", None, "1.0.0", 1200, 200)


def test_the_registry_names_exactly_the_schemas_sources() -> None:
    """The manifest, the index and every `sources` entry join on these names."""
    assert set(SOURCES) == set(KNOWLEDGE_SOURCES)


def test_every_registered_source_is_licensed_and_reachable_over_https() -> None:
    """Attribution needs a licence to cite and an https origin to point at."""
    for source in SOURCES.values():
        assert source.license
        assert source.upstream_url.startswith("https://")
        assert source.include


def test_the_public_url_is_built_from_the_files_stem() -> None:
    """`cheatsheets/X.md` is published at `.../cheatsheets/X.html`."""
    assert CHEATSHEETS.public_url("cheatsheets/Input_Validation_Cheat_Sheet.md") == (
        "https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html")


def test_a_source_is_immutable() -> None:
    """The registry is a constant; a test or a caller cannot rewrite a licence in passing."""
    with pytest.raises(AttributeError):
        Source("n", "https://x", "L", ("*.md",), "{stem}").license = "other"


def test_a_source_entry_is_recomputable_from_the_clone(tmp_path: Path) -> None:
    """Every field is either the registry's, the commit, or derived from the matched files."""
    (tmp_path / "cheatsheets").mkdir()
    (tmp_path / "cheatsheets" / "A.md").write_text("a", encoding="utf-8")
    files = matched_files(tmp_path, CHEATSHEETS)
    assert source_entry(CHEATSHEETS, COMMIT, files, tmp_path, 7) == {
        "name": OWASP_CHEATSHEETS, "upstream_url": CHEATSHEETS.upstream_url,
        "upstream_commit": COMMIT, "license": CHEATSHEETS.license,
        "include": sorted(CHEATSHEETS.include), "file_count": 1,
        "content_digest": content_digest(tmp_path, files), "indexed_passage_count": 7,
    }


def test_build_manifest_sorts_the_sources_by_name() -> None:
    """Sorted, so two builds from the same clones write the same bytes."""
    assert [s["name"] for s in document("zeta", "alpha")["sources"]] == ["alpha", "zeta"]


def test_build_manifest_restates_the_source_count() -> None:
    """The count is a restatement, and a restatement can disagree; here it does not."""
    built = document("alpha", "zeta")
    assert built["source_count"] == len(built["sources"]) == 2


def test_build_manifest_refuses_two_sources_with_one_name() -> None:
    """Names are what the files join on, so a duplicate is a producer bug."""
    with pytest.raises(ValueError, match="share a name"):
        document("alpha", "alpha")


def test_build_manifest_carries_the_note_and_schema_version() -> None:
    """A reader meeting the manifest learns why the clones beside it are not committed."""
    built = document("alpha")
    assert built["note"] == NOTE and NOTE.strip()
    assert built["schema_version"] == manifest.SCHEMA_VERSION


def test_build_manifest_records_every_pin_it_was_given() -> None:
    """The embed model, its digest, the database version and the chunking are all restated."""
    built = build_manifest([entry("alpha")], "model", "abc123", "1.2.3", 1200, 200)
    assert (built["embed_model"], built["embed_model_digest"], built["chromadb_version"],
            built["chunk_chars"], built["chunk_overlap_chars"]) == (
        "model", "abc123", "1.2.3", 1200, 200)


def test_the_manifest_is_written_with_sorted_keys_and_a_trailing_newline() -> None:
    """The on-disk form every producer in this project uses, so a diff is a change."""
    text = manifest_to_json({"zeta": 1, "alpha": 2})
    assert text == '{\n  "alpha": 2,\n  "zeta": 1\n}\n'
    assert json.loads(text) == {"alpha": 2, "zeta": 1}


def test_the_manifest_digest_is_over_the_written_text() -> None:
    """The index records this digest, so it must be the digest of exactly what was written."""
    text = manifest_to_json({"a": 1})
    assert manifest_digest(text) == DIGEST_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()
