"""A promoted draft is a shipped key, so the key document obeys a shipped key's rules.

The moment `promote_key` moves the pair up one level, `discover_graded_apps`
finds it and runs are scored against it -- there is no lesser status a promoted
key sits in. So everything `docs/SCHEMAS.md` requires of a key in
`grading_keys/` must already be true of whatever `key_promotion.refusals` was
willing to let through.

`grading_keys/` has held no key since 2026-09-06, so this promotion is the only
grading key the suite can read: these three files are where those rules have a
subject at all, and it is one the test builds rather than one it finds on disk.

The field lists are **imported from `grading_key_rules.py`** rather than
respelled, so a rule tightened there reaches this file instead of passing it. A
failure here is not a bad test: it is `key_promotion` missing a check, and the
name of the failing test says which.

The entries are `test_promoted_entries_shipped_rules.py` and the pin is
`test_promoted_pin_shipped_rules.py`, because one file asking all three
questions grew past the length a reader takes in at once.

The draft promoted here is the one a real run would produce -- built by
`key_drafting.key_document` from a model entry, anchored, sorted, with the
extractor's surfaces beside it -- plus the two corrections a human makes by
hand. A hostile draft is a different question and these files do not ask it.
"""

from pathlib import Path

import promote_key
import pytest
from drafted_key_fixtures import (
    APP,
    DRAFTS_NAME,
    corrected_draft,
    fit_key,
    promote_one_draft,
    promoted_document,
    redirect_keys_dir,
)
from keys import key_drafting
from evaluation.harness import KEY_SCHEMA_VERSION, check_key
from keys.grading_keys import (
    GROUND_TRUTH_SUFFIX,
    KEY_SOURCES,
    discover_graded_apps,
    key_path,
)
from grading_key_rules import REQUIRED_ENTRY_FIELDS, REQUIRED_KEY_FIELDS
from keys.key_promotion import ANCHOR_FIELD, ENTRY_FIELDS

# What the promoted draft holds, so no assertion below passes over an empty list.
ENTRY_COUNT = 1
SURFACE_COUNT = 1

# A draft somebody recorded a check on before promoting it, which is the state
# the web editor's verify route leaves one in. The date is the one the route
# stamped, not one this test invents a meaning for.
CHECKED_BY = "Quokka Reviewer"
CHECKED_ON = "2026-09-16"
CHECKED_KEY = {**fit_key(), "verified": True, "verified_by": CHECKED_BY,
               "verified_date": CHECKED_ON}


@pytest.fixture
def keys_dir(monkeypatch, tmp_path) -> Path:
    """A temporary keys folder with one corrected draft promoted into it."""
    return promote_one_draft(monkeypatch, tmp_path)


@pytest.fixture
def key(keys_dir: Path) -> dict:
    """The promoted grading key, read from where discovery would read it."""
    return promoted_document(keys_dir, GROUND_TRUTH_SUFFIX)


# --- the promotion happened, and there is something to check ------------------

def test_the_promoted_app_is_discovered(keys_dir) -> None:
    """Discovery reads the pin as it goes, so this is also the key's first real reader."""
    assert discover_graded_apps(keys_dir) == (APP,)


def test_the_promoted_key_holds_the_entries_the_draft_had(key) -> None:
    """The guard: a key with no findings would make the per-entry file prove nothing."""
    assert len(key["findings"]) == ENTRY_COUNT
    assert key["finding_count"] == ENTRY_COUNT


# --- what `docs/SCHEMAS.md` requires of the document --------------------------

def test_the_promoted_key_carries_every_required_field(key) -> None:
    """The thirteen `docs/SCHEMAS.md` marks required, imported from `grading_key_rules`."""
    assert [field for field in REQUIRED_KEY_FIELDS if field not in key] == []


def test_the_promoted_key_is_at_the_schema_version_the_scorer_reads(key) -> None:
    """A key at another version is refused at score time, which is far from the cause."""
    assert key["schema_version"] == KEY_SCHEMA_VERSION


def test_the_promoted_key_names_the_app_its_file_is_named_after(key) -> None:
    """The app name is the only join key, so the field and the file name must agree."""
    assert key["app"] == APP


def test_the_promoted_key_counts_its_own_contents(key) -> None:
    """A count that disagrees with the list makes every figure computed from it wrong."""
    assert key["expected_surface_count"] == len(key["expected_surfaces"]) == SURFACE_COUNT


def test_the_promoted_key_declares_a_known_source(key) -> None:
    """A source outside the vocabulary earns no qualification at all."""
    assert key["source"] in KEY_SOURCES


def test_promotion_invents_no_verification_claim(key) -> None:
    """The drafter wrote no claim, and promoting is not a review, so none appears.

    Narrower than it used to read. This said "a tool cannot verify the key it
    wrote for itself", which was a general rule and is no longer true: since
    2026-09-16 `tool_drafted` with `verified: true` is a legal document, and the
    editor's verify route is how a human records having read the entries. What
    is still true, and is what this holds, is that promotion carries the field
    through rather than setting it -- the test below is the other direction.
    """
    assert key["verified"] is False
    assert key["verified_by"] is None and key["verified_date"] is None


def test_promotion_carries_a_recorded_verification_through_unchanged(
        monkeypatch, tmp_path) -> None:
    """The direction the name above implies and nothing held: a checked draft stays checked.

    Promotion moves the document; it neither invents a claim nor resets one. A
    promotion that quietly cleared `verified` would discard the one fact the
    verify route exists to record, and every figure scored against the key would
    go on carrying `key_unverified` with nobody able to say why.

    `--accept-verification` is what lets it past, because the claim can be made
    through an endpoint with no authentication -- `test_promote_key_verification.py`
    is where that gate is the subject.
    """
    keys_dir = redirect_keys_dir(monkeypatch, tmp_path)
    drafts_dir = keys_dir / DRAFTS_NAME
    corrected_draft(drafts_dir, key=CHECKED_KEY)
    promote_key.promote(APP, drafts_dir, accept_verification=True)
    promoted = promoted_document(keys_dir, GROUND_TRUTH_SUFFIX)
    assert promoted["verified"] is True
    assert promoted["verified_by"] == CHECKED_BY
    assert promoted["verified_date"] == CHECKED_ON
    assert promoted["source"] == key_drafting.SOURCE


def test_the_promoted_key_lists_its_findings_in_the_documented_order(key) -> None:
    """Sorted by (file, line, id), which is what lets two revisions be diffed."""
    order = [(entry["file"], entry["line"], entry["id"]) for entry in key["findings"]]
    assert order == sorted(order)


def test_the_scorers_own_gate_accepts_the_promoted_key(key) -> None:
    """`harness.check_key` is what a real scoring run puts the key through first."""
    assert check_key(key, key_path(APP, GROUND_TRUTH_SUFFIX)) is key


def test_promotion_requires_exactly_the_entry_fields_the_schema_does() -> None:
    """Stricter than the schema is as wrong as looser, so the two lists are held equal.

    `key_promotion` checks the seven fields it would subscript and `code_anchor`
    has a refusal of its own; together that is the schema's required eight, and
    this fails in whichever direction the two drift apart.
    """
    assert set(ENTRY_FIELDS) | {ANCHOR_FIELD} == set(REQUIRED_ENTRY_FIELDS)
