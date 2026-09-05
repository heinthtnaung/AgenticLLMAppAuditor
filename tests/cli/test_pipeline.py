"""What `resolve_repo` does with a path, a fresh link, and a link fetched before.

The fetch stage is stubbed at the pipeline's seam throughout, so nothing here
clones or opens a socket, and the download root is always under tmp_path --
never the real `fetched/`.
"""

from pathlib import Path

import pytest

import json

import grading_keys
import pipeline
from fetch_helpers import COMMIT, NAME, URL
from fetch_repo import manifest_path
from grading_keys import GROUND_TRUTH_SUFFIX
from pipeline_helpers import plant_tree, point_download_root, record_fetch, write_pin

# A name a grading key owns, for the reuse-collision guard. Planted by the test:
# this project ships no keys, so the guard refuses nothing until one exists.
GRADED_APP = "a-graded-app"

# Another owner's repository with the same last path segment, so its tree would
# land on the same directory name as URL's.
OTHER_URL = "https://github.com/somebody-else/demo.git"

REFUSAL = FileExistsError("fetched/demo already exists; a fetch never writes "
                          "over anything it did not create")


def test_is_url_tells_a_link_from_a_directory() -> None:
    """Only an https:// argument runs the pipeline; a path stays the offline audit."""
    assert pipeline.is_url(URL)
    assert not pipeline.is_url("some/local/repo")


def test_a_local_path_passes_through_without_a_fetch(monkeypatch, tmp_path) -> None:
    """A directory argument is returned as a Path untouched, and fetch never runs."""
    calls = record_fetch(monkeypatch)
    resolved = pipeline.resolve_repo(str(tmp_path / "repo"))
    assert resolved == Path(str(tmp_path / "repo"))
    assert calls == []


def test_a_url_fetched_before_is_reused_without_a_fetch(monkeypatch, tmp_path) -> None:
    """Tree and pin both present for the same URL: the tree is returned, no fetch."""
    root = point_download_root(monkeypatch, tmp_path)
    tree = plant_tree(root)
    write_pin(root)
    calls = record_fetch(monkeypatch)
    assert pipeline.resolve_repo(URL) == tree
    assert calls == []


def test_reuse_names_the_pinned_commit(monkeypatch, tmp_path, capsys) -> None:
    """The note says which commit the reused tree is pinned at, so a reader can check."""
    root = point_download_root(monkeypatch, tmp_path)
    plant_tree(root)
    write_pin(root)
    record_fetch(monkeypatch)
    pipeline.resolve_repo(URL)
    printed = capsys.readouterr().out
    assert "reusing" in printed
    assert COMMIT in printed


def plant_key(monkeypatch, tmp_path: Path, app: str) -> None:
    """Write one grading key and point the collision guard's default folder at it.

    `pipeline.resolve_repo` takes no keys directory -- it is the one-command
    path, not a scoring one -- so the one constant that names the folder is
    redirected, the same seam `point_download_root` uses for the download root.
    It is patched on `grading_keys`, not on `fetch_repo`: `key_path` resolves
    the default itself, which is what keeps the folder named in one place.
    """
    keys_dir = tmp_path / "grading_keys"
    keys_dir.mkdir()
    (keys_dir / f"{app}{GROUND_TRUTH_SUFFIX}").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(grading_keys, "KEYS_DIR", keys_dir)


def test_reuse_refuses_a_name_a_grading_key_owns(monkeypatch, tmp_path) -> None:
    """A tree named after a graded app is refused on the reuse path too --
    otherwise a rerun would overwrite that app's scored artifacts."""
    point_download_root(monkeypatch, tmp_path)
    plant_key(monkeypatch, tmp_path, GRADED_APP)
    record_fetch(monkeypatch)
    with pytest.raises(ValueError, match="graded app"):
        pipeline.resolve_repo(f"https://github.com/someone/{GRADED_APP}")


def test_the_reuse_path_allows_a_name_no_key_owns(monkeypatch, tmp_path) -> None:
    """Guard on the guard: refusing every name would mean refusing every pipeline run."""
    root = point_download_root(monkeypatch, tmp_path)
    plant_key(monkeypatch, tmp_path, "a-different-app")
    tree = plant_tree(root)
    write_pin(root)
    record_fetch(monkeypatch)
    assert pipeline.resolve_repo(URL) == tree


def test_a_pin_without_an_upstream_url_is_a_message_not_a_traceback(
        monkeypatch, tmp_path) -> None:
    """A hand-edited or truncated pin hits the mismatch message, never a KeyError."""
    root = point_download_root(monkeypatch, tmp_path)
    plant_tree(root)
    manifest_path(root, NAME).write_text(json.dumps({"name": NAME}), encoding="utf-8")
    record_fetch(monkeypatch)
    with pytest.raises(ValueError, match="not"):
        pipeline.resolve_repo(URL)


def test_a_same_named_tree_from_another_url_is_refused(monkeypatch, tmp_path) -> None:
    """The pin holds a different upstream_url: refused, naming both URLs, no fetch."""
    root = point_download_root(monkeypatch, tmp_path)
    plant_tree(root)
    write_pin(root, url=OTHER_URL)
    calls = record_fetch(monkeypatch)
    with pytest.raises(ValueError) as caught:
        pipeline.resolve_repo(URL)
    message = str(caught.value)
    assert OTHER_URL in message
    assert URL in message
    assert calls == []


def test_a_tree_without_its_pin_falls_through_to_fetch(monkeypatch, tmp_path) -> None:
    """Half an artifact is not a reuse, so fetch runs and its own refusal is kept."""
    root = point_download_root(monkeypatch, tmp_path)
    plant_tree(root)
    record_fetch(monkeypatch, error=REFUSAL)
    with pytest.raises(FileExistsError, match="never writes over"):
        pipeline.resolve_repo(URL)


def test_a_pin_without_its_tree_falls_through_to_fetch(monkeypatch, tmp_path) -> None:
    """The other half alone is no reuse either: fetch runs and may refuse the pin."""
    root = point_download_root(monkeypatch, tmp_path)
    write_pin(root)
    record_fetch(monkeypatch, error=REFUSAL)
    with pytest.raises(FileExistsError, match="never writes over"):
        pipeline.resolve_repo(URL)


def test_a_fresh_url_is_fetched_exactly_once(monkeypatch, tmp_path) -> None:
    """Nothing on disk yet: one fetch, given the validated URL, answers the tree."""
    root = point_download_root(monkeypatch, tmp_path)
    destination = root / NAME
    calls = record_fetch(monkeypatch, result=destination)
    assert pipeline.resolve_repo(URL) == destination
    assert calls == [URL]


def test_a_link_with_no_host_is_refused_before_any_fetch(monkeypatch, tmp_path) -> None:
    """Validation runs first, so a malformed https link never reaches the fetcher."""
    point_download_root(monkeypatch, tmp_path)
    calls = record_fetch(monkeypatch)
    with pytest.raises(ValueError, match="names no host"):
        pipeline.resolve_repo("https://")
    assert calls == []


def test_the_vex_emitter_and_the_fetcher_agree_on_the_download_root() -> None:
    """One `fetched/` root: emit_vex resolves a pin where fetch_repo wrote it."""
    import emit_vex
    from fetch_repo import DOWNLOAD_ROOT
    assert emit_vex.FETCH_ROOT == DOWNLOAD_ROOT
