"""The pin a fetch writes: the only surviving record of which commit was audited.

The history is deleted once the tree is on disk, so nothing in the tree says
where it came from. That makes this small file the whole provenance of a fetched
audit, and it is held to the same rules as every other artifact here: fixed
fields, sorted keys, a trailing newline, and no value that changes between two
identical runs.

`manifest` is pure, so its tests hand it strings. `write_manifest` is the one
line of file I/O, so its tests read what landed on disk.

A hand-written pin used to sit beside a pinned fixture, and one test compared
the two shapes. This project ships no keys any more, so only the producer's
half is checked here: the field list below is the whole record of the format.
"""

import json
from pathlib import Path

import fetch_repo
from fetch_helpers import COMMIT, COMMIT_DATE, NAME, URL, download_root, install_fake_git
from grading_keys import MANIFEST_SUFFIX

# Every field the pin carries, named here so adding or dropping one is a test
# change a reader can see rather than a silent schema drift.
PIN_FIELDS = {"name", "role", "upstream_url", "upstream_commit",
              "upstream_commit_date", "note"}


def built_pin() -> dict:
    """One pin, built through the real function from known strings."""
    return fetch_repo.manifest(NAME, URL, COMMIT, COMMIT_DATE)


def written_pin_text(root: Path) -> str:
    """Write one pin through the real function and return the text that landed."""
    return fetch_repo.write_manifest(root, built_pin()).read_text(encoding="utf-8")


# --- What the pin says -------------------------------------------------------

def test_the_pin_carries_exactly_the_documented_fields() -> None:
    """A field that appears without being documented is a schema change nobody read."""
    assert set(built_pin()) == PIN_FIELDS


def test_the_pin_records_the_commit_and_its_date() -> None:
    """The commit is what makes the audit repeatable; without it the URL names a branch."""
    document = built_pin()
    assert document["upstream_commit"] == COMMIT
    assert document["upstream_commit_date"] == COMMIT_DATE


def test_the_pin_records_where_the_tree_came_from() -> None:
    """The tree has no history left, so the URL survives only here."""
    assert built_pin()["upstream_url"] == URL


def test_the_pin_says_the_tree_was_fetched_for_an_audit() -> None:
    """The role tells a reader this is not a signed-off fixture with a grading key."""
    assert built_pin()["role"] == "fetched_for_audit"
    assert fetch_repo.FETCHED_ROLE == "fetched_for_audit"


def test_the_pin_records_no_fetch_time() -> None:
    """A commit is byte-stable; a clock is not, and one time field would end determinism."""
    assert "fetched_at" not in built_pin()
    assert not [key for key in built_pin() if key.endswith(("_at", "_time", "timestamp"))]


def test_the_pin_explains_that_the_history_is_gone() -> None:
    """Whoever opens the tree next needs to know why there is nothing to run git in."""
    assert "the history was removed" in built_pin()["note"]


def test_building_a_pin_twice_gives_the_same_document() -> None:
    """It is a pure function: same arguments in, same bytes out, no hidden state."""
    assert built_pin() == built_pin()


# --- Where it lands, and how it is written ----------------------------------

def test_the_pin_goes_beside_the_tree_and_never_inside_it(tmp_path) -> None:
    """A file written inside the tree would be audited as part of the fetched app."""
    path = fetch_repo.manifest_path(tmp_path, NAME)
    assert path == tmp_path / f"{NAME}{MANIFEST_SUFFIX}"
    assert path.parent == tmp_path


def test_the_pin_is_written_with_sorted_keys_and_a_trailing_newline(tmp_path) -> None:
    """The convention every producer under src/ follows, so two runs diff as nothing."""
    text = written_pin_text(tmp_path)
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_the_written_pin_reads_back_as_the_document_it_was_given(tmp_path) -> None:
    """Sorting keys must not lose or rename a field on the way to disk."""
    assert json.loads(written_pin_text(tmp_path)) == built_pin()


def test_a_finished_fetch_leaves_a_pin_naming_the_commit_that_arrived(
        tmp_path, monkeypatch) -> None:
    """End to end: the commit read from the tree is the commit the pin records."""
    install_fake_git(monkeypatch)
    root = download_root(tmp_path)
    fetch_repo.fetch(URL, root)
    document = json.loads(fetch_repo.manifest_path(root, NAME).read_text(encoding="utf-8"))
    assert document == fetch_repo.manifest(NAME, URL, COMMIT, COMMIT_DATE)
