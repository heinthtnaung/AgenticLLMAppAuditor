"""What `check_tree_matches_pin` does with a pin it cannot read, and with no pin at all.

The read itself -- and the three ways a hand edit breaks it -- is
`test_fetch_repo_pin_read.py`. This file is the caller every path reaches that
read through: `audit_run.report_pin_gap` prints what it returns, and
`web/source_routes._pin_note` renders it into the `unchecked` field of a source
window. Both had to be given a `ValueError` rather than an `AttributeError` or a
`PermissionError`, which is why the refusal is asserted *here* as well as at the
read.

**Two answers that are not refusals sit beside them**, because a check that
raised whatever it was given would satisfy every assertion about raising: a tree
whose pin is fine but whose history is gone is *reported*, and a tree nothing
pins at all is silence.

Which sentence reaches a reader, and the drifted-commit and dirty-tree cases
that need a history to compare against, is `tests/web/test_source_pin_notes.py`.

Nothing here clones or runs git: a tree with no `.git` never reaches `read_pin`,
and every file is written into `tmp_path`.
"""

import pytest

import fetch_repo
from fetch_helpers import (
    HALF_SAVED, NAME, UNPARSEABLE, WRONG_SHAPE, a_fetched_pin, a_pin, a_pinned_tree)
from keys import grading_keys
from keys.grading_keys import MANIFEST_SUFFIX

# What `check_tree_matches_pin` can only ever say about a tool-fetched tree: the
# fetch deleted the history that would answer.
CANNOT_BE_CHECKED = "carries no history"

# What it says about a tree nothing pins at all: nothing, because there is no
# claim to make.
NOTHING_PINS_IT = ""


def test_the_tree_check_passes_the_pins_refusal_through(tmp_path) -> None:
    """A `ValueError` and not an `AttributeError`, at the function both callers call."""
    a_pin(tmp_path, "[]")
    with pytest.raises(ValueError, match=WRONG_SHAPE):
        fetch_repo.check_tree_matches_pin(a_pinned_tree(tmp_path))


def test_the_hand_written_grading_key_pin_is_guarded_too(tmp_path, monkeypatch) -> None:
    """The fallback pin is the one a person types, which is why the guard exists at all.

    A hand-cloned tree carries no fetch manifest, so `_pin_for` consults
    `grading_keys/<app>.manifest.json`. `KEYS_DIR` is redirected under
    `tmp_path` first: the checkout's own folder holds real work and no test
    writes there.
    """
    keys_dir = tmp_path / "grading_keys"
    keys_dir.mkdir()
    monkeypatch.setattr(grading_keys, "KEYS_DIR", keys_dir)
    (keys_dir / f"{NAME}{MANIFEST_SUFFIX}").write_text(HALF_SAVED, encoding="utf-8")
    with pytest.raises(ValueError, match=UNPARSEABLE):
        fetch_repo.check_tree_matches_pin(a_pinned_tree(tmp_path))


def test_a_pinned_tree_with_no_history_is_reported_rather_than_refused(tmp_path) -> None:
    """The ordinary case a fetch leaves, so the refusals above are not the only outcome."""
    a_fetched_pin(tmp_path)
    assert CANNOT_BE_CHECKED in fetch_repo.check_tree_matches_pin(a_pinned_tree(tmp_path))


def test_a_tree_nothing_pins_is_answered_with_silence(tmp_path, monkeypatch) -> None:
    """No pin is no claim: there is nothing to check against and nothing to report."""
    monkeypatch.setattr(grading_keys, "KEYS_DIR", tmp_path / "grading_keys")
    assert fetch_repo.check_tree_matches_pin(a_pinned_tree(tmp_path)) == NOTHING_PINS_IT
