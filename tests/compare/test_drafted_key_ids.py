"""Two entries, one surface, ids `1` and `"K-02"` -- and no hand edit anywhere.

**The first of this family a *model reply* is enough to cause.** Every earlier
one needed a person to edit a key or a pin; this one needed the model to label
one entry with a number. `key_document` sorts its entries on `(file, line, id)`,
so the pair reached `sorted` and raised:

    TypeError: '<' not supported between instances of 'str' and 'int'
      in pipeline.DRAFTING_FAILURES? False
      in main.EXPECTED_FAILURES?    False

In neither list, so `--draft-key` ended in a traceback **after the audit had
succeeded and every artifact was already on disk** -- which falsifies
`main._draft_key`'s own docstring, that every failure there is a printed reason
and an exit code of zero. The same reach from `compare_run.ensure_key`, and from
the web wrapper's `draft_key` option as a *failed run row over a successful
audit*.

`key_drafting._is_grounded` bounded `owasp_id`, `file` and `line` against the
extracted surfaces and simply did not bound `id`. It does now, and **drops
rather than coerces**: an entry the model labelled with a number is an entry it
did not label, and inventing `K-04` for it would put a name in ground truth that
nothing chose.

Both drafting callers are driven here, because the harness's type check does not
close this path: `check_key` is never consulted while a draft is being *written*.
What `draft()` itself makes of the reply is
`tests/compare/test_key_drafting_entries.py`; the whole `--draft-key` run is
`tests/cli/test_pipeline_draft_key.py`; the reading half -- a key already on disk
with a wrong-typed id -- is `harness.TYPED_ENTRY_FIELDS` and its three test
files.

Nothing here reaches a model, clones or launches a process: the app is written
into `tmp_path` and `ask` is a function the test wrote.
"""

import json
from pathlib import Path

import compare_run
import fetch_repo
import main
import pipeline
from draft_key_helpers import (
    BOTH_LABELLED_REPLY, LABELLED_ID, MIXED_ID_REPLY, drafts_dir)
from fetch_helpers import COMMIT, COMMIT_DATE, URL
from keys import key_drafting
from mixed_app_fixtures import APP_NAME, write_mixed_app

# What survives the reply: the entry the model really labelled, and only it.
KEPT_IDS = [LABELLED_ID]

# What survives when both entries are labelled -- the off position that says the
# drop is about the *type* of the id and not about two entries on one surface.
BOTH_IDS = ["K-01", LABELLED_ID]

# The class the sort raised, which neither list of expected failures holds.
ESCAPING_CLASS = TypeError


def a_pinned_app(tmp_path: Path) -> Path:
    """The mixed-language app written into `tmp_path`, with the pin a draft is anchored by."""
    repo = write_mixed_app(tmp_path)
    fetch_repo.write_manifest(
        tmp_path, fetch_repo.manifest(APP_NAME, URL, COMMIT, COMMIT_DATE))
    return repo


def answering_with(reply: str):
    """An `ask` that answers every prompt with one canned model reply."""
    return lambda prompt: reply


def entry_ids(path: Path) -> list:
    """The ids of the entries a drafted key on disk holds, in the order it holds them."""
    return [entry["id"]
            for entry in json.loads(path.read_text(encoding="utf-8"))["findings"]]


def drafted_by_the_pipeline(tmp_path: Path, reply: str) -> Path:
    """Run the pipeline's drafting stage over that reply, failing with anything that escaped.

    Deliberately not `pytest.raises`: the claim is the opposite one. The defect
    was an exception reaching a caller written for a different class, so the
    failure message names what escaped.
    """
    repo = a_pinned_app(tmp_path)
    try:
        written = pipeline.draft_key(repo, answering_with(reply), drafts_dir(tmp_path))
    except BaseException as escaped:  # noqa: BLE001 - the class that escapes is the defect
        raise AssertionError(f"draft_key raised {type(escaped).__name__} instead of "
                             f"drafting: {escaped}") from escaped
    assert written is not None, "the stage drafted nothing at all"
    return written


def drafted_by_the_comparison(monkeypatch, tmp_path: Path, reply: str) -> Path:
    """The same reply through the other caller, which writes into the drafts folder."""
    repo = a_pinned_app(tmp_path)
    monkeypatch.setattr(key_drafting, "DRAFTED_KEYS_DIR", drafts_dir(tmp_path))
    try:
        written = compare_run.ensure_key(APP_NAME, repo, {"ask": answering_with(reply)})
    except BaseException as escaped:  # noqa: BLE001 - the class that escapes is the defect
        raise AssertionError(f"ensure_key raised {type(escaped).__name__} instead of "
                             f"drafting: {escaped}") from escaped
    assert written is not None, "the comparison drafted nothing at all"
    return written


# --- the stage that runs after the audit has already succeeded -------------------

def test_the_pipeline_stage_writes_a_draft_rather_than_raising(tmp_path) -> None:
    """The fault itself: this reply used to be a traceback out of a finished run."""
    assert drafted_by_the_pipeline(tmp_path, MIXED_ID_REPLY).is_file()


def test_the_entry_the_model_labelled_with_a_number_is_dropped(tmp_path) -> None:
    """Dropped, not coerced: an entry labelled with a number is one the model did not label."""
    assert entry_ids(drafted_by_the_pipeline(tmp_path, MIXED_ID_REPLY)) == KEPT_IDS


def test_the_count_the_document_declares_matches_what_it_kept(tmp_path) -> None:
    """A dropped entry has to leave the count behind it, or promotion refuses the draft."""
    written = drafted_by_the_pipeline(tmp_path, MIXED_ID_REPLY)
    document = json.loads(written.read_text(encoding="utf-8"))
    assert document["finding_count"] == len(KEPT_IDS)


# --- and the same reply through the comparison's own drafter ---------------------

def test_the_comparison_writes_a_draft_rather_than_raising(monkeypatch, tmp_path) -> None:
    """`ensure_key` reaches the identical sort, and the harness's check guards neither."""
    assert drafted_by_the_comparison(monkeypatch, tmp_path, MIXED_ID_REPLY).is_file()


def test_the_comparison_drops_the_numeric_entry_too(monkeypatch, tmp_path) -> None:
    """One rule in `_is_grounded`, so both callers answer the same thing."""
    written = drafted_by_the_comparison(monkeypatch, tmp_path, MIXED_ID_REPLY)
    assert entry_ids(written) == KEPT_IDS


# --- the off position: it is the type that drops it, not the duplication ---------

def test_two_properly_labelled_entries_on_one_surface_are_both_kept(tmp_path) -> None:
    """Without this, a drafter that dropped every second entry would pass every test above.

    Two entries on one surface is a *promotion* refusal -- `_colliding_pairs`
    names the pair -- and it is not a drafting one. The draft records what the
    model said; the human correcting it decides which entry to keep.
    """
    written = drafted_by_the_pipeline(tmp_path, BOTH_LABELLED_REPLY)
    assert sorted(entry_ids(written)) == BOTH_IDS


# --- why it was a traceback rather than a printed reason -------------------------

def test_the_class_the_sort_raised_is_in_neither_list_of_expected_failures() -> None:
    """The reason this cost the run its report: nothing along the way was written for it."""
    assert not any(issubclass(ESCAPING_CLASS, held)
                   for held in pipeline.DRAFTING_FAILURES)
    assert not any(issubclass(ESCAPING_CLASS, held)
                   for held in main.EXPECTED_FAILURES)
