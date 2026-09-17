"""Promoting a draft that is a json object and whose entries are not entries.

`test_promote_key_wrong_shape.py` is the layer above this one: a file that is
readable json and *not an object at all*, which `promote_key._object` now
refuses by name. That guard stops at the root. A draft holding
`findings: "xy"` is an object, passes it, and used to reach
`key_promotion._malformed_entries`, which iterated the string and called `.get`
on a character -- `AttributeError`, which is not in `EXPECTED_FAILURES`, so the
command answered a hand-edited file with a traceback out of the auditor's own
source. That is the whole fault class in one sentence: **a guard on the document
and none on the members every caller subscripts.**

**The class is the assertion with teeth**, spelled `type(raised) is ValueError`
and checked against `EXPECTED_FAILURES` itself: the escapes here were
`AttributeError` and `TypeError`, and a test that only looked for the file's
name in a message would pass on either.

Why `refusals` reports these at all, and why the scorer's own check runs first,
is `test_key_promotion_member_shapes.py`.

`KEYS_DIR` is redirected under `tmp_path` before any promotion runs: the real
`grading_keys/` is this project's committed evidence, and nothing here writes to
it or to `grading_keys/drafts/`.
"""

from pathlib import Path

import promote_key
import pytest
from drafted_key_fixtures import (
    APP, DRAFTS_NAME, corrected_draft, fit_key, redirect_keys_dir)
from guarded_read import refusal_from
from keys import key_drafting
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX

# Every way a hand edit leaves `findings` something other than a list of
# entries. The same table the pure-function file drives, because it is the same
# document arriving by another road.
MALFORMED_FINDINGS = {"a string": "xy", "a list of numbers": [1, 2],
                      "null": None, "a list holding null": [None]}
FINDINGS_IDS = list(MALFORMED_FINDINGS)
FINDINGS_SHAPES = list(MALFORMED_FINDINGS.values())

# The shape used where the test is not about which shape it is.
ONE_OF_THEM = MALFORMED_FINDINGS["a string"]

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


def a_draft_whose_findings_are(drafts_dir: Path, shape: object) -> None:
    """Write a corrected draft whose one member is not a list of entries."""
    corrected_draft(drafts_dir, key={**fit_key(), "findings": shape})


def refused_promotion(drafts_dir: Path) -> Exception:
    """Whatever `promote` raised, as an object, so its class is what gets asserted."""
    return refusal_from(lambda: promote_key.promote(APP, drafts_dir), "promote")


def promoted_files(keys_dir: Path) -> list[str]:
    """Every file promotion moved up, so "nothing moved" is a list and not a hunch."""
    return sorted(path.name for path in keys_dir.iterdir() if path.is_file())


def both_draft_names() -> list[str]:
    """The pair a successful promotion moves, by the names discovery reads."""
    return sorted(f"{APP}{suffix}" for suffix in (GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX))


# --- the refusal ------------------------------------------------------------------

@pytest.mark.parametrize("shape", FINDINGS_SHAPES, ids=FINDINGS_IDS)
def test_such_a_draft_is_refused_as_a_value_error(drafts_dir, shape: object) -> None:
    """`AttributeError` and `TypeError` are the two that escaped; neither is a `ValueError`."""
    a_draft_whose_findings_are(drafts_dir, shape)
    assert type(refused_promotion(drafts_dir)) is ValueError


@pytest.mark.parametrize("shape", FINDINGS_SHAPES, ids=FINDINGS_IDS)
def test_the_refusal_is_one_the_command_is_written_to_catch(drafts_dir,
                                                            shape: object) -> None:
    """The class matters because of this list, so the list is asserted and not assumed."""
    a_draft_whose_findings_are(drafts_dir, shape)
    assert isinstance(refused_promotion(drafts_dir), promote_key.EXPECTED_FAILURES)


def test_the_refusal_names_the_draft_and_what_is_wrong_with_it(drafts_dir) -> None:
    """A reader is told which file to open and what promotion could not read in it."""
    a_draft_whose_findings_are(drafts_dir, ONE_OF_THEM)
    said = str(refused_promotion(drafts_dir))
    assert f"{APP}{GROUND_TRUTH_SUFFIX}" in said
    assert "findings" in said


# --- and nothing moves ------------------------------------------------------------

def test_nothing_is_promoted_out_of_such_a_draft(keys_dir, drafts_dir) -> None:
    """A refusal that had already moved the pair would put an unread key where runs are scored."""
    a_draft_whose_findings_are(drafts_dir, ONE_OF_THEM)
    refused_promotion(drafts_dir)
    assert promoted_files(keys_dir) == []


def test_both_files_are_left_where_a_person_can_fix_them(drafts_dir) -> None:
    """The other half of "nothing moved": the draft is still there to be corrected."""
    a_draft_whose_findings_are(drafts_dir, ONE_OF_THEM)
    refused_promotion(drafts_dir)
    assert sorted(path.name for path in drafts_dir.iterdir()) == both_draft_names()


def test_a_draft_whose_entries_are_entries_still_promotes(keys_dir, drafts_dir) -> None:
    """The off position: this pair is fit, so "nothing moved" means the shape stopped it."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert promoted_files(keys_dir) == both_draft_names()


# --- what the command prints --------------------------------------------------------

def test_the_command_prints_a_reason_and_exits_one(keys_dir, monkeypatch,
                                                   capsys) -> None:
    """Where "a message, not a traceback" is actually decided for this shape of draft.

    An escaping `AttributeError` fails this test by leaving `main` at all: the
    exit code is only reached because the command caught what was raised.

    The command takes no folder argument, so the draft is planted where it really
    looks: `key_drafting.DRAFTED_KEYS_DIR`, which `conftest`'s autouse fixture has
    already pointed at a temporary folder of its own.
    """
    a_draft_whose_findings_are(key_drafting.DRAFTED_KEYS_DIR, ONE_OF_THEM)
    monkeypatch.setattr("sys.argv", ["promote_key.py", APP])
    assert promote_key.main() == FAILED
    said = capsys.readouterr().err
    assert said.startswith(PRINTED_REASON)
    assert "findings" in said
