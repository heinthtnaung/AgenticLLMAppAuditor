"""The scorer's edge: what it reads from disk, what it refuses, and what it writes.

Every test here stages its own artifacts and its own grading key under
`tmp_path` and passes that directory in, so nothing here reads or writes the
real `grading_keys/`. A key is hand-placed input now that the pinned corpus is
gone, so its shape is checked at this edge rather than trusted; the shape
check's own cases are in `test_key_check.py`, and one test here proves it is
wired into the read rather than merely available beside it.

The refusals are the point. A missing findings.json scored as "nothing found"
would read as a perfect-precision run over an app that was never audited, so
each absence is asserted to raise and to name the artifact that is absent.
"""

import json
from pathlib import Path

import pytest

from evaluation.harness import (
    EVALUATION_NAME,
    FINDINGS_NAME,
    SURFACES_NAME,
    evaluation_to_json,
    load_app,
    score_apps,
    write_evaluation,
)
from evaluation_fixtures import APP, answered_key, grading_key
from grading_keys import GROUND_TRUTH_SUFFIX

# A second app, named so that sorting it after `APP` is not the input order.
OTHER_APP = "aardvark-app"

# The two directories a run uses: the grading keys, and everything the tool wrote.
KEY_DIR_NAME = "grading_keys"
ARTIFACTS_DIR_NAME = "artifacts"

NOT_JSON = "{not json at all"


def write_json(path: Path, document: dict) -> None:
    """Write one artifact where the harness will go looking for it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def keys_dir(tmp_path: Path) -> Path:
    """The temporary directory the staged grading keys are written into."""
    return tmp_path / KEY_DIR_NAME


def staged_key_path(tmp_path: Path, app: str) -> Path:
    """Where the harness will look for one app's grading key."""
    return keys_dir(tmp_path) / f"{app}{GROUND_TRUTH_SUFFIX}"


def stage(tmp_path: Path, *apps: str) -> Path:
    """Write a complete, scorable set of artifacts for each app; return the artifacts dir."""
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    for app in apps or (APP,):
        key, findings, surfaces = answered_key()
        write_json(staged_key_path(tmp_path, app), key)
        write_json(artifacts_dir / app / FINDINGS_NAME, findings)
        write_json(artifacts_dir / app / SURFACES_NAME, surfaces)
    return artifacts_dir


def load(tmp_path: Path, app: str = APP) -> tuple[dict, dict, dict]:
    """Load one staged app through the harness, with the staged keys directory."""
    return load_app(app, tmp_path / ARTIFACTS_DIR_NAME, keys_dir=keys_dir(tmp_path))


def score(tmp_path: Path, apps: list[str], artifacts_dir: Path) -> dict:
    """Score the named staged apps, reading their keys from the staged keys directory."""
    return score_apps(apps, artifacts_dir, keys_dir=keys_dir(tmp_path))


def test_load_app_returns_the_key_then_the_findings_then_the_surfaces(tmp_path) -> None:
    """The documented order, because `score_app` takes all three positionally."""
    stage(tmp_path)
    key, findings, surfaces = load(tmp_path)
    assert key["app"] == APP and key["source"] == "manual_review"
    assert findings["finding_count"] == 1
    assert surfaces["skipped_files"] == []


def test_a_missing_grading_key_names_the_grading_key(tmp_path) -> None:
    """Without a key there is nothing to score against, so it must not read as zero."""
    stage(tmp_path)
    staged_key_path(tmp_path, APP).unlink()
    with pytest.raises(FileNotFoundError) as raised:
        load(tmp_path)
    assert f"a grading key for {APP}" in str(raised.value)


def test_a_missing_findings_document_names_the_findings(tmp_path) -> None:
    """An app that was never audited must fail, not score perfect precision on nothing."""
    artifacts_dir = stage(tmp_path)
    (artifacts_dir / APP / FINDINGS_NAME).unlink()
    with pytest.raises(FileNotFoundError) as raised:
        load(tmp_path)
    assert f"{APP}'s findings" in str(raised.value)


def test_a_missing_surfaces_document_names_the_surfaces(tmp_path) -> None:
    """Misses are attributed against the scan, so a scoring run without one is refused."""
    artifacts_dir = stage(tmp_path)
    (artifacts_dir / APP / SURFACES_NAME).unlink()
    with pytest.raises(FileNotFoundError) as raised:
        load(tmp_path)
    assert f"{APP}'s surfaces" in str(raised.value)


def test_the_missing_artifact_message_names_only_the_one_that_is_missing(tmp_path) -> None:
    """Naming both would send the reader looking for a file that is there."""
    artifacts_dir = stage(tmp_path)
    (artifacts_dir / APP / FINDINGS_NAME).unlink()
    with pytest.raises(FileNotFoundError) as raised:
        load(tmp_path)
    assert SURFACES_NAME not in str(raised.value)


def test_the_missing_artifact_message_says_what_to_do_about_it(tmp_path) -> None:
    """The error is read by someone who has not run the auditor yet; it tells them so."""
    artifacts_dir = stage(tmp_path)
    (artifacts_dir / APP / FINDINGS_NAME).unlink()
    with pytest.raises(FileNotFoundError) as raised:
        load(tmp_path)
    assert "Run agentic_auditor over this app first." in str(raised.value)


def test_malformed_json_is_refused_with_the_path_that_holds_it(tmp_path) -> None:
    """A half-written artifact names its own path, so nobody greps the whole tree for it."""
    artifacts_dir = stage(tmp_path)
    broken = artifacts_dir / APP / FINDINGS_NAME
    broken.write_text(NOT_JSON, encoding="utf-8")
    with pytest.raises(ValueError) as raised:
        load(tmp_path)
    assert str(broken) in str(raised.value)


def test_malformed_json_is_reraised_rather_than_left_as_a_decode_error(tmp_path) -> None:
    """A bare `JSONDecodeError` names a column in a file the caller cannot see."""
    artifacts_dir = stage(tmp_path)
    (artifacts_dir / APP / SURFACES_NAME).write_text(NOT_JSON, encoding="utf-8")
    with pytest.raises(ValueError) as raised:
        load(tmp_path)
    assert not isinstance(raised.value, json.JSONDecodeError)


def test_scoring_one_app_returns_its_scorecard(tmp_path) -> None:
    """The happy path: the staged app is loaded, scored and counted."""
    document = score(tmp_path, [APP], stage(tmp_path))
    assert document["app_count"] == 1
    assert document["apps"][0]["app"] == APP
    assert document["apps"][0]["true_positives"] == 1


def test_scoring_no_apps_at_all_is_refused(tmp_path) -> None:
    """An empty evaluation would read as "scored, nothing to report"."""
    with pytest.raises(ValueError, match="no grading key found"):
        score(tmp_path, [], stage(tmp_path))


def test_the_refusal_to_score_nothing_says_there_was_nothing_to_score(tmp_path) -> None:
    """Zero keys is normal now, so the message must read as a fact and not a fault."""
    with pytest.raises(ValueError) as raised:
        score(tmp_path, [], stage(tmp_path))
    assert "there is nothing to score" in str(raised.value)


def test_the_apps_are_scored_in_sorted_order_whatever_order_they_arrive_in(tmp_path) -> None:
    """Sorted, so the artifact does not change when the caller's app list is reshuffled."""
    artifacts_dir = stage(tmp_path, APP, OTHER_APP)
    document = score(tmp_path, [APP, OTHER_APP], artifacts_dir)
    assert [app["app"] for app in document["apps"]] == [OTHER_APP, APP]


def test_two_runs_over_the_same_artifacts_serialise_to_the_same_bytes(tmp_path) -> None:
    """Byte-identical determinism: a diff in evaluation.json means the score changed."""
    artifacts_dir = stage(tmp_path, APP, OTHER_APP)
    first = evaluation_to_json(score(tmp_path, [APP, OTHER_APP], artifacts_dir))
    second = evaluation_to_json(score(tmp_path, [OTHER_APP, APP], artifacts_dir))
    assert first == second


def test_the_serialised_evaluation_sorts_its_keys() -> None:
    """`sort_keys=True`, so key order can never carry a difference of its own."""
    assert list(json.loads(evaluation_to_json({"b": 1, "a": 2}))) == ["a", "b"]


def test_the_serialised_evaluation_ends_with_a_newline() -> None:
    """A trailing newline, so the file is a well-formed text file and diffs cleanly."""
    assert evaluation_to_json({"a": 1}).endswith("}\n")


def test_write_evaluation_returns_the_path_it_wrote(tmp_path) -> None:
    """One file for the whole run, named `evaluation.json` beside the per-app artifacts."""
    artifacts_dir = stage(tmp_path)
    document = score(tmp_path, [APP], artifacts_dir)
    written = write_evaluation(document, artifacts_dir)
    assert written == artifacts_dir / EVALUATION_NAME
    assert written.is_file()


def test_write_evaluation_creates_a_directory_that_is_not_there_yet(tmp_path) -> None:
    """Scoring a fresh checkout must not fail on a missing artifacts directory."""
    document = score(tmp_path, [APP], stage(tmp_path))
    fresh = tmp_path / "brand" / "new"
    assert write_evaluation(document, fresh) == fresh / EVALUATION_NAME


def test_the_written_file_round_trips_to_the_same_document(tmp_path) -> None:
    """What is read back is what was scored, not a lossy rendering of it."""
    artifacts_dir = stage(tmp_path)
    document = score(tmp_path, [APP], artifacts_dir)
    written = write_evaluation(document, artifacts_dir)
    assert json.loads(written.read_text(encoding="utf-8")) == document


def test_the_written_file_holds_exactly_what_the_serialiser_produced(tmp_path) -> None:
    """The bytes on disk are the serialiser's, so the determinism test covers the file too."""
    artifacts_dir = stage(tmp_path)
    document = score(tmp_path, [APP], artifacts_dir)
    written = write_evaluation(document, artifacts_dir)
    assert written.read_text(encoding="utf-8") == evaluation_to_json(document)


def test_a_malformed_key_on_disk_is_refused_by_load_app(tmp_path) -> None:
    """The shape check is wired into the read, not merely available beside it.

    Its own cases are in test_key_check.py; what this asserts is that the read
    goes through it, so a malformed key never reaches `scorer.py`.
    """
    stage(tmp_path)
    key = grading_key([])
    del key["verified_by"]
    write_json(staged_key_path(tmp_path, APP), key)
    with pytest.raises(ValueError, match="verified_by"):
        load(tmp_path)
