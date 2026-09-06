"""Drafting a grading key is the last stage of a URL run, and it may never cost it anything.

`main._draft_key` runs after the artifacts are on disk and after they have been
published. Every way it can fail -- no pin to draft against, a draft already
there, an unreachable model, an unwritable folder -- is a printed reason and an
exit code of zero, because the alternative is an audit that succeeded being
reported as a failure and its reports going unread.

Two boundaries are asserted rather than assumed. A **local path drafts
nothing**: a key pins line numbers to a commit, and a directory this project did
not fetch may be at no commit at all. And the draft lands in the folder the run
was pointed at and **never in the repository's own `grading_keys/`** -- that
folder is committed evidence, and `key_drafting.DRAFTED_KEYS_DIR` is an absolute
path inside it, so a test that did not redirect it would write a model-authored
answer key into the project.

Nothing here clones, launches a process or reaches a model: the fetch, the
publish, Syft and both model calls are replaced at their seams, and the app is
written into `tmp_path`.
"""

from pathlib import Path

import fetch_repo
from keys import key_drafting
import model_client
from cli_helpers import (
    EMPTY_SCAN, STUB_ADVICE, run_cli, stub_model, stub_model_unavailable, stub_syft)
from fetch_helpers import COMMIT, COMMIT_DATE, URL
from keys.grading_keys import GROUND_TRUTH_SUFFIX, discover_graded_apps, key_path
from keys.key_drafting import DRAFTED_KEYS_DIR as REAL_DRAFTS_DIR
from mixed_app_fixtures import APP_NAME, PYTHON_FILE, write_mixed_app
from pipeline_helpers import point_download_root, record_fetch, record_publish
from shipped_key_fixtures import SHIPPED_APPS

# The sentence `key_drafting.PROMPT` opens with, which tells the stubbed model
# which of the run's two questions it is being asked.
DRAFTING_MARKER = "drafting a security grading key"

# One entry on the tool call the mixed app really carries, so the model names a
# defect the extractor found and the draft is not refused as ungrounded.
TOOL_LINE = 7
DRAFTED_REPLY = (
    '[{"id": "K-01", "file": "%s", "line": %d, "owasp_id": "LLM06", '
    '"llm_surface": "TOOL_CALL", "surface_name": "ShellTool", "component": null, '
    '"detection": "static", "title": "A shell tool", "description": "why"}]'
) % (PYTHON_FILE, TOOL_LINE)


def drafts_dir(tmp_path: Path) -> Path:
    """Where a drafted key goes in a test: a tmp_path stand-in for grading_keys/drafts/."""
    return tmp_path / "grading_keys" / "drafts"


def drafting_model(monkeypatch) -> list[str]:
    """Answer the drafting question with one entry and everything else with advice."""
    seen: list[str] = []

    def answer(prompt: str, model: str | None = None) -> str:
        """Record the prompt, then reply as the model the run expects."""
        seen.append(prompt)
        return DRAFTED_REPLY if DRAFTING_MARKER in prompt else STUB_ADVICE

    stub_model(monkeypatch)
    monkeypatch.setattr(model_client, "ask", answer)
    return seen


def stage(monkeypatch, tmp_path: Path, pinned: bool) -> Path:
    """Plant the tree a fetch would return, redirect the drafts folder, stub the rest."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    root = point_download_root(monkeypatch, tmp_path)
    repo = write_mixed_app(root)
    if pinned:
        fetch_repo.write_manifest(
            root, fetch_repo.manifest(APP_NAME, URL, COMMIT, COMMIT_DATE))
    record_fetch(monkeypatch, result=repo)
    monkeypatch.setattr(key_drafting, "DRAFTED_KEYS_DIR", drafts_dir(tmp_path))
    return repo


def drafted_key(tmp_path: Path) -> Path:
    """Where this run's drafted key should have landed."""
    return key_path(APP_NAME, GROUND_TRUTH_SUFFIX, drafts_dir(tmp_path))


# --- a failed draft costs the run nothing -------------------------------------

def test_a_tree_with_no_pin_is_audited_published_and_left_unkeyed(monkeypatch,
                                                                  tmp_path) -> None:
    """A key's lines mean nothing without a commit, so it is refused -- after publishing."""
    stage(monkeypatch, tmp_path, pinned=False)
    drafting_model(monkeypatch)
    published = record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts) == 0
    assert published == [(artifacts / APP_NAME, False)]
    assert not drafted_key(tmp_path).exists()


def test_the_unpinned_run_says_which_stage_gave_up_and_why(monkeypatch, tmp_path,
                                                           capsys) -> None:
    """The reason names the missing commit, so this is a refusal and not a silent skip."""
    stage(monkeypatch, tmp_path, pinned=False)
    drafting_model(monkeypatch)
    record_publish(monkeypatch)
    run_cli(monkeypatch, URL, tmp_path / "artifacts")
    printed = capsys.readouterr().err
    assert "no key drafted" in printed
    assert "no upstream commit could be read" in printed


def test_the_model_really_was_asked_to_draft(monkeypatch, tmp_path) -> None:
    """Guard: every test in this file would pass over a model that named nothing."""
    stage(monkeypatch, tmp_path, pinned=False)
    seen = drafting_model(monkeypatch)
    record_publish(monkeypatch)
    run_cli(monkeypatch, URL, tmp_path / "artifacts")
    assert [prompt for prompt in seen if DRAFTING_MARKER in prompt] != []


def test_an_unreachable_model_costs_the_run_neither_its_reports_nor_its_exit_code(
        monkeypatch, tmp_path, capsys) -> None:
    """The server being down is a reason to say so, never a reason to fail a finished audit."""
    stage(monkeypatch, tmp_path, pinned=True)
    stub_model_unavailable(monkeypatch)
    published = record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts) == 0
    assert published == [(artifacts / APP_NAME, False)]
    assert "no key drafted" in capsys.readouterr().err
    assert not drafted_key(tmp_path).exists()


# --- a pinned tree is drafted once --------------------------------------------

def test_a_pinned_tree_is_drafted_where_the_run_was_pointed(monkeypatch, tmp_path,
                                                            capsys) -> None:
    """The key lands in the folder nothing discovers, and the run says where it went."""
    stage(monkeypatch, tmp_path, pinned=True)
    drafting_model(monkeypatch)
    record_publish(monkeypatch)
    assert run_cli(monkeypatch, URL, tmp_path / "artifacts") == 0
    assert drafted_key(tmp_path).is_file()
    assert "a draft, not an answer" in capsys.readouterr().out


def test_the_draft_never_lands_in_the_repositorys_own_keys(monkeypatch, tmp_path) -> None:
    """`grading_keys/` is committed evidence; a model-written key may not appear in it."""
    stage(monkeypatch, tmp_path, pinned=True)
    drafting_model(monkeypatch)
    record_publish(monkeypatch)
    run_cli(monkeypatch, URL, tmp_path / "artifacts")
    assert not key_path(APP_NAME, GROUND_TRUTH_SUFFIX).exists()
    assert not key_path(APP_NAME, GROUND_TRUTH_SUFFIX, REAL_DRAFTS_DIR).exists()
    assert discover_graded_apps() == SHIPPED_APPS


def test_a_second_run_leaves_the_first_draft_exactly_as_it_was(monkeypatch, tmp_path) -> None:
    """A redraft would move every figure already scored against the first, so it is not made."""
    stage(monkeypatch, tmp_path, pinned=True)
    drafting_model(monkeypatch)
    record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts) == 0
    first = drafted_key(tmp_path).read_bytes()
    assert run_cli(monkeypatch, URL, artifacts) == 0
    assert drafted_key(tmp_path).read_bytes() == first


# --- a local path is not a fetched one ----------------------------------------

def test_a_local_path_drafts_nothing_at_all(monkeypatch, tmp_path) -> None:
    """Only a fetched tree is drafted for: a local one may be at no commit at all."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    repo = write_mixed_app(tmp_path)
    fetch_repo.write_manifest(
        tmp_path, fetch_repo.manifest(APP_NAME, URL, COMMIT, COMMIT_DATE))
    monkeypatch.setattr(key_drafting, "DRAFTED_KEYS_DIR", drafts_dir(tmp_path))
    seen = drafting_model(monkeypatch)
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts") == 0
    assert not drafts_dir(tmp_path).exists()
    assert [prompt for prompt in seen if DRAFTING_MARKER in prompt] == []
