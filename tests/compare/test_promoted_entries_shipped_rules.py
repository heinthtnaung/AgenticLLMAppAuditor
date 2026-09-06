"""Each entry of a promoted key, held to what a shipped key's entries are held to.

The companion of `test_promoted_key_shipped_rules.py`, split off it because one
file doing both jobs grew past the length a reader takes in at once. The rules
and the field list come from `tests/test_shipped_grading_key.py`: a promoted
entry is a shipped entry, and the two files may not disagree about what that
requires.

`test_the_promoted_key_holds_the_entries_the_draft_had` is the guard that stops
every loop here passing over an empty findings list; it lives in the companion
file with the count it checks, and `ENTRY_COUNT` is imported from there.
"""

import pytest
from artifacts.repo_path import is_repo_relative_posix
from artifacts.surface import SURFACE_KINDS
from drafted_key_fixtures import promote_one_draft, promoted_document
from grading_keys import GROUND_TRUTH_SUFFIX
from test_promoted_key_shipped_rules import ENTRY_COUNT
from test_shipped_grading_key import CODE_ANCHOR_LENGTH, OWASP_IDS, REQUIRED_ENTRY_FIELDS


@pytest.fixture
def entries(monkeypatch, tmp_path) -> list[dict]:
    """The findings of one promoted key, read back off disk."""
    keys_dir = promote_one_draft(monkeypatch, tmp_path)
    return promoted_document(keys_dir, GROUND_TRUTH_SUFFIX)["findings"]


def test_there_are_entries_to_check(entries) -> None:
    """The guard, restated here so this file cannot go quiet on its own."""
    assert len(entries) == ENTRY_COUNT


def test_every_promoted_entry_carries_every_required_field(entries) -> None:
    """The eight required fields, including `code_anchor`, which no reader guards."""
    for entry in entries:
        assert [field for field in REQUIRED_ENTRY_FIELDS if field not in entry] == []


def test_every_promoted_entry_has_a_unique_id(entries) -> None:
    """Ids are cited in results tables, so two entries sharing one misattribute a row."""
    ids = [entry["id"] for entry in entries]
    assert len(set(ids)) == len(ids)


def test_every_promoted_entry_names_a_risk_class_this_project_scores(entries) -> None:
    """The 2025 OWASP subset plus auditability; anything else cannot be scored."""
    for entry in entries:
        assert entry["owasp_id"] in OWASP_IDS


def test_every_promoted_entry_anchors_a_repo_relative_posix_path(entries) -> None:
    """`file` is the join key against `surfaces.json`, which uses that convention."""
    for entry in entries:
        assert is_repo_relative_posix(entry["file"])


def test_every_promoted_entry_anchors_a_real_line_number(entries) -> None:
    """A line below 1 could match no surface and would be silently unscoreable."""
    for entry in entries:
        assert isinstance(entry["line"], int) and entry["line"] >= 1


def test_every_promoted_anchor_is_trimmed_source_text_of_the_documented_length(entries) -> None:
    """The first 60 characters of the trimmed source at `line`, and no more."""
    for entry in entries:
        anchor = entry["code_anchor"]
        assert anchor and anchor == anchor.lstrip()
        assert len(anchor) <= CODE_ANCHOR_LENGTH


def test_every_promoted_entry_names_a_surface_kind_the_extractor_produces(entries) -> None:
    """`llm_surface` joins on `Surface.kind`, so a kind outside the four matches nothing."""
    for entry in entries:
        assert entry["llm_surface"] is None or entry["llm_surface"] in SURFACE_KINDS
