"""Writing a drafted grading key: the two files, and the two refusals.

The subject is `key_store`, the disk half of drafting -- `key_drafting` shapes
what the model said, this module puts the pair on disk. The split landed with
the drafts folder; the claims below are the ones that were true of the single
module before it and are true of the writer now.

A drafted key is written once and never again, and it is written pinned or not
at all. Both refusals exist because of where the alternative surfaces: a second
draft would silently move every figure scored against the first, and an
unpinned key passes `write` happily and then fails several steps later inside
`grading_keys.discover_graded_apps`, nowhere near the cause.

So the last two tests here close that loop rather than trusting it: the pair
this module writes is fed straight to `discover_graded_apps` -- which raises on
an unpinned key -- and to `harness.check_key`, which is what the scorer's
loader puts a hand-placed key through. Every key is written into `tmp_path`;
`grading_keys/` is never touched, and `test_drafted_key_location.py` is what
holds that.
"""

import json

import pytest

import key_drafting
import key_store
from drafted_key_fixtures import APP, COMMIT, ENTRY, PIN
from evaluation.harness import KEY_SCHEMA_VERSION, check_key
from grading_keys import (
    GROUND_TRUTH_SUFFIX,
    KEY_SOURCES,
    MANIFEST_SUFFIX,
    TOOL_DRAFTED,
    discover_graded_apps,
    key_path,
)

# What `fetch_repo.pin_document` answers for a tree nothing pins: no commit, so
# no key may be written against it.
UNPINNED: dict = {}


def written(tmp_path, pin: dict = PIN, entries: tuple[dict, ...] = (ENTRY,)):
    """Write one drafted key and its pin into a temporary directory; return the key's path."""
    document = key_drafting.key_document(
        APP, list(entries), pin.get("upstream_commit", ""))
    return key_store.write(APP, document, pin, tmp_path)


def read(path) -> dict:
    """Read one written grading file back."""
    return json.loads(path.read_text(encoding="utf-8"))


# --- both files land ----------------------------------------------------------

def test_it_writes_the_key_and_the_manifest_beside_it(tmp_path) -> None:
    """A key alone is unpinned, so the pair is written or neither is."""
    written(tmp_path)
    assert key_path(APP, GROUND_TRUTH_SUFFIX, tmp_path).is_file()
    assert key_path(APP, MANIFEST_SUFFIX, tmp_path).is_file()


def test_it_makes_the_directory_it_was_pointed_at(tmp_path) -> None:
    """`grading_keys/drafts/` is gitignored, so a clean checkout does not have one."""
    drafts = tmp_path / "drafts"
    document = key_drafting.key_document(APP, [ENTRY], COMMIT)
    assert key_store.write(APP, document, PIN, drafts).parent == drafts


def test_the_key_is_written_where_it_says_it_was(tmp_path) -> None:
    """The returned path is the ground-truth file, which is what the caller prints."""
    assert written(tmp_path) == key_path(APP, GROUND_TRUTH_SUFFIX, tmp_path)


def test_the_written_key_holds_the_entries_it_was_given(tmp_path) -> None:
    """The document is written through, not rebuilt: the model's one entry survives."""
    document = read(written(tmp_path))
    assert [entry["id"] for entry in document["findings"]] == ["K-01"]
    assert document["finding_count"] == 1


def test_the_manifest_pins_the_commit_the_key_was_drafted_at(tmp_path) -> None:
    """Line numbers mean nothing without the commit they were read at, so it is recorded."""
    written(tmp_path)
    assert read(key_path(APP, MANIFEST_SUFFIX, tmp_path))["upstream_commit"] == COMMIT


def test_the_key_records_the_same_commit_as_its_manifest(tmp_path) -> None:
    """Two files, one pin: the scorer copies the key's, the discovery check reads the pin's."""
    document = read(written(tmp_path))
    assert document["upstream_commit"] == COMMIT


def test_a_second_run_finds_the_key_the_first_one_wrote(tmp_path) -> None:
    """`existing` is what stops a second run redrafting on every invocation."""
    path = written(tmp_path)
    assert key_store.existing(APP, tmp_path) == path


def test_nothing_is_found_before_anything_is_drafted(tmp_path) -> None:
    """The off position: an empty directory answers None rather than a path that is not there."""
    assert key_store.existing(APP, tmp_path) is None


# --- the two refusals ---------------------------------------------------------

def test_it_refuses_to_overwrite_a_key_it_already_wrote(tmp_path) -> None:
    """A redraft would discard whatever a human has corrected in the first draft."""
    written(tmp_path)
    with pytest.raises(FileExistsError, match="is not overwritten"):
        written(tmp_path)


def test_the_first_draft_survives_the_refused_second(tmp_path) -> None:
    """Refusing is only worth anything if the file on disk is left as it was."""
    before = written(tmp_path).read_bytes()
    with pytest.raises(FileExistsError):
        written(tmp_path, entries=())
    assert key_path(APP, GROUND_TRUTH_SUFFIX, tmp_path).read_bytes() == before


def test_it_refuses_a_key_that_nothing_pins(tmp_path) -> None:
    """The message names the cause -- no commit could be read -- and how to get one."""
    with pytest.raises(ValueError, match="no upstream commit could be read"):
        written(tmp_path, pin=UNPINNED)


def test_an_unpinned_draft_writes_no_file_at_all(tmp_path) -> None:
    """Refused before the directory is made, so a failed draft leaves nothing behind."""
    with pytest.raises(ValueError):
        written(tmp_path / "drafts", pin=UNPINNED)
    assert list(tmp_path.iterdir()) == []


# --- the readers downstream accept it -----------------------------------------

def test_discovery_accepts_the_pair_that_was_written(tmp_path) -> None:
    """`discover_graded_apps` raises on an unpinned key, so the pair is fed straight to it."""
    written(tmp_path)
    assert discover_graded_apps(tmp_path) == (APP,)


def test_the_written_key_passes_the_check_the_scorers_loader_makes(tmp_path) -> None:
    """A hand-placed key is validated at the I/O edge, and a drafted one goes the same way."""
    path = written(tmp_path)
    assert check_key(read(path), path)["source"] == TOOL_DRAFTED


# --- the vocabulary the document is written in --------------------------------

def test_the_drafted_schema_version_is_the_one_the_scorer_reads() -> None:
    """`key_drafting` spells the version itself; the check is exact equality, so it must agree."""
    assert key_drafting.SCHEMA_VERSION == KEY_SCHEMA_VERSION


def test_the_source_it_writes_is_in_the_closed_vocabulary() -> None:
    """A source outside `KEY_SOURCES` earns no qualification at all, which is the worst case."""
    assert key_drafting.SOURCE == TOOL_DRAFTED
    assert key_drafting.SOURCE in KEY_SOURCES


def test_a_drafted_document_never_claims_to_have_been_verified() -> None:
    """A tool cannot verify the key it wrote, so the field is false at the producer."""
    document = key_drafting.key_document(APP, [ENTRY], COMMIT)
    assert (document["verified"], document["verified_by"], document["verified_date"]) \
        == (False, None, None)


def test_a_drafted_document_claims_completeness_for_neither_list() -> None:
    """Nobody checked it, so false positives are unmeasurable rather than counted as wrong."""
    document = key_drafting.key_document(APP, [ENTRY], COMMIT)
    assert (document["findings_complete"], document["expected_surfaces_complete"]) \
        == (False, False)
