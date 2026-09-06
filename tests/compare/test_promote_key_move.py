"""Promoting a corrected draft: what moves, and what a promotion must not change.

`python src/promote_key.py <app>` is the step where a human takes responsibility
for a drafted key. It moves the pair up one level, out of `grading_keys/drafts/`
and into `grading_keys/`, and that move is the entire feature: nothing discovers
a draft, so nothing scores against one until it has been promoted. The pair of
assertions in `test_promotion_is_what_enrols_the_app_for_scoring` is the point.

**The destination is redirected, never the real folder.** `promote` takes
`drafts_dir` but resolves its destination through `key_path`, which reads
`grading_keys.KEYS_DIR` at call time -- the seam that constant's docstring
exists for, and the one `test_drafted_key_pin.py` already promotes through.
`redirect_keys_dir` points it at `tmp_path`; `test_promote_key_guards.py` holds
the real folder untouched afterwards.

What promotion deliberately does **not** do is edit either document: `source`
and `verified` survive it, because a human correcting entries does not undo the
tool having chosen which lines were candidates.
"""

import json
from pathlib import Path

import promote_key
import pytest
from drafted_key_fixtures import (
    APP,
    DRAFTS_NAME,
    corrected_draft,
    redirect_keys_dir,
)
from keys.grading_keys import (
    GROUND_TRUTH_SUFFIX,
    MANIFEST_SUFFIX,
    TOOL_DRAFTED,
    discover_graded_apps,
    key_path,
)


@pytest.fixture
def keys_dir(monkeypatch, tmp_path) -> Path:
    """An empty keys folder under `tmp_path`, with `KEYS_DIR` pointed at it."""
    return redirect_keys_dir(monkeypatch, tmp_path)


@pytest.fixture
def drafts_dir(keys_dir: Path) -> Path:
    """The drafts folder one level down, where a corrected draft waits."""
    return keys_dir / DRAFTS_NAME


def promoted_key(keys_dir: Path) -> dict:
    """The key document sitting at the top level after a promotion."""
    return json.loads(key_path(APP, GROUND_TRUTH_SUFFIX,
                               keys_dir).read_text(encoding="utf-8"))


# --- both files arrive, and neither is left behind ----------------------------

def test_the_key_arrives_at_the_top_level(keys_dir, drafts_dir) -> None:
    """Where `discover_graded_apps` globs, which is what makes the app scoreable."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert key_path(APP, GROUND_TRUTH_SUFFIX, keys_dir).is_file()


def test_the_pin_arrives_beside_it(keys_dir, drafts_dir) -> None:
    """A key without its pin is refused by discovery, so both files move or neither does."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert key_path(APP, MANIFEST_SUFFIX, keys_dir).is_file()


def test_neither_draft_file_is_left_behind(drafts_dir) -> None:
    """A move, not a copy: a leftover draft would be re-promotable and then refused."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert not key_path(APP, GROUND_TRUTH_SUFFIX, drafts_dir).exists()
    assert not key_path(APP, MANIFEST_SUFFIX, drafts_dir).exists()


def test_promote_returns_where_the_key_went(keys_dir, drafts_dir) -> None:
    """The caller is told the path rather than having to rebuild it."""
    corrected_draft(drafts_dir)
    assert promote_key.promote(APP, drafts_dir) == key_path(
        APP, GROUND_TRUTH_SUFFIX, keys_dir)


# --- what the move is for -----------------------------------------------------

def test_a_corrected_draft_alone_enrols_no_app(keys_dir, drafts_dir) -> None:
    """The guard: discovery is non-recursive, so the test below starts from nothing."""
    corrected_draft(drafts_dir)
    assert discover_graded_apps(keys_dir) == ()


def test_promotion_is_what_enrols_the_app_for_scoring(keys_dir, drafts_dir) -> None:
    """The whole feature: a run is scored against this key only once it has moved."""
    corrected_draft(drafts_dir)
    assert discover_graded_apps(keys_dir) == ()
    promote_key.promote(APP, drafts_dir)
    assert discover_graded_apps(keys_dir) == (APP,)


# --- and what it must not change ----------------------------------------------

def test_the_key_is_moved_byte_for_byte(keys_dir, drafts_dir) -> None:
    """Promotion moves a document a human corrected; editing it would discard that."""
    draft = corrected_draft(drafts_dir)
    before = draft.read_bytes()
    promote_key.promote(APP, drafts_dir)
    assert key_path(APP, GROUND_TRUTH_SUFFIX, keys_dir).read_bytes() == before


def test_the_pin_is_moved_byte_for_byte(keys_dir, drafts_dir) -> None:
    """The same for the manifest: the framework and language a human filled in survive."""
    corrected_draft(drafts_dir)
    before = key_path(APP, MANIFEST_SUFFIX, drafts_dir).read_bytes()
    promote_key.promote(APP, drafts_dir)
    assert key_path(APP, MANIFEST_SUFFIX, keys_dir).read_bytes() == before


def test_the_promoted_key_still_says_the_tool_drafted_it(keys_dir, drafts_dir) -> None:
    """The qualification outlives promotion: correcting entries does not undo the
    tool having chosen which lines were candidates."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert promoted_key(keys_dir)["source"] == TOOL_DRAFTED


def test_promotion_does_not_tick_verified(keys_dir, drafts_dir) -> None:
    """Verification is a separate, deliberate edit; promoting is not a human signing off."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    key = promoted_key(keys_dir)
    assert key["verified"] is False
    assert key["verified_by"] is None and key["verified_date"] is None
