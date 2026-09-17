"""An upload changes no finding, asserted the way the scorer boundary is asserted.

`web/uploads.py` says it plainly -- nothing under `src/` reads that directory,
no check joins on an upload, `findings.json` is untouched -- and until now
nothing held it. This is the enforcement, and it is the same shape as
`tests/test_scorer_boundary.py`: a negative cannot be shown by running the tool,
because a code path that was not taken looks exactly like one that does not
exist. So the source is read instead.

**Why it would matter.** Attached files are the one object on this server that
`src/` did not produce: attacker-chosen bytes arriving at an endpoint with no
authentication. A check that read one would be a check whose evidence came from
the person being audited, and every finding downstream of it would inherit that.
The page says "they change no finding" in so many words; this is what makes the
sentence true rather than current.

The second half is where the bytes live **when nobody says otherwise**.
`DEFAULT_UPLOAD_DIR` is derived from `history_store.STORE_DIR`, so wherever the
history goes the attachments follow -- and that directory is `runs/`, which is
gitignored, so an upload is *structurally* uncommittable, the same protection
`grading_keys/drafts/` has.

Be exact about which half of that is shown here. The derivation is, against the
real constants; that `STORE_DIR` is itself anchored to this repository rather
than to a working directory is `test_history_store_location.py`'s subject, and
it has to read the default in a subprocess because this folder rebinds it before
the first test runs. The `.gitignore` line is read from the file. That the
default really is only a default -- `register` takes the directory, and taking
it is the only way to move the bytes -- is `test_uploads_destination.py`.

Nothing here skips, and that is deliberate: the `src/` boundary is the claim
worth holding on a checkout with no web extra installed, because it is a claim
about the tool rather than about the wrapper. The one test that has to read
`web/uploads.py`'s own constant asks for the module there and then, since
importing it needs fastapi.
"""

from pathlib import Path

import pytest

import history_store

from ast_scan import modules_importing, modules_using_value, source_files
from conftest import REPO_ROOT, SRC_DIR

from . import WEB_DIR

# The directory's name as a module would have to write it to reach the files.
# Not `"upload"` singular: `src/detectors/detector_names.py` maps
# `st.file_uploader` to "user-uploaded file", which is a Streamlit surface and
# has nothing to do with this endpoint. A guard that matched it would be a guard
# nobody could keep green.
UPLOADS_DIRECTORY = "uploads"

# The module that owns them, which `src/` may not import either -- naming the
# directory is one way to reach the bytes and importing the module is the other.
UPLOADS_MODULE = "uploads"

# The exact set, and it is empty. Every tree under `src/` is covered, not only
# the ones the scorer is barred from: an upload is input from the audited side,
# so there is no component here with a reason to read one.
SRC_MODULES_TOUCHING_UPLOADS: frozenset[str] = frozenset()

# A planted module, to prove the matcher fires on a real violation.
PLANTED_FILE = "planted.py"
PLANTED_READER = 'EVIDENCE = open("runs/uploads/latest").read()\n'

# A floor under the scan, since an empty file list satisfies an empty set.
LEAST_SRC_MODULES = 40

# The wrapper's module that must name the directory, so the search is shown to
# be able to find the token at all. A floor rather than an exact set: `web/`
# spells `uploads` in three places -- the directory, the column and the record
# field -- and which of them do is not this test's business.
THE_MODULE_THAT_OWNS_THEM = "uploads.py"

# Where the bytes go, and the line that keeps them out of a commit.
GITIGNORE = REPO_ROOT / ".gitignore"
IGNORED_DIRECTORY = "runs/"


def plant(tmp_path: Path, source: str) -> Path:
    """Write a throwaway tree holding one offending module, and return its root."""
    root = tmp_path / "planted_src"
    root.mkdir()
    (root / PLANTED_FILE).write_text(source, encoding="utf-8")
    return root


# --- the scan is looking at something ------------------------------------------

def test_the_tool_was_actually_scanned() -> None:
    """Guard: the two empty sets below say nothing if the file list came back empty."""
    assert len(source_files(SRC_DIR)) >= LEAST_SRC_MODULES


# --- nothing under src/ can reach an attachment ---------------------------------

def test_no_module_of_the_tool_names_the_uploads_directory() -> None:
    """The claim the page makes to a reader: the audit does not know they exist."""
    assert modules_using_value(UPLOADS_DIRECTORY, SRC_DIR) == set(
        SRC_MODULES_TOUCHING_UPLOADS)


def test_no_module_of_the_tool_imports_the_module_that_holds_them() -> None:
    """The other route to the same bytes, closed the same way."""
    assert modules_importing(UPLOADS_MODULE, SRC_DIR) == set(
        SRC_MODULES_TOUCHING_UPLOADS)


def test_that_search_would_notice_a_module_that_read_them(tmp_path) -> None:
    """Mutation check: plant one that opens the directory and see the search name it."""
    root = plant(tmp_path, PLANTED_READER)
    assert modules_using_value(UPLOADS_DIRECTORY, root) == {PLANTED_FILE}


def test_the_wrapper_is_where_the_directory_is_named() -> None:
    """Non-vacuity in the other direction: the token exists and the search can find it."""
    assert THE_MODULE_THAT_OWNS_THEM in modules_using_value(UPLOADS_DIRECTORY, WEB_DIR)


# --- and they cannot be committed -------------------------------------------------

def test_the_default_upload_directory_is_derived_from_where_the_history_lives() -> None:
    """Wherever the run history goes, the attachments follow by default -- one anchor, not two.

    Which directory that is, and that it is anchored to this repository rather
    than to a working directory, is `test_history_store_location.py`: this
    folder rebinds the constant before the first test runs, so the value read
    here is the redirection and the *relationship* is what it can show.

    The module is asked for here rather than at the top of the file because
    importing it needs fastapi, and the `src/` boundary above is worth holding
    without it.
    """
    uploads = pytest.importorskip(
        "uploads", reason="the web extra is not installed, so there are no upload routes")
    assert uploads.DEFAULT_UPLOAD_DIR.parent == history_store.STORE_DIR
    assert uploads.DEFAULT_UPLOAD_DIR.name == UPLOADS_DIRECTORY


def test_that_directory_is_one_git_is_told_to_ignore() -> None:
    """Structurally uncommittable, which is the protection `grading_keys/drafts/` has."""
    ignored = GITIGNORE.read_text(encoding="utf-8").splitlines()
    assert IGNORED_DIRECTORY in [line.strip() for line in ignored]
