"""The pin's inputs: a clone's commit read from its own files, and a digest over what was indexed.

The commit is read without starting a program, so the three shapes a `.git`
directory keeps it in are each laid out under `tmp_path`, and everything else is
refused -- a pin that might be wrong is worse than none. The digest rule is
spelled in the module's docstring, and one test computes it by hand so a second
implementation could not quietly disagree. Assembling the manifest document
from these is in test_manifest_document.py.
"""

import hashlib
from pathlib import Path

import pytest

from artifacts.remediation import OWASP_CHEATSHEETS
from retrieval.manifest import (
    DIGEST_PREFIX,
    PACKED_REFS,
    SOURCES,
    commit_from_git_dir,
    content_digest,
    index_present,
    matched_files,
)

COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER_COMMIT = "fedcba9876543210fedcba9876543210fedcba98"
BRANCH = "refs/heads/main"
CHEATSHEETS = SOURCES[OWASP_CHEATSHEETS]


def git_dir(tmp_path: Path, head: str) -> Path:
    """A `.git` holding only a HEAD file with the given text."""
    path = tmp_path / ".git"
    path.mkdir()
    (path / "HEAD").write_text(head, encoding="utf-8")
    return path


def clone_with(tmp_path: Path, files: dict[str, str]) -> Path:
    """A clone root holding the given relative files."""
    for relative, text in files.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    return tmp_path


def test_a_detached_head_is_the_commit_itself(tmp_path: Path) -> None:
    """The simplest shape: HEAD holds the forty hex digits."""
    assert commit_from_git_dir(git_dir(tmp_path, f"{COMMIT}\n")) == COMMIT


def test_a_symbolic_head_is_followed_to_a_loose_ref(tmp_path: Path) -> None:
    """`ref: refs/heads/main` names a file that holds the commit."""
    path = git_dir(tmp_path, f"ref: {BRANCH}\n")
    (path / BRANCH).parent.mkdir(parents=True)
    (path / BRANCH).write_text(f"{COMMIT}\n", encoding="utf-8")
    assert commit_from_git_dir(path) == COMMIT


def test_a_ref_kept_only_in_packed_refs_is_found_there(tmp_path: Path) -> None:
    """After `gc` the loose file is gone and the ref lives in packed-refs, header and peel lines included."""
    path = git_dir(tmp_path, f"ref: {BRANCH}\n")
    (path / PACKED_REFS).write_text(
        "# pack-refs with: peeled fully-peeled sorted \n"
        f"{OTHER_COMMIT} refs/tags/v1\n^{COMMIT}\n{COMMIT} {BRANCH}\n", encoding="utf-8")
    assert commit_from_git_dir(path) == COMMIT


def test_a_head_holding_neither_commit_nor_ref_is_refused(tmp_path: Path) -> None:
    """Garbage is not a pin."""
    with pytest.raises(ValueError, match="neither a commit nor a ref"):
        commit_from_git_dir(git_dir(tmp_path, "not a commit\n"))


def test_a_ref_with_no_file_and_no_packed_refs_is_refused(tmp_path: Path) -> None:
    """A ref that resolves nowhere names the missing packed-refs in its refusal."""
    with pytest.raises(ValueError, match="no loose file"):
        commit_from_git_dir(git_dir(tmp_path, f"ref: {BRANCH}\n"))


def test_a_ref_absent_from_packed_refs_is_refused(tmp_path: Path) -> None:
    """packed-refs exists but lists another ref: still nowhere."""
    path = git_dir(tmp_path, f"ref: {BRANCH}\n")
    (path / PACKED_REFS).write_text(f"{COMMIT} refs/heads/other\n", encoding="utf-8")
    with pytest.raises(ValueError, match="is not in"):
        commit_from_git_dir(path)


def test_a_loose_ref_holding_something_other_than_a_commit_is_refused(tmp_path: Path) -> None:
    """The value found must itself be a commit id, whatever file it came from."""
    path = git_dir(tmp_path, f"ref: {BRANCH}\n")
    (path / BRANCH).parent.mkdir(parents=True)
    (path / BRANCH).write_text("ref: refs/heads/elsewhere\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a commit id"):
        commit_from_git_dir(path)


def test_matched_files_follow_the_sources_include_globs(tmp_path: Path) -> None:
    """Only what `include` selects: the repository's own README and non-Markdown files are left out."""
    clone = clone_with(tmp_path, {"cheatsheets/B.md": "b", "cheatsheets/A.md": "a",
                                  "README.md": "r", "cheatsheets/notes.txt": "n"})
    assert [p.relative_to(clone).as_posix() for p in matched_files(clone, CHEATSHEETS)] == [
        "cheatsheets/A.md", "cheatsheets/B.md"]


def test_matched_files_are_sorted(tmp_path: Path) -> None:
    """Sorted, so the digest and the passage numbering do not depend on directory order."""
    clone = clone_with(tmp_path, {f"cheatsheets/{name}.md": name for name in "zqam"})
    files = matched_files(clone, CHEATSHEETS)
    assert files == sorted(files)


def test_the_content_digest_is_deterministic(tmp_path: Path) -> None:
    """The same files digest to the same value twice."""
    clone = clone_with(tmp_path, {"cheatsheets/A.md": "a"})
    files = matched_files(clone, CHEATSHEETS)
    assert content_digest(clone, files) == content_digest(clone, files)


def test_the_content_digest_carries_the_sha256_prefix(tmp_path: Path) -> None:
    """Named algorithm, like every other digest this project writes."""
    clone = clone_with(tmp_path, {"cheatsheets/A.md": "a"})
    assert content_digest(clone, matched_files(clone, CHEATSHEETS)).startswith(DIGEST_PREFIX)


def test_renaming_a_file_changes_the_digest(tmp_path: Path) -> None:
    """The path is fed too, so a rename is caught as an edit would be."""
    one = clone_with(tmp_path / "one", {"cheatsheets/A.md": "same bytes"})
    two = clone_with(tmp_path / "two", {"cheatsheets/B.md": "same bytes"})
    assert content_digest(one, matched_files(one, CHEATSHEETS)) != content_digest(
        two, matched_files(two, CHEATSHEETS))


def test_the_content_digest_follows_the_documented_rule(tmp_path: Path) -> None:
    """Sorted POSIX paths, each as path, NUL, bytes, NUL -- computed here by hand."""
    clone = clone_with(tmp_path, {"cheatsheets/B.md": "bee", "cheatsheets/A.md": "ay"})
    expected = hashlib.sha256(b"cheatsheets/A.md\0ay\0cheatsheets/B.md\0bee\0").hexdigest()
    assert content_digest(clone, matched_files(clone, CHEATSHEETS)) == DIGEST_PREFIX + expected


def test_no_index_is_present_in_an_empty_directory(tmp_path: Path) -> None:
    """Checked before any client is opened, because opening one would create the file."""
    assert index_present(tmp_path) is False
