"""What the fetcher refuses, and what it leaves on disk when a clone goes wrong.

No test here clones anything: each one replaces the fetcher's single process
launch, so the network is never reached and a refusal is proved by planting the
attempt rather than by describing it.

The theme is that a half-fetched tree is worse than no tree. An audit reading
one would report on a repository it only partly has, and its report would look
exactly like a complete run -- so every failure path below is checked for what
it removed, not only for what it raised.
"""

from pathlib import Path

import pytest

import fetch_repo
from fetch_helpers import (
    CLONE_FAILED,
    NAME,
    PARTIAL_FILE,
    SOURCE_FILE,
    URL,
    download_root,
    install_fake_git,
    install_failing_git,
    install_hanging_git,
    install_recording_git,
)
from fetch_repo import HISTORY_DIR

# Small enough that the stand-in's few-line tree is over it.
TINY_CAP = 10

# Planted at the fetcher rather than at repo_url, so the refusal is shown to
# happen before anything is launched, not merely to exist.
REFUSED_URL = "file:///etc/passwd"


def manifest_files(root: Path) -> list[str]:
    """Every pin written under a download root, so a failed fetch can be shown to write none."""
    return sorted(path.name for path in root.glob("*.json"))


# --- A fetch that works, so the refusals below mean something ---------------

def test_a_fetch_returns_the_tree_it_wrote(tmp_path, monkeypatch) -> None:
    """The happy path lands the cloned files under the download root."""
    install_fake_git(monkeypatch)
    destination = fetch_repo.fetch(URL, download_root(tmp_path))
    assert destination == download_root(tmp_path) / NAME
    assert (destination / SOURCE_FILE).is_file()


def test_the_history_directory_is_removed_from_the_fetched_tree(tmp_path, monkeypatch) -> None:
    """A tree with a .git in it reads as a repository the tool might write to."""
    install_fake_git(monkeypatch)
    destination = fetch_repo.fetch(URL, download_root(tmp_path))
    assert not (destination / HISTORY_DIR).exists()


def test_the_commit_is_read_before_the_history_is_removed(tmp_path, monkeypatch) -> None:
    """Delete first and the pin is unreadable: the order is the whole of the evidence."""
    fake = install_fake_git(monkeypatch)
    fetch_repo.fetch(URL, download_root(tmp_path))
    assert fake.history_present_at_pin == [True]


# --- Nothing is ever written over ------------------------------------------

def test_a_destination_that_already_exists_is_refused(tmp_path, monkeypatch) -> None:
    """A fetch landing on an existing tree could replace a pinned fixture."""
    install_fake_git(monkeypatch)
    root = download_root(tmp_path)
    (root / NAME).mkdir(parents=True)
    with pytest.raises(FileExistsError, match="already exists"):
        fetch_repo.fetch(URL, root)


def test_an_existing_destination_is_refused_before_git_is_run(tmp_path, monkeypatch) -> None:
    """The refusal has to come first, or the network is reached to no purpose."""
    fake = install_fake_git(monkeypatch)
    root = download_root(tmp_path)
    (root / NAME).mkdir(parents=True)
    with pytest.raises(FileExistsError):
        fetch_repo.fetch(URL, root)
    assert fake.calls == []


def test_a_manifest_left_behind_is_refused_even_though_the_tree_is_gone(
        tmp_path, monkeypatch) -> None:
    """The pin is half the artifact: a stale one must not be silently rewritten."""
    install_fake_git(monkeypatch)
    root = download_root(tmp_path)
    root.mkdir(parents=True)
    pin = fetch_repo.manifest_path(root, NAME)
    pin.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match=pin.name):
        fetch_repo.fetch(URL, root)


def test_a_refused_url_never_reaches_git(tmp_path, monkeypatch) -> None:
    """`file://` is turned away by the URL check, so no process is started at all."""
    fake = install_fake_git(monkeypatch)
    with pytest.raises(ValueError, match="only https:// URLs are fetched"):
        fetch_repo.fetch(REFUSED_URL, download_root(tmp_path))
    assert fake.calls == []


# --- A clone that fails leaves nothing behind -------------------------------

def test_a_clone_that_exits_non_zero_leaves_no_partial_tree(tmp_path, monkeypatch) -> None:
    """Planted: git writes half a tree and fails. The half must not survive."""
    install_failing_git(monkeypatch)
    root = download_root(tmp_path)
    with pytest.raises(RuntimeError):
        fetch_repo.fetch(URL, root)
    assert not (root / NAME).exists()
    assert not (root / NAME / PARTIAL_FILE).exists()


def test_a_clone_that_exits_non_zero_says_what_git_said(tmp_path, monkeypatch) -> None:
    """git's own stderr is the only thing that explains why the fetch failed."""
    install_failing_git(monkeypatch)
    with pytest.raises(RuntimeError, match=CLONE_FAILED):
        fetch_repo.fetch(URL, download_root(tmp_path))


def test_a_clone_that_exits_non_zero_writes_no_pin(tmp_path, monkeypatch) -> None:
    """A pin without a tree is the state the fetcher refuses to start from."""
    install_failing_git(monkeypatch)
    root = download_root(tmp_path)
    with pytest.raises(RuntimeError):
        fetch_repo.fetch(URL, root)
    assert manifest_files(root) == []


def test_a_clone_that_times_out_leaves_no_partial_tree(tmp_path, monkeypatch) -> None:
    """Planted: git stalls past the timeout. A stalled fetch is a failure, not a partial one."""
    install_hanging_git(monkeypatch)
    root = download_root(tmp_path)
    with pytest.raises(RuntimeError):
        fetch_repo.fetch(URL, root)
    assert not (root / NAME).exists()


def test_a_clone_that_times_out_says_so_and_names_the_limit(tmp_path, monkeypatch) -> None:
    """"git failed" would send a reader looking for a repository problem there is not."""
    install_hanging_git(monkeypatch)
    with pytest.raises(RuntimeError, match=f"timed out after {fetch_repo.TIMEOUT_SECONDS}s"):
        fetch_repo.fetch(URL, download_root(tmp_path))


# --- A tree too large to audit ----------------------------------------------

def test_a_tree_over_the_size_cap_is_removed_rather_than_audited(
        tmp_path, monkeypatch) -> None:
    """The cap bounds what is scanned, and a tree over it is deleted, not kept."""
    install_fake_git(monkeypatch)
    monkeypatch.setattr(fetch_repo, "MAX_TREE_BYTES", TINY_CAP)
    root = download_root(tmp_path)
    with pytest.raises(ValueError, match=f"over the {TINY_CAP} byte cap"):
        fetch_repo.fetch(URL, root)
    assert not (root / NAME).exists()
    assert manifest_files(root) == []


def test_the_composed_git_command_pins_the_transport_and_stays_shallow(
        monkeypatch, tmp_path) -> None:
    """The flags are the safety properties, so assert the argv rather than trust it.

    `protocol.allow=never` with https restored is what stops a redirect
    downgrading the transport after the URL has already passed validation, and
    submodules are never recursed because a submodule URL is not the one checked.
    """
    seen = install_recording_git(monkeypatch)
    fetch_repo.fetch(URL, download_root(tmp_path))
    clone = next(argv for argv in seen if "clone" in argv)
    assert clone[0] == fetch_repo.PROGRAM_NAME
    assert clone[-1] != URL, "the URL must never be the program to run"
    assert "-c" in clone and "protocol.allow=never" in clone
    assert "protocol.https.allow=always" in clone
    assert clone[clone.index("--depth") + 1] == "1"
    assert "--no-tags" in clone
    assert not [flag for flag in clone if "recurse-submodules" in flag]


# --- Measuring a tree --------------------------------------------------------

def test_tree_bytes_totals_the_regular_files(tmp_path) -> None:
    """The measurement has to count something, or the cap can never trip."""
    (tmp_path / "one.py").write_bytes(b"x" * 40)
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "two.py").write_bytes(b"y" * 60)
    assert fetch_repo.tree_bytes(tmp_path) == 100


def test_tree_bytes_does_not_follow_a_symlink(tmp_path) -> None:
    """A fetched tree is untrusted: a link to a huge file outside must not be measured."""
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"z" * 5000)
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "real.py").write_bytes(b"x" * 40)
    (tree / "link.py").symlink_to(outside)
    assert fetch_repo.tree_bytes(tree) == 40

