"""The pin a promoted key ships beside it, held to a shipped pin's rules.

`tests/test_shipped_grading_pin.py` is the authority and its field lists are
imported: a promoted manifest is a graded app's manifest, and the one place the
two producers differ -- `framework` and `language`, which a fetcher cannot know
-- is exactly what `key_promotion` refuses a draft for. That refusal and this
requirement are the same rule seen from both ends, which is why this file exists
rather than being taken on trust.
"""

from pathlib import Path

import pytest
from drafted_key_fixtures import APP, promote_one_draft, promoted_document
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX
from test_shipped_grading_pin import (
    COMMIT_LENGTH,
    GRADED_PIN_FIELDS,
    HTTPS_PREFIX,
    PIN_ROLES,
    REQUIRED_PIN_FIELDS,
)


@pytest.fixture
def keys_dir(monkeypatch, tmp_path) -> Path:
    """A temporary keys folder with one corrected draft promoted into it."""
    return promote_one_draft(monkeypatch, tmp_path)


@pytest.fixture
def pin(keys_dir: Path) -> dict:
    """The manifest of one promoted key, read from beside the key."""
    return promoted_document(keys_dir, MANIFEST_SUFFIX)


def test_the_promoted_pin_names_the_app_it_pins(pin) -> None:
    """The guard and the join: a pin naming another app pins nothing about this one."""
    assert pin["name"] == APP


def test_the_promoted_pin_agrees_with_the_key_it_moved_with(keys_dir, pin) -> None:
    """Two files, one commit: a key scored against another one scores the wrong lines."""
    key = promoted_document(keys_dir, GROUND_TRUTH_SUFFIX)
    assert key["upstream_commit"] == pin["upstream_commit"]


def test_the_promoted_pin_carries_every_required_field(pin) -> None:
    """The pin is the only surviving evidence of what the key was read against."""
    assert [field for field in REQUIRED_PIN_FIELDS if field not in pin] == []


def test_the_promoted_pin_names_a_full_commit(pin) -> None:
    """An abbreviated sha is ambiguous, and a pin that is ambiguous pins nothing."""
    commit = pin["upstream_commit"]
    assert len(commit) == COMMIT_LENGTH and commit.isalnum()


def test_the_promoted_pin_is_an_https_url(pin) -> None:
    """The same rule `fetch_repo` enforces, so the pinned commit can really be re-fetched."""
    assert pin["upstream_url"].startswith(HTTPS_PREFIX)


def test_the_promoted_pin_declares_a_known_role(pin) -> None:
    """`role` has a documented vocabulary of three, and nothing under `src/` enforces it."""
    assert pin["role"] in PIN_ROLES


def test_the_promoted_pin_says_what_the_app_exercises(pin) -> None:
    """`framework` and `language` are required of a graded app's pin, and refused without."""
    assert [field for field in GRADED_PIN_FIELDS if field not in pin] == []
