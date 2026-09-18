"""The page groups runs by repository on a value the server sent, and derives none itself.

`canonical_url` decides whether two URLs name one repository: a trailing slash
and a `.git` suffix removed, and **nothing else**, because two owners with the
same repository name are two repositories. `pipeline._reused` joins on it, the
run record serves it as `canonical_repo_url`, and `frontend/src/repoGroup.js`
groups on the served value.

**A second implementation in JavaScript is the thing this file forbids**, and it
is a sharper rule than the one the page follows for the run-status vocabulary.
Three status strings are a closed set a test can compare name for name against
`RUN_STATUSES`; a *function over an open domain* cannot be shown equal to
another implementation by any number of examples. So the copy is refused
outright rather than checked, and the check is the absence of the one token such
a copy cannot be written without: a `.git` literal.

**This is a guard with a history, and that is why it is worded as one.** A JS
copy of `canonical_url` existed and was deleted when the grouping was built --
and the docstring written for it claimed "a test derives its cases from the
Python". No such test existed. The claim was checkable and unchecked, which is
the state this file ends.

**Comments are stripped first, and that is load-bearing here rather than
incidental.** Two files in the page mention `.git` in prose today: `repoGroup.js`
explaining why the rule is not there, and `SourceWindow.jsx` explaining what the
clone does with it. A sweep over raw text would report both and the only way to
green would be to stop writing the explanation down -- a rule nobody agreed to,
which is the exact defect `jsx_sweep.strip_comments` was written for.

What it cannot see: a suffix stripped without naming it -- `url.slice(0, -4)` --
or one assembled from pieces. Both are unreadable enough that a reviewer would
ask, which is not a guarantee and is stated rather than glossed.

Reads the page's own `.js` and `.jsx` as text, and the record's field list from
`web/run_record.py`. No fastapi, no node, no build.
"""

from run_record import COMPUTED_FIELDS

from .jsx_sweep import FRONTEND_SRC, accessors_in, strip_comments

GROUPING_MODULE = FRONTEND_SRC / "repoGroup.js"

# The field the page groups on, and the prefix it is read off a row by.
THE_FIELD = "canonical_repo_url"
THE_ROW = "run"

# What a re-derived rule cannot be written without, in the three ways JavaScript
# quotes a string. Searched for after comments are stripped.
GIT_LITERALS = ('".git"', "'.git'", "`.git`")

# The field a group must *not* be keyed on. A run that failed before it resolved
# a tree has no `app` at all, and those are exactly the rows a reader wants
# beside the successful runs of the same repository.
THE_WRONG_KEY = "app"

# Floors, so a sweep that read nothing cannot pass as a sweep that found no
# copy. Twenty-nine source files in the page today.
MINIMUM_FILES = 10
MINIMUM_CHARACTERS = 20000


def page_sources() -> list:
    """Every JavaScript and JSX file the page is written in."""
    return sorted([*FRONTEND_SRC.rglob("*.js"), *FRONTEND_SRC.rglob("*.jsx")])


def git_literals_in(text: str) -> list[str]:
    """Every `.git` literal one file's code writes, comments excluded."""
    stripped = strip_comments(text)
    return [written for written in GIT_LITERALS if written in stripped]


def copies_of_the_rule() -> list[str]:
    """Every file in the page that writes a `.git` literal, or nothing."""
    return [f"{source.name}: {written}" for source in page_sources()
            for written in git_literals_in(source.read_text(encoding="utf-8"))]


def grouping_source() -> str:
    """The grouping module's own source, comments stripped."""
    return strip_comments(GROUPING_MODULE.read_text(encoding="utf-8"))


def fields_the_grouping_reads() -> list[str]:
    """Every field `repoGroup.js` reads off a run."""
    return accessors_in(GROUPING_MODULE.read_text(encoding="utf-8"), THE_ROW)


# --- the rule is not written twice ----------------------------------------------

def test_no_file_in_the_page_writes_a_git_suffix_literal() -> None:
    """The one token a JavaScript copy of `canonical_url` cannot be written without."""
    assert copies_of_the_rule() == []


def test_the_sweep_read_the_whole_page() -> None:
    """Non-vacuity: an empty file list satisfies the absence above having read nothing."""
    sources = page_sources()
    assert len(sources) >= MINIMUM_FILES
    assert sum(len(source.read_text(encoding="utf-8")) for source in sources) \
        >= MINIMUM_CHARACTERS


def test_a_git_suffix_written_in_code_is_reported() -> None:
    """Planted: the absence above is an empty list either way."""
    assert git_literals_in('const key = url.replace(".git", "");') == ['".git"']


def test_a_git_suffix_written_in_prose_is_not_reported() -> None:
    """The stripping, measured: explaining the rule may not be what fails this file."""
    assert git_literals_in("// a `.git` strip here would be a second owner\n") == []


# --- and the page groups on what the server sent --------------------------------

def test_the_grouping_keys_on_the_served_field() -> None:
    """One value, two readers: the page and `pipeline._reused` cannot disagree about it."""
    assert THE_FIELD in fields_the_grouping_reads()


def test_the_field_it_groups_on_is_one_the_record_really_carries() -> None:
    """Across a boundary with no compiler: a wrong name is `undefined`, and groups everything."""
    assert THE_FIELD in COMPUTED_FIELDS


def test_the_grouping_is_not_keyed_on_the_app_name() -> None:
    """A run that failed before resolving a tree has no `app`, and belongs in its repository's group."""
    assert THE_WRONG_KEY not in fields_the_grouping_reads()


def test_the_grouping_module_was_read_and_is_not_empty() -> None:
    """Non-vacuity: an unreadable module satisfies both the presence and the absence above."""
    assert len(fields_the_grouping_reads()) >= 1
    assert "export function" in grouping_source()
