"""Drafting a grading key is the last stage of a `--draft-key` run, and may never cost it anything.

`main._draft_key` runs after the artifacts are on disk and, on a URL run, after
they have been published. Every way it can fail -- no pin to draft against, a
draft already there, an unreachable model, an unwritable folder -- is a printed
reason and an exit code of zero, because the alternative is an audit that
succeeded being reported as a failure and its reports going unread.

Every run here passes `--draft-key`, which is what reaches the stage at all
since 2026-09-06. That the flag is also the *only* thing that reaches it is a
separate claim, held by `test_draft_key_flag.py`.

One boundary is asserted rather than assumed: the draft lands in the folder the
run was pointed at and **never in the repository's own `grading_keys/`** -- that
folder is committed evidence, and `key_drafting.DRAFTED_KEYS_DIR` is an absolute
path inside it, so a test that did not redirect it would write a model-authored
answer key into the project.

Nothing here clones, launches a process or reaches a model: the fetch, the
publish, Syft and both model calls are replaced at their seams, and the app is
written into `tmp_path`.
"""

from cli_helpers import run_cli, stub_model_unavailable
from draft_key_helpers import (
    DRAFT_KEY, drafted_key, drafting_model, drafting_prompts, fetched_tree)
from fetch_helpers import URL
from keys.grading_keys import GROUND_TRUTH_SUFFIX, discover_graded_apps, key_path
from keys.key_drafting import DRAFTED_KEYS_DIR as REAL_DRAFTS_DIR
from mixed_app_fixtures import APP_NAME
from pipeline_helpers import NO_LISTENER, record_publish


# --- a failed draft costs the run nothing -------------------------------------

def test_a_tree_with_no_pin_is_audited_published_and_left_unkeyed(monkeypatch,
                                                                  tmp_path) -> None:
    """A key's lines mean nothing without a commit, so it is refused -- after publishing."""
    fetched_tree(monkeypatch, tmp_path, pinned=False)
    drafting_model(monkeypatch)
    published = record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts, flags=DRAFT_KEY) == 0
    assert published == [(artifacts / APP_NAME, False, NO_LISTENER)]
    assert not drafted_key(tmp_path).exists()


def test_the_unpinned_run_says_which_stage_gave_up_and_why(monkeypatch, tmp_path,
                                                           capsys) -> None:
    """The reason names the missing commit, so this is a refusal and not a silent skip."""
    fetched_tree(monkeypatch, tmp_path, pinned=False)
    drafting_model(monkeypatch)
    record_publish(monkeypatch)
    run_cli(monkeypatch, URL, tmp_path / "artifacts", flags=DRAFT_KEY)
    printed = capsys.readouterr().err
    assert "no key drafted" in printed
    assert "no upstream commit could be read" in printed


def test_the_model_really_was_asked_to_draft(monkeypatch, tmp_path) -> None:
    """Guard: every test in this file would pass over a model that named nothing."""
    fetched_tree(monkeypatch, tmp_path, pinned=False)
    seen = drafting_model(monkeypatch)
    record_publish(monkeypatch)
    run_cli(monkeypatch, URL, tmp_path / "artifacts", flags=DRAFT_KEY)
    assert drafting_prompts(seen) != []


def test_an_unreachable_model_costs_the_run_neither_its_reports_nor_its_exit_code(
        monkeypatch, tmp_path, capsys) -> None:
    """The server being down is a reason to say so, never a reason to fail a finished audit."""
    fetched_tree(monkeypatch, tmp_path, pinned=True)
    stub_model_unavailable(monkeypatch)
    published = record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts, flags=DRAFT_KEY) == 0
    assert published == [(artifacts / APP_NAME, False, NO_LISTENER)]
    assert "no key drafted" in capsys.readouterr().err
    assert not drafted_key(tmp_path).exists()


# --- a pinned tree is drafted once --------------------------------------------

def test_a_pinned_tree_is_drafted_where_the_run_was_pointed(monkeypatch, tmp_path,
                                                            capsys) -> None:
    """The key lands in the folder nothing discovers, and the run says where it went."""
    fetched_tree(monkeypatch, tmp_path, pinned=True)
    drafting_model(monkeypatch)
    record_publish(monkeypatch)
    assert run_cli(monkeypatch, URL, tmp_path / "artifacts", flags=DRAFT_KEY) == 0
    assert drafted_key(tmp_path).is_file()
    assert "a draft, not an answer" in capsys.readouterr().out


def test_the_draft_never_lands_in_the_repositorys_own_keys(monkeypatch, tmp_path) -> None:
    """`grading_keys/` is committed evidence; a model-written key may not appear in it.

    The run really drafted one -- asserted first, or the three refusals below
    would hold over a run that never reached the stage -- and discovery over the
    real folder is compared before against after, which fails on a key landing
    there whether the folder held one to begin with or not.
    """
    fetched_tree(monkeypatch, tmp_path, pinned=True)
    drafting_model(monkeypatch)
    record_publish(monkeypatch)
    before = discover_graded_apps()
    run_cli(monkeypatch, URL, tmp_path / "artifacts", flags=DRAFT_KEY)
    assert drafted_key(tmp_path).is_file(), "the run reached the drafting stage"
    assert not key_path(APP_NAME, GROUND_TRUTH_SUFFIX).exists()
    assert not key_path(APP_NAME, GROUND_TRUTH_SUFFIX, REAL_DRAFTS_DIR).exists()
    assert discover_graded_apps() == before


def test_a_second_run_leaves_the_first_draft_exactly_as_it_was(monkeypatch, tmp_path) -> None:
    """A redraft would move every figure already scored against the first, so it is not made."""
    fetched_tree(monkeypatch, tmp_path, pinned=True)
    drafting_model(monkeypatch)
    record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts, flags=DRAFT_KEY) == 0
    first = drafted_key(tmp_path).read_bytes()
    assert run_cli(monkeypatch, URL, artifacts, flags=DRAFT_KEY) == 0
    assert drafted_key(tmp_path).read_bytes() == first
