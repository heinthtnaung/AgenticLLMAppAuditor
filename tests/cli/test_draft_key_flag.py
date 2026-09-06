"""`--draft-key` is what runs the drafting stage, and a pin is what decides which trees can.

Until 2026-09-06 a grading key was drafted on **every** URL audit. That put a
local-model call on the default path of a run that is otherwise fast, static and
offline, and it is the one stage where the model authors ground truth rather
than advice. It is now opt-in, and the two things that made it worth a flag are
asserted here rather than described: a default run sends no drafting prompt at
all, and leaves no key anywhere.

The flag does not decide *which* trees can be drafted for -- the pin does. A key
pins line numbers to a commit, so a pinned tree is drafted for whether it was
fetched or pointed at, and an unpinned one is refused either way. The URL half
of that refusal is in `test_pipeline_draft_key.py`; the local half is here,
because a directory argument never goes near the fetcher.

Nothing here clones, launches a process or reaches a model: see
`draft_key_helpers.py` for what is replaced and where.
"""

from cli_helpers import run_cli
from conftest import read_json
from draft_key_helpers import (
    DRAFT_KEY, drafted_key, drafting_model, drafting_prompts, drafts_dir,
    fetched_tree, local_tree)
from fetch_helpers import COMMIT, URL
from keys.grading_keys import GROUND_TRUTH_SUFFIX, discover_graded_apps, key_path
from keys.key_drafting import DRAFTED_KEYS_DIR as REAL_DRAFTS_DIR
from mixed_app_fixtures import APP_NAME
from pipeline_helpers import record_publish
from shipped_key_fixtures import SHIPPED_APPS


# --- without the flag, the stage is not reached -------------------------------

def test_a_default_url_run_never_asks_the_model_to_draft(monkeypatch, tmp_path) -> None:
    """The speed the flag protects: no drafting prompt is sent on a default run.

    Everything a draft needs is staged -- a pinned tree and a model that would
    answer with an entry -- so the absent flag is the only thing stopping it.
    The recorded prompts are asserted non-empty because the run does reach the
    model for advice: the recorder was live, and recorded no drafting question.
    """
    fetched_tree(monkeypatch, tmp_path, pinned=True)
    seen = drafting_model(monkeypatch)
    record_publish(monkeypatch)
    assert run_cli(monkeypatch, URL, tmp_path / "artifacts") == 0
    assert seen != [], "the run asked the model for advice, so nothing muted the recorder"
    assert drafting_prompts(seen) == []


def test_a_default_url_run_leaves_no_key_anywhere(monkeypatch, tmp_path) -> None:
    """The other half: no key is written, in the run's folder or the project's."""
    fetched_tree(monkeypatch, tmp_path, pinned=True)
    drafting_model(monkeypatch)
    published = record_publish(monkeypatch)
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, URL, artifacts) == 0
    assert published == [(artifacts / APP_NAME, False)], "the run reached its last stage"
    assert not drafts_dir(tmp_path).exists()
    assert not key_path(APP_NAME, GROUND_TRUTH_SUFFIX, REAL_DRAFTS_DIR).exists()
    assert discover_graded_apps() == SHIPPED_APPS


# --- with the flag, the pin decides and the fetcher does not -------------------

def test_a_pinned_local_tree_is_drafted_without_ever_being_fetched(monkeypatch,
                                                                  tmp_path) -> None:
    """Drafting follows the pin, not the URL: a hand-cloned tree carries one too.

    The commit asserted is the one in the manifest beside the local tree, so
    this cannot pass on a key drafted against some other pin.
    """
    repo = local_tree(monkeypatch, tmp_path, pinned=True)
    drafting_model(monkeypatch)
    published = record_publish(monkeypatch)
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts", flags=DRAFT_KEY) == 0
    assert published == [], "a local path publishes nothing, drafted key or not"
    assert read_json(drafted_key(tmp_path))["upstream_commit"] == COMMIT


def test_an_unpinned_local_tree_is_refused_with_a_reason_and_still_exits_zero(
        monkeypatch, tmp_path, capsys) -> None:
    """Asking for a key the tree cannot support is answered, not raised."""
    repo = local_tree(monkeypatch, tmp_path, pinned=False)
    drafting_model(monkeypatch)
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts", flags=DRAFT_KEY) == 0
    assert "no upstream commit could be read" in capsys.readouterr().err
    assert not drafted_key(tmp_path).exists()
