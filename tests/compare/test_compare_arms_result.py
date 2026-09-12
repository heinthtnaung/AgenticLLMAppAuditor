"""What a real `--compare-models` run hands back to whoever called it.

`compare_run.run` returned `0` once, and the first caller that was not a
command line -- `web/api.py`, which reads `produced["app"]` -- answered the
browser with a 500. Raised, on this path, only after both audits had finished
and the audited repository's source had already gone to a third party.

This is the first of the three links that hold that shut. Here the whole
comparison really runs, over an app written into `tmp_path`, and the dict it
returns is asserted key by key. `test_compare_run_result.py` asserts `main.run`
hands that same dict back unchanged, with both branches stubbed;
`tests/web/test_api_compare_models.py` asserts the wrapper turns it into a 200.
Each is cheap on its own and none of the three is sufficient alone.

Split out of `test_compare_arms.py`, which is about where the two arms' files
land. The staging both share is `compare_arms_fixtures`, which says what is
replaced and why -- nothing here reaches a model, a network or a repository
this project does not own.
"""

import compare_run
import main
from compare_arms_fixtures import compare
from mixed_app_fixtures import APP_NAME
from outputs import FINDINGS_NAME

# What the run hands back, and the reason it is a dict rather than an exit code:
# `main.run` promises one on every path, and `web/api.py` reads `produced["app"]`
# straight off it.
LOCAL_RESULT_KEYS = {"app", "artifacts", "seconds", "advisories_read"}


def test_the_run_returns_the_local_arms_result(monkeypatch, tmp_path) -> None:
    """A dict, not an exit code: every path through `main.run` answers the same shape."""
    result = compare(monkeypatch, tmp_path)
    assert set(result) == LOCAL_RESULT_KEYS
    assert result["app"] == APP_NAME


def test_the_returned_artifacts_directory_is_the_local_arms(monkeypatch, tmp_path) -> None:
    """The hosted arm's directory would send a reader to the comparison, not to the audit."""
    result = compare(monkeypatch, tmp_path)
    assert result["artifacts"] == main.DEFAULT_ARTIFACTS_DIR / APP_NAME
    assert result["artifacts"] != compare_run.CLOUD_ARTIFACTS_DIR / APP_NAME


def test_the_returned_directory_is_one_that_was_really_written(monkeypatch,
                                                               tmp_path) -> None:
    """Non-vacuity: the path named holds the local arm's findings, not just the right spelling."""
    result = compare(monkeypatch, tmp_path)
    assert (tmp_path / result["artifacts"] / FINDINGS_NAME).is_file()


def test_the_run_reports_the_local_arms_facts(monkeypatch, tmp_path) -> None:
    """The other two keys the wrapper reads: a duration, and whether advisories were read."""
    result = compare(monkeypatch, tmp_path)
    assert result["seconds"] >= 0
    assert result["advisories_read"] is False
