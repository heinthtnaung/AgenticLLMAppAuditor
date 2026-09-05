"""The committed knowledge manifest, if there is one, says what the advice was grounded on.

The sibling of `test_vex_unread.py`'s manifest tests. The clones and the index
under `knowledge/` are gitignored; the manifest is the one committed record, so
it is held to the schema here. It is written by the index command and does not
exist until that command has run on some machine, so this file skips -- visibly,
naming the path -- rather than failing on a checkout that has not built one.
Nothing else under `knowledge/` is read.
"""

import json
from pathlib import Path

import pytest

from artifacts.remediation import KNOWLEDGE_SOURCES
from retrieval import manifest as manifest_module
from retrieval.manifest import MANIFEST_NAME

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"
MANIFEST = KNOWLEDGE_DIR / MANIFEST_NAME


@pytest.fixture(scope="module")
def manifest() -> dict:
    """The committed manifest, or a visible skip when the index has never been built here."""
    if not MANIFEST.is_file():
        pytest.skip(f"{MANIFEST} is not committed; the index command writes it")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_the_manifest_carries_the_schema_version_the_reader_knows(manifest: dict) -> None:
    """A version the probe cannot read is a manifest it cannot compare."""
    assert manifest["schema_version"] == manifest_module.SCHEMA_VERSION


def test_the_source_count_agrees_with_the_list(manifest: dict) -> None:
    """The count is a restatement, so it can disagree; a test is what stops it."""
    assert manifest["source_count"] == len(manifest["sources"])


def test_every_source_is_one_the_schema_names(manifest: dict) -> None:
    """The `sources` entries in remediation.json join on these names."""
    assert {entry["name"] for entry in manifest["sources"]} <= set(KNOWLEDGE_SOURCES)


def test_the_manifest_says_why_the_folder_beside_it_is_empty(manifest: dict) -> None:
    """A committed manifest beside gitignored clones needs its note, as the VEX one does."""
    assert manifest["note"].strip()


def test_every_upstream_url_is_https(manifest: dict) -> None:
    """The origin of each clone is a page a reader can open, over a channel they can trust."""
    for entry in manifest["sources"]:
        assert entry["upstream_url"].startswith("https://"), entry["name"]


def test_every_source_is_pinned_to_a_commit_and_a_digest(manifest: dict) -> None:
    """A commit alone is not a pin -- a clone can be edited without moving it -- so both are present."""
    for entry in manifest["sources"]:
        assert len(entry["upstream_commit"]) == 40, entry["name"]
        assert entry["content_digest"].startswith(manifest_module.DIGEST_PREFIX), entry["name"]


def test_the_manifest_is_in_its_canonical_form() -> None:
    """Written by the tool with sorted keys and one trailing newline, so a hand edit shows as a diff."""
    if not MANIFEST.is_file():
        pytest.skip(f"{MANIFEST} is not committed; the index command writes it")
    text = MANIFEST.read_text(encoding="utf-8")
    assert text == manifest_module.manifest_to_json(json.loads(text))
