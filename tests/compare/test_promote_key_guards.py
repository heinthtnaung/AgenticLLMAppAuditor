"""What `promote_key` refuses to move, and the folder no test may write into.

Two refusals stand between a draft and the keys a run is scored against:

* a draft `key_promotion` is not satisfied with is not moved, and the command
  repeats every reason rather than moving it and letting the suite explain the
  fault later in six failures a reader has to reverse-engineer;
* a key already at the top level is never overwritten, because promoting over
  one would replace the answer every published figure was measured against.

The last test is the safety net for this whole family of files: `grading_keys/`
is this project's committed evidence, so after a promotion has run to completion
against `tmp_path`, the real folder still holds exactly the bytes it held
before. `REAL_KEYS_DIR` is captured at import, before any test redirects the
constant.
"""

import json
import re
from pathlib import Path

import grading_keys
import key_promotion
import promote_key
import pytest
from drafted_key_fixtures import (
    APP,
    DRAFTS_NAME,
    ENTRY,
    corrected_draft,
    fit_key,
    fit_pin,
    redirect_keys_dir,
)
from grading_keys import (
    GROUND_TRUTH_SUFFIX,
    MANUAL_REVIEW,
    discover_graded_apps,
    key_path,
)
from shipped_key_fixtures import SHIPPED_APPS

# The real folder, bound before any redirection, so the net below is over the
# committed evidence and not over whatever a fixture pointed the constant at.
REAL_KEYS_DIR = grading_keys.KEYS_DIR

# A key already being scored against, told apart from the draft by its source.
HAND_WRITTEN_KEY = {**fit_key(), "source": MANUAL_REVIEW}

# A draft with one fault: the entries the model replied with, never anchored.
UNANCHORED_KEY = fit_key((ENTRY,))


@pytest.fixture
def keys_dir(monkeypatch, tmp_path) -> Path:
    """An empty keys folder under `tmp_path`, with `KEYS_DIR` pointed at it."""
    return redirect_keys_dir(monkeypatch, tmp_path)


@pytest.fixture
def drafts_dir(keys_dir: Path) -> Path:
    """The drafts folder one level down, where a draft waits to be promoted."""
    return keys_dir / DRAFTS_NAME


def shipped_bytes() -> dict[str, bytes]:
    """Every file in the real grading keys folder, by name, as it is on disk."""
    return {path.name: path.read_bytes()
            for path in sorted(REAL_KEYS_DIR.iterdir()) if path.is_file()}


# --- a draft that is not ready -------------------------------------------------

def test_an_unfit_draft_is_refused_with_every_reason(drafts_dir) -> None:
    """The command repeats `refusals` rather than inventing a message of its own."""
    corrected_draft(drafts_dir, key=UNANCHORED_KEY)
    with pytest.raises(ValueError) as refused:
        promote_key.promote(APP, drafts_dir)
    for reason in key_promotion.refusals(UNANCHORED_KEY, fit_pin()):
        assert reason in str(refused.value)


def test_the_refusal_names_the_draft_it_read(drafts_dir) -> None:
    """A reader has to know which file to open and correct."""
    draft = corrected_draft(drafts_dir, key=UNANCHORED_KEY)
    with pytest.raises(ValueError, match=re.escape(str(draft))):
        promote_key.promote(APP, drafts_dir)


def test_two_faults_are_both_reported(drafts_dir) -> None:
    """One run of the command, one list of everything to fix."""
    corrected_draft(drafts_dir, key=UNANCHORED_KEY, pin=fit_pin(framework=""))
    with pytest.raises(ValueError) as refused:
        promote_key.promote(APP, drafts_dir)
    message = str(refused.value)
    assert "code_anchor" in message and "framework" in message


def test_a_refused_draft_is_left_exactly_where_it_was(keys_dir, drafts_dir) -> None:
    """Nothing is half-moved: the pair is still a draft, and no app was enrolled."""
    draft = corrected_draft(drafts_dir, key=UNANCHORED_KEY)
    with pytest.raises(ValueError):
        promote_key.promote(APP, drafts_dir)
    assert draft.is_file()
    assert discover_graded_apps(keys_dir) == ()


# --- a key that is already being scored against --------------------------------

def test_promotion_never_overwrites_a_shipped_key(keys_dir, drafts_dir) -> None:
    """Replacing the answer a published figure was measured against is refused by name."""
    corrected_draft(keys_dir, key=HAND_WRITTEN_KEY)
    corrected_draft(drafts_dir)
    with pytest.raises(FileExistsError, match=APP):
        promote_key.promote(APP, drafts_dir)


def test_the_shipped_key_is_untouched_by_the_refusal(keys_dir, drafts_dir) -> None:
    """The refusal is what matters, so what it protected is asserted rather than assumed."""
    existing = corrected_draft(keys_dir, key=HAND_WRITTEN_KEY)
    before = existing.read_bytes()
    corrected_draft(drafts_dir)
    with pytest.raises(FileExistsError):
        promote_key.promote(APP, drafts_dir)
    assert existing.read_bytes() == before
    assert json.loads(existing.read_text(encoding="utf-8"))["source"] == MANUAL_REVIEW


def test_the_draft_survives_the_refusal(keys_dir, drafts_dir) -> None:
    """Neither file moves, so the draft can still be renamed and promoted under another name."""
    corrected_draft(keys_dir, key=HAND_WRITTEN_KEY)
    draft = corrected_draft(drafts_dir)
    with pytest.raises(FileExistsError):
        promote_key.promote(APP, drafts_dir)
    assert draft.is_file()


# --- the folder that is committed evidence -------------------------------------

def test_a_promotion_writes_nothing_into_the_real_keys_folder(drafts_dir) -> None:
    """The net under every test here: a whole promotion, and the evidence unchanged."""
    before = shipped_bytes()
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert shipped_bytes() == before


def test_the_real_folder_still_ships_exactly_the_keys_it_shipped(drafts_dir) -> None:
    """Stated against discovery too: a promoted draft enrols no app in the real folder."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert discover_graded_apps(REAL_KEYS_DIR) == SHIPPED_APPS


def test_the_real_folder_is_not_empty(drafts_dir) -> None:
    """Guard: an empty folder would make both tests above hold over nothing."""
    assert shipped_bytes()
    assert key_path(SHIPPED_APPS[0], GROUND_TRUTH_SUFFIX, REAL_KEYS_DIR).is_file()
