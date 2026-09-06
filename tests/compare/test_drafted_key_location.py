"""A drafted key lives in `grading_keys/drafts/`, which nothing discovers and git ignores.

Three claims hold that folder in place, and every one of them is load-bearing
somewhere else:

* `discover_graded_apps` globs **non-recursively**, so a key one level down
  enrols no app. `emit_vex.product_iri`, `fetch_repo._pin_for` and
  `fetch_repo.check_not_a_graded_app` each look for a key at the top level only,
  and each would answer differently about a draft if that glob reached it -- a
  VEX product named from a model-written pin, a tree pinned by one, and a
  refusal of the second run against the same URL.
* the drafts folder is the one part of `grading_keys/` git ignores, so a
  model-written answer key cannot become this project's committed evidence.
* it sits *inside* `grading_keys/`, one level down, because a human moving the
  pair up one level is what accepts responsibility for it.

The non-recursion is asserted over a `tmp_path` mirror of that layout, never
over the real folder: a test may not write into the repository. The structural
test is what makes the mirror faithful -- the real drafts directory is a child
of the real keys directory, so a child of `tmp_path` answers the same question.

`.gitignore` is read and matched here rather than asked of `git`, so this file
passes in a checkout with no `.git` present at all.
"""

from fnmatch import fnmatch

from conftest import REPO_ROOT
from drafted_key_fixtures import APP, draft_into
from fetch_repo import check_not_a_graded_app
from keys.grading_keys import GROUND_TRUTH_SUFFIX, KEYS_DIR, discover_graded_apps
from keys.key_drafting import DRAFTED_KEYS_DIR

# The two repository-relative paths the ignore rules must treat differently.
# Neither file exists -- `grading_keys/` has held no key since 2026-09-06 and
# the drafted one is written under `tmp_path` -- and neither needs to: the
# patterns are matched against the paths a key *would* take.
TOP_LEVEL_KEY_PATH = f"{KEYS_DIR.name}/{APP}{GROUND_TRUTH_SUFFIX}"
DRAFTED_KEY_PATH = (f"{KEYS_DIR.name}/{DRAFTED_KEYS_DIR.name}/"
                    f"{APP}{GROUND_TRUTH_SUFFIX}")

# The pattern that has to be in `.gitignore`, spelled from the constants the
# code uses rather than as a literal, so moving the folder fails this test.
DRAFTS_PATTERN = f"{KEYS_DIR.name}/{DRAFTED_KEYS_DIR.name}/"


def ignore_patterns() -> list[str]:
    """Every pattern `.gitignore` states, with its comments and blank lines dropped."""
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.startswith("#")]


def ignores(relative_path: str, pattern: str) -> bool:
    """Say whether one pattern covers one repository-relative path.

    Only the two forms `.gitignore` actually uses: a trailing-slash directory
    prefix, and a plain name or glob. Git's full matcher is not reimplemented --
    `test_the_matcher_fires_on_a_drafted_key` is what keeps this honest.
    """
    if pattern.endswith("/"):
        return relative_path.startswith(pattern)
    return fnmatch(relative_path, pattern) or relative_path.startswith(f"{pattern}/")


# --- where the folder is ------------------------------------------------------

def test_the_drafts_directory_is_a_child_of_the_keys_directory() -> None:
    """One level down, so accepting a draft is a human moving the pair up one level."""
    assert DRAFTED_KEYS_DIR.parent == KEYS_DIR
    assert DRAFTED_KEYS_DIR != KEYS_DIR


# --- nothing discovers it -----------------------------------------------------

def test_a_key_one_level_down_enrols_no_app(tmp_path) -> None:
    """The claim three modules rest on: the glob is non-recursive, so a draft is not an app."""
    draft_into(tmp_path / DRAFTED_KEYS_DIR.name)
    assert discover_graded_apps(tmp_path) == ()


def test_the_same_pair_at_the_top_level_does_enrol_one(tmp_path) -> None:
    """Guard: the test above would pass over a pair that was never written at all."""
    draft_into(tmp_path)
    assert discover_graded_apps(tmp_path) == (APP,)


def test_a_second_run_against_the_same_repository_is_not_refused(tmp_path) -> None:
    """`check_not_a_graded_app` reads the shipped folder alone, so a draft refuses nothing."""
    draft_into(tmp_path / DRAFTED_KEYS_DIR.name)
    assert check_not_a_graded_app(APP) is None


# --- git ignores it, and only it ----------------------------------------------

def test_the_drafts_folder_is_gitignored() -> None:
    """A model-written answer key must not be committable as this project's evidence."""
    assert DRAFTS_PATTERN in ignore_patterns()


def test_a_key_at_the_top_level_is_not_gitignored() -> None:
    """The other half: `grading_keys/` itself stays tracked, so a hand-written key ships."""
    assert [pattern for pattern in ignore_patterns()
            if ignores(TOP_LEVEL_KEY_PATH, pattern)] == []


def test_the_matcher_fires_on_a_drafted_key() -> None:
    """Guard: a matcher that matched nothing would make the test above vacuous."""
    assert [pattern for pattern in ignore_patterns()
            if ignores(DRAFTED_KEY_PATH, pattern)] == [DRAFTS_PATTERN]


# --- and the repository's own keys are untouched by any of it -----------------

def test_a_drafting_run_leaves_the_repositorys_own_keys_as_they_were(tmp_path) -> None:
    """The assertion a drafting run must not disturb: no argument, the real folder.

    Before against after, not against a list of what ships -- `grading_keys/`
    holds no key today, and this has to fail on a draft landing there whether it
    holds one or not. The first assertion is what stops the other two holding
    over a drafting run that wrote nothing at all.
    """
    before = discover_graded_apps()
    drafted = draft_into(tmp_path / DRAFTED_KEYS_DIR.name)
    assert drafted.is_file(), "the draft was written, so this is a run that really happened"
    assert discover_graded_apps() == before
    assert APP not in discover_graded_apps()
