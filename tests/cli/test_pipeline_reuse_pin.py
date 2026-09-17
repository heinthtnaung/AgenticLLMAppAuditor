"""The pin a reuse is decided by: what it may hold, and when two URLs are one tree.

Two claims, and they arrived together. `canonical_url` was added so a pin
written `.../demo` matches a request for `.../demo.git` -- both land on
`fetched/demo`, so a pin that disagreed with the directory refused a re-audit of
a tree that had been fetched correctly. Nothing asserted that behaviour.

Routing both sides of the comparison through that function also **took a string
for granted**, and the comparison it replaced had not: `held != url` refused a
non-string pin for free, because `123 != "https://..."`. So a hand-edited or
truncated pin turned a named `ValueError` into
`AttributeError: 'int' object has no attribute 'rstrip'` -- a class
`main.EXPECTED_FAILURES` does not list, on the audit path, reachable from an
unauthenticated `POST /api/audit` whenever `fetched/<name>/` already exists.
**The first section is that regression**, and it fails again the moment a future
edit makes the comparison smarter and drops the type check with it.

The pin's *absent* `upstream_url` is `test_pipeline.py`'s
`test_a_pin_without_an_upstream_url_is_a_message_not_a_traceback`: presence was
already held, and what was missing was type. `canonical_url` itself is
`tests/test_repo_url_canonical.py`.

The fetch stage is stubbed throughout and the download root is always under
`tmp_path`, so nothing here clones or opens a socket.
"""

import json
from pathlib import Path

import pytest

import pipeline
from fetch_helpers import NAME, URL
from guarded_read import refusal_from
from pipeline_helpers import plant_tree, point_download_root, record_fetch, write_pin

# The same repository as `fetch_helpers.URL`, spelled the other two ways a pin
# or a request can carry it. `URL` itself ends in `.git`.
PLAIN_URL = "https://github.com/owner/demo"
SLASHED_URL = "https://github.com/owner/demo/"

# Another owner's repository of the same name, which lands on the same directory
# and must still be refused however either side is spelled.
ANOTHER_OWNER_URL = "https://github.com/somebody-else/demo"

# What a hand edit or a truncated write leaves where the URL belongs. Every one
# of them used to reach `.rstrip` and escape as an `AttributeError`.
NOT_A_URL = {"an int": 123, "a list": [PLAIN_URL], "null": None}
NOT_A_URL_IDS = list(NOT_A_URL)
NOT_A_URL_SHAPES = list(NOT_A_URL.values())


def pin_holding(root: Path, shape: object) -> Path:
    """Leave the pin a real fetch wrote, with `upstream_url` replaced by a hand edit."""
    path = write_pin(root)
    record = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**record, "upstream_url": shape}), encoding="utf-8")
    return path


def a_reusable_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                    pinned_as: str = URL) -> tuple[Path, list[str]]:
    """A fetched tree with a pin naming `pinned_as`, and the record of any fetch."""
    root = point_download_root(monkeypatch, tmp_path)
    tree = plant_tree(root)
    write_pin(root, url=pinned_as)
    return tree, record_fetch(monkeypatch)


# --- the regression: a pin whose URL is not a string -----------------------------

@pytest.mark.parametrize("shape", NOT_A_URL_SHAPES, ids=NOT_A_URL_IDS)
def test_a_pin_whose_url_is_not_a_string_is_refused_by_name(monkeypatch, tmp_path,
                                                            shape: object) -> None:
    """The class is the subject: `ValueError` is expected, `AttributeError` is the defect.

    `refusal_from` rather than `pytest.raises`, because an `AttributeError`
    reaching `main` is the wrong *answer* and not an error in this test.
    """
    root = point_download_root(monkeypatch, tmp_path)
    plant_tree(root)
    pin_holding(root, shape)
    record_fetch(monkeypatch)
    raised = refusal_from(lambda: pipeline.resolve_repo(URL), "resolve_repo")
    assert isinstance(raised, ValueError), (
        f"a pin holding {shape!r} escaped as {type(raised).__name__}: {raised}")


@pytest.mark.parametrize("shape", NOT_A_URL_SHAPES, ids=NOT_A_URL_IDS)
def test_the_refusal_names_the_directory_and_the_url_that_was_asked_for(
        monkeypatch, tmp_path, shape: object) -> None:
    """A reader has to be told which tree to remove, not only that something is wrong."""
    root = point_download_root(monkeypatch, tmp_path)
    plant_tree(root)
    pin_holding(root, shape)
    record_fetch(monkeypatch)
    message = str(refusal_from(lambda: pipeline.resolve_repo(URL), "resolve_repo"))
    assert str(root / NAME) in message
    assert URL in message


@pytest.mark.parametrize("shape", NOT_A_URL_SHAPES, ids=NOT_A_URL_IDS)
def test_a_pin_it_cannot_read_is_never_fetched_over(monkeypatch, tmp_path,
                                                    shape: object) -> None:
    """The refusal is the end of it: a tree that is there is not re-cloned on top."""
    root = point_download_root(monkeypatch, tmp_path)
    plant_tree(root)
    pin_holding(root, shape)
    calls = record_fetch(monkeypatch)
    refusal_from(lambda: pipeline.resolve_repo(URL), "resolve_repo")
    assert calls == []


# --- the reuse the canonical comparison was added to produce ---------------------

def test_a_pin_without_the_suffix_matches_a_request_carrying_it(monkeypatch,
                                                                tmp_path) -> None:
    """The case the function exists for: one directory, two spellings, one repository."""
    tree, calls = a_reusable_tree(monkeypatch, tmp_path, pinned_as=PLAIN_URL)
    assert pipeline.resolve_repo(URL) == tree
    assert calls == []


def test_a_pin_carrying_the_suffix_matches_a_request_without_it(monkeypatch,
                                                                tmp_path) -> None:
    """The other direction, because a pin is written by whichever spelling was asked first."""
    tree, calls = a_reusable_tree(monkeypatch, tmp_path, pinned_as=URL)
    assert pipeline.resolve_repo(PLAIN_URL) == tree
    assert calls == []


def test_a_trailing_slash_on_either_side_is_still_one_repository(monkeypatch,
                                                                 tmp_path) -> None:
    """A link pasted from an address bar carries one; the tree it names is the same tree."""
    tree, calls = a_reusable_tree(monkeypatch, tmp_path, pinned_as=SLASHED_URL)
    assert pipeline.resolve_repo(URL) == tree
    assert calls == []


# --- the off position the whole comparison exists for ----------------------------

def test_another_owners_repository_is_refused_however_it_is_spelled(monkeypatch,
                                                                    tmp_path) -> None:
    """Canonicalising both sides may not make two owners' `demo` into one tree.

    Without this, a `canonical_url` that returned the last path segment -- or
    anything else that agreed here -- would pass every reuse test above while
    handing an audit the wrong repository.
    """
    _tree, calls = a_reusable_tree(monkeypatch, tmp_path, pinned_as=ANOTHER_OWNER_URL)
    raised = refusal_from(lambda: pipeline.resolve_repo(URL), "resolve_repo")
    assert isinstance(raised, ValueError), raised
    assert ANOTHER_OWNER_URL in str(raised)
    assert calls == []
