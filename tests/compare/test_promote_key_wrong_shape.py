"""A draft or a manifest that parses fine and is not an object, through promotion.

`promote_key._read` guarded the open and the parse. Nothing guarded what came
back, so a draft holding `[]` reached `key_document.get("verified")` as an
`AttributeError` -- and `EXPECTED_FAILURES` lists `FileNotFoundError`,
`FileExistsError` and `ValueError`, not that. One `except` clause from a fault
this same file already refuses by name, the command answered a hand-edited file
with a traceback out of the auditor's own source.

**The class is the assertion with teeth**, spelled `type(raised) is ValueError`.
Checking only that the message names the file would not tell a refusal from an
escape in the neighbouring fault: `PermissionError`'s own message is
`[Errno 13] Permission denied: <path>`.

**And promotion moves files.** Both documents are read before either
`shutil.move`, so a wrong-shaped manifest -- the second file, read after a
perfectly good key -- has to leave the keys folder empty. That ordering is
asserted rather than read off the source, with an off position below so it
cannot hold vacuously.

`KEYS_DIR` is redirected under `tmp_path` before any promotion runs: the real
`grading_keys/` is this project's committed evidence, and
`test_promote_key_guards.py` holds it byte for byte.
"""

import json
from pathlib import Path

import promote_key
import pytest
from drafted_key_fixtures import (
    APP, DRAFTS_NAME, corrected_draft, fit_key, redirect_keys_dir)
from guarded_read import WRONG_SHAPE, refusal_from
from keys import key_drafting
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path

# Readable json that is not an object, with what the refusal must call each one.
# Three shapes because the fault is "not an object" and not "is a list": a hand
# edit that deleted everything but the entries leaves the first, and a truncated
# file can leave either of the others.
WRONG_SHAPES = (("[]", "list"), (f'"{APP}"', "str"), ("7", "int"))
SHAPE_IDS = [text for text, _name in WRONG_SHAPES]
WRONG_SHAPE_TEXTS = [text for text, _name in WRONG_SHAPES]

# The two hand-edited files of a draft, by the name a reader would call each.
# Both go through the same guarded read, so either can be the one at fault.
DRAFT_FILES = {"the key": GROUND_TRUTH_SUFFIX, "the manifest": MANIFEST_SUFFIX}

# The exit code `main` returns on a refusal, and the prefix it writes first. A
# traceback reaches the terminal without that prefix.
FAILED = 1
PRINTED_REASON = "error: "


@pytest.fixture
def keys_dir(monkeypatch, tmp_path) -> Path:
    """An empty keys folder under `tmp_path`, with `KEYS_DIR` pointed at it."""
    return redirect_keys_dir(monkeypatch, tmp_path)


@pytest.fixture
def drafts_dir(keys_dir: Path) -> Path:
    """The drafts folder one level down, where a draft waits to be promoted."""
    return keys_dir / DRAFTS_NAME


def holding(tmp_path: Path, text: str) -> Path:
    """One key file holding whatever a hand edit left in it."""
    path = tmp_path / f"{APP}{GROUND_TRUTH_SUFFIX}"
    path.write_text(text, encoding="utf-8")
    return path


def refused_read(path: Path) -> Exception:
    """Whatever `_object` raised for this file, as an object, so its class is assertable."""
    return refusal_from(lambda: promote_key._object(path), path.name)


def misshapen(drafts_dir: Path, suffix: str, text: str) -> Path:
    """Stage a correct draft and leave one of its two files holding `text`."""
    corrected_draft(drafts_dir)
    path = key_path(APP, suffix, drafts_dir)
    path.write_text(text, encoding="utf-8")
    return path


def refused_promotion(drafts_dir: Path) -> Exception:
    """Whatever `promote` raised, as an object, so its class is what gets asserted."""
    return refusal_from(lambda: promote_key.promote(APP, drafts_dir), "promote")


def promoted_files(keys_dir: Path) -> list[str]:
    """Every file promotion moved up, so "nothing moved" is a list and not a hunch."""
    return sorted(path.name for path in keys_dir.iterdir() if path.is_file())


def both_draft_names() -> list[str]:
    """The pair a refused promotion must leave exactly where a person can fix it."""
    return sorted(f"{APP}{suffix}" for suffix in DRAFT_FILES.values())


# --- one document, read on its own ---------------------------------------------

def test_a_json_object_is_returned_unchanged(tmp_path) -> None:
    """The off position: the guard passes the document every good draft holds."""
    assert promote_key._object(holding(tmp_path, json.dumps(fit_key()))) == fit_key()


@pytest.mark.parametrize("text,_shape", WRONG_SHAPES, ids=SHAPE_IDS)
def test_a_document_that_is_not_an_object_is_refused_as_a_value_error(
        tmp_path, text: str, _shape: str) -> None:
    """The escape itself: `.get` on a list is an `AttributeError`, which is not a `ValueError`."""
    assert type(refused_read(holding(tmp_path, text))) is ValueError


@pytest.mark.parametrize("text,shape", WRONG_SHAPES, ids=SHAPE_IDS)
def test_the_refusal_names_the_file_and_the_shape_it_found(tmp_path, text: str,
                                                           shape: str) -> None:
    """Both halves of the advice: which file to open, and what it turned out to hold."""
    path = holding(tmp_path, text)
    said = str(refused_read(path))
    assert str(path) in said
    assert shape in said and WRONG_SHAPE in said


def test_the_refusal_is_one_the_command_is_written_to_catch(tmp_path) -> None:
    """The class matters because of this list, so the list is asserted and not assumed."""
    assert isinstance(refused_read(holding(tmp_path, "[]")),
                      promote_key.EXPECTED_FAILURES)


# --- and through the promotion that reads both ---------------------------------

@pytest.mark.parametrize("text", WRONG_SHAPE_TEXTS, ids=SHAPE_IDS)
@pytest.mark.parametrize("suffix", list(DRAFT_FILES.values()), ids=list(DRAFT_FILES))
def test_either_file_of_the_wrong_shape_stops_the_promotion(drafts_dir, suffix: str,
                                                            text: str) -> None:
    """Six cases, because the manifest is read too and is hand-edited for the same reason."""
    misshapen(drafts_dir, suffix, text)
    assert type(refused_promotion(drafts_dir)) is ValueError


@pytest.mark.parametrize("suffix", list(DRAFT_FILES.values()), ids=list(DRAFT_FILES))
def test_the_refusal_names_the_misshapen_file_and_not_the_other(drafts_dir,
                                                                suffix: str) -> None:
    """Two files are read, and the other one is sitting there perfectly well formed."""
    path = misshapen(drafts_dir, suffix, "[]")
    other = [name for name in DRAFT_FILES.values() if name != suffix][0]
    said = str(refused_promotion(drafts_dir))
    assert str(path) in said
    assert str(key_path(APP, other, drafts_dir)) not in said


# --- nothing is half-promoted --------------------------------------------------

@pytest.mark.parametrize("suffix", list(DRAFT_FILES.values()), ids=list(DRAFT_FILES))
def test_nothing_is_moved_into_the_keys_folder(keys_dir, drafts_dir,
                                               suffix: str) -> None:
    """A half-promotion would put an unread key where published figures are scored.

    The manifest is the ordering case -- the key is read first and read fine --
    and it is the one a promotion that moved as it went would get wrong.
    """
    misshapen(drafts_dir, suffix, "[]")
    refused_promotion(drafts_dir)
    assert promoted_files(keys_dir) == []


@pytest.mark.parametrize("suffix", list(DRAFT_FILES.values()), ids=list(DRAFT_FILES))
def test_both_files_are_left_in_the_drafts_folder(drafts_dir, suffix: str) -> None:
    """The other half of "nothing moved": they stay where a person can correct them."""
    misshapen(drafts_dir, suffix, "[]")
    refused_promotion(drafts_dir)
    assert sorted(path.name for path in drafts_dir.iterdir()) == both_draft_names()


def test_a_draft_of_the_right_shape_still_promotes(keys_dir, drafts_dir) -> None:
    """The off position: this pair is fit, so "nothing moved" means the shape stopped it."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert promoted_files(keys_dir) == both_draft_names()


# --- and what the command prints -----------------------------------------------

@pytest.mark.parametrize("suffix", list(DRAFT_FILES.values()), ids=list(DRAFT_FILES))
def test_the_command_prints_one_line_and_exits_one(keys_dir, monkeypatch, capsys,
                                                   suffix: str) -> None:
    """Where "a message, not a traceback" is actually decided, for both files.

    The command takes no folder argument, so the draft is planted where it really
    looks: `key_drafting.DRAFTED_KEYS_DIR`, which `conftest`'s autouse fixture
    has already pointed at a temporary folder of its own.
    """
    path = misshapen(key_drafting.DRAFTED_KEYS_DIR, suffix, "[]")
    monkeypatch.setattr("sys.argv", ["promote_key.py", APP])
    assert promote_key.main() == FAILED
    said = capsys.readouterr().err.splitlines()
    assert len(said) == 1 and said[0].startswith(PRINTED_REASON)
    assert str(path) in said[0] and WRONG_SHAPE in said[0]
