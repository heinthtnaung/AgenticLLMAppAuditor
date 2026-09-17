"""A draft that claims a human checked it needs a local human to say so again.

The claim is recorded through `POST /api/keys/{app}/verify`, on a server with
**no authentication**. That is fine while it stays a draft: nothing discovers a
draft, it changes no number, and `discover_graded_apps` globs one level so
scoring cannot see it. Promotion is the moment it starts bounding a published
figure -- so `promote_key.py` refuses a verified draft unless
`--accept-verification` is passed, and the refusal names the flag.

**What the gate is not.** It does not re-check the entries, and it does not
judge the claim: it asks the person at the keyboard to stand behind one that
arrived over a socket. Promotion still moves neither `source` nor `verified` --
`test_promote_key_move.py` and `test_promoted_key_shipped_rules.py` hold that --
so a promoted verified draft is still `tool_drafted` and still carries both
drafting qualifications.

**The gate has to be able to not fire, or it says nothing.** An unverified draft
promotes with no flag at all, which is the ordinary case and the non-vacuity
under every refusal here.

`KEYS_DIR` is redirected to `tmp_path` by `redirect_keys_dir`, so no promotion
in this file can reach the checkout's own `grading_keys/`;
`test_promote_key_guards.py` is the net that proves it for the whole family.
"""

import json
import re
from pathlib import Path

import promote_key
import pytest
from drafted_key_fixtures import (
    APP,
    DRAFTS_NAME,
    corrected_draft,
    fit_key,
    redirect_keys_dir,
)
from keys import key_drafting
from keys.grading_keys import GROUND_TRUTH_SUFFIX, TOOL_DRAFTED, key_path

# What a draft the web editor has recorded a check on looks like on disk.
CHECKED_BY = "Quokka Reviewer"
CHECKED_ON = "2026-09-16"
VERIFIED_DRAFT = {**fit_key(), "verified": True, "verified_by": CHECKED_BY,
                  "verified_date": CHECKED_ON}

# A claim with no name on it, which a hand edit can leave behind even though the
# route refuses one: the gate is about `verified`, not about who is named.
ANONYMOUS_DRAFT = {**fit_key(), "verified": True, "verified_by": None,
                   "verified_date": CHECKED_ON}

# The flag, spelled as the command line spells it and as the message must name
# it. One constant, so the refusal and the parser cannot drift apart.
FLAG = "--accept-verification"

# The exit codes `main` returns.
FAILED, SUCCEEDED = 1, 0


@pytest.fixture
def keys_dir(monkeypatch, tmp_path) -> Path:
    """An empty keys folder under `tmp_path`, with `KEYS_DIR` pointed at it."""
    return redirect_keys_dir(monkeypatch, tmp_path)


@pytest.fixture
def drafts_dir(keys_dir: Path) -> Path:
    """The drafts folder one level down, where a draft waits to be promoted."""
    return keys_dir / DRAFTS_NAME


def promoted_key_exists(keys_dir: Path) -> bool:
    """Whether a key reached the level discovery reads."""
    return key_path(APP, GROUND_TRUTH_SUFFIX, keys_dir).is_file()


def run_command(monkeypatch, capsys, *flags: str) -> tuple[int, str, str]:
    """Run `promote_key.py <app> [flags]` and return its code, stdout and stderr.

    `main` takes no path, so it reads `key_drafting.DRAFTED_KEYS_DIR` -- which
    `conftest`'s autouse fixture has already pointed at a temporary folder. The
    two tests using this plant their draft there for that reason.
    """
    monkeypatch.setattr("sys.argv", ["promote_key.py", *flags, APP])
    code = promote_key.main()
    printed = capsys.readouterr()
    return code, printed.out, printed.err


# --- refused without the flag --------------------------------------------------

def test_a_verified_draft_is_refused(keys_dir, drafts_dir) -> None:
    """The gate: a claim made over an unauthenticated socket does not promote itself."""
    corrected_draft(drafts_dir, key=VERIFIED_DRAFT)
    with pytest.raises(ValueError, match="claims a human verified it"):
        promote_key.promote(APP, drafts_dir)


def test_the_refusal_names_the_flag_that_is_the_way_past(keys_dir, drafts_dir) -> None:
    """A refusal with no way out is a dead end; whoever hits this needs the next command."""
    corrected_draft(drafts_dir, key=VERIFIED_DRAFT)
    with pytest.raises(ValueError, match=re.escape(FLAG)):
        promote_key.promote(APP, drafts_dir)


def test_the_refusal_names_who_claimed_to_have_checked_it(keys_dir, drafts_dir) -> None:
    """The person deciding whether to stand behind it has to know whose claim it is."""
    corrected_draft(drafts_dir, key=VERIFIED_DRAFT)
    with pytest.raises(ValueError, match=re.escape(CHECKED_BY)):
        promote_key.promote(APP, drafts_dir)


def test_a_claim_with_no_name_is_still_refused(keys_dir, drafts_dir) -> None:
    """The gate is on `verified`, so a hand edit that ticked it without a name is caught too."""
    corrected_draft(drafts_dir, key=ANONYMOUS_DRAFT)
    with pytest.raises(ValueError, match=re.escape(FLAG)):
        promote_key.promote(APP, drafts_dir)


def test_the_refused_draft_is_left_exactly_where_it_was(keys_dir, drafts_dir) -> None:
    """Nothing half-moved: the pair is still a draft, and no app was enrolled."""
    draft = corrected_draft(drafts_dir, key=VERIFIED_DRAFT)
    with pytest.raises(ValueError):
        promote_key.promote(APP, drafts_dir)
    assert draft.is_file()
    assert not promoted_key_exists(keys_dir)


# --- and promoted with it ------------------------------------------------------

def test_the_flag_promotes_the_verified_draft(keys_dir, drafts_dir) -> None:
    """Non-vacuity for every refusal above: the gate opens, it is not a wall."""
    corrected_draft(drafts_dir, key=VERIFIED_DRAFT)
    promote_key.promote(APP, drafts_dir, accept_verification=True)
    assert promoted_key_exists(keys_dir)


def test_an_unverified_draft_needs_no_flag(keys_dir, drafts_dir) -> None:
    """The ordinary case, and the proof the gate is about the claim and not about promotion."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    assert promoted_key_exists(keys_dir)


def test_the_flag_changes_nothing_about_an_unverified_draft(keys_dir, drafts_dir) -> None:
    """Passing it where there is no claim is not an error and not a claim either."""
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir, accept_verification=True)
    assert promoted_key_exists(keys_dir)


def test_the_gate_is_closed_by_default_for_a_caller_that_is_not_the_command(
        keys_dir, drafts_dir) -> None:
    """A keyword default, asserted: `web/` is one import away from calling `promote` directly.

    Every refusal above relies on the default being `False`. Flipped to `True`
    they would all keep passing on the command line, because `main` passes the
    parsed flag explicitly -- and any other caller would inherit an open gate.
    """
    corrected_draft(drafts_dir, key=VERIFIED_DRAFT)
    with pytest.raises(ValueError, match=re.escape(FLAG)):
        promote_key.promote(APP, drafts_dir)
    assert not promoted_key_exists(keys_dir)


# --- what the command line does with it ----------------------------------------

def test_the_flag_is_off_unless_it_is_given() -> None:
    """The parser's own answer, so the default is held on both sides of `main`."""
    assert promote_key.build_parser().parse_args([APP]).accept_verification is False


def test_the_flag_is_on_when_it_is_given() -> None:
    """Guard: a flag that parsed to `False` either way would make the command useless."""
    assert promote_key.build_parser().parse_args(
        [FLAG, APP]).accept_verification is True


def test_the_command_reports_the_refusal_and_exits_one(keys_dir, monkeypatch,
                                                       capsys) -> None:
    """`main` turns it into one line on stderr, not a traceback out of `promote`."""
    corrected_draft(key_drafting.DRAFTED_KEYS_DIR, key=VERIFIED_DRAFT)
    code, _out, said = run_command(monkeypatch, capsys)
    assert code == FAILED
    assert FLAG in said


def test_the_command_promotes_when_the_flag_is_given(keys_dir, monkeypatch,
                                                     capsys) -> None:
    """The whole path, end to end: a checked draft becomes a key a run is scored against."""
    corrected_draft(key_drafting.DRAFTED_KEYS_DIR, key=VERIFIED_DRAFT)
    code, _out, said = run_command(monkeypatch, capsys, FLAG)
    assert (code, said) == (SUCCEEDED, "")
    assert promoted_key_exists(keys_dir)


def test_the_promoted_key_still_says_the_tool_drafted_it(keys_dir, drafts_dir) -> None:
    """What the gate does not do: accepting the claim does not make the key independent."""
    corrected_draft(drafts_dir, key=VERIFIED_DRAFT)
    promote_key.promote(APP, drafts_dir, accept_verification=True)
    promoted = json.loads(key_path(APP, GROUND_TRUTH_SUFFIX,
                                   keys_dir).read_text(encoding="utf-8"))
    assert promoted["source"] == TOOL_DRAFTED
    assert promoted["verified"] is True
