"""`canonical_repo_url` is computed from the record, by the function `src/` owns.

The history page groups runs by repository, and two runs of one repository are
routinely spelled two ways -- a person pastes `.../demo`, a git remote hands out
`.../demo.git`, a browser leaves a trailing slash. Deciding that those are one
repository is `src/repo_url.py::canonical_url`'s job, and `pipeline._reused`
already joins on it: a page that disagreed would show two groups for a
repository the tool itself treats as one.

**Why this file exists at all.** The field is registered in
`run_record.COMPUTED_FIELDS`, and both of the tests that sweep the record's
fields derive their allowed sets *from that constant* -- so adding the name made
them pass and **nothing asserted the value**. A `canonical_repo_url` that
returned the empty string, or the record's `app`, or the URL untouched, would
have satisfied every test in this folder.

So the value is asserted here, and always against the **imported** function
rather than a string typed into this file. A transcribed expectation would be a
second implementation of the rule, in the one place a disagreement with the real
one is guaranteed to go unnoticed: two owners' identically named repositories
are two repositories, and that property cannot be pinned by any number of
examples written out by hand.

What a transcription-free comparison cannot do is show the function is
*right* -- `canonical_url` returning its argument unchanged would satisfy the
first section below. That is why the second section is the equivalence classes
instead: the spellings that must land together, and the two that must not,
stated without naming what either lands on. `tests/test_repo_url_canonical.py`
is where the function's own behaviour is held.

Free of fastapi: `run_record.py` is, on purpose, and the record is where the
field is computed. What the endpoints answer with is `test_run_routes.py`, and
the page's side of the join -- that the browser re-derives nothing -- is
`test_repo_group_join.py`.
"""

import inspect
from dataclasses import replace

from repo_url import canonical_url
from run_record import COMPUTED_FIELDS, DURABLE_FIELDS, body, summary

from .run_rows import AUDITOR, WHEN, running

THE_FIELD = "canonical_repo_url"

# One repository, written the four ways a person or a git remote writes it.
PLAIN = "https://github.com/owner/demo"
WITH_SUFFIX = "https://github.com/owner/demo.git"
WITH_SLASH = "https://github.com/owner/demo/"
WITH_BOTH = "https://github.com/owner/demo.git/"

SPELLINGS = (PLAIN, WITH_SUFFIX, WITH_SLASH, WITH_BOTH)

# Another owner, same last segment. The collision the join must not make: two
# people's forks of a name are not one repository, however alike they look in a
# list.
ANOTHER_OWNER = "https://github.com/somebody-else/demo"

# Another forge entirely, same path.
ANOTHER_HOST = "https://gitlab.invalid/owner/demo"

RUN_ID = "a" * 32


def a_body(repo_url: str) -> dict:
    """One run as an API body, for a run of the repository spelled this way."""
    return body(replace(running(RUN_ID), repo_url=repo_url),
                artifacts_present=False, artifacts_current=True)


def served(repo_url: str) -> str:
    """The canonical URL one body carries."""
    return a_body(repo_url)[THE_FIELD]


# --- the value is the function's, not a copy of the rule -----------------------

def test_the_body_carries_the_field_at_all() -> None:
    """Registered in `COMPUTED_FIELDS`, which is what made the field sweeps pass for free."""
    assert THE_FIELD in a_body(PLAIN)
    assert THE_FIELD in COMPUTED_FIELDS


def test_the_served_value_is_the_function_applied_to_this_records_url() -> None:
    """Four spellings, compared against the imported function and never a typed string."""
    assert [served(url) for url in SPELLINGS] == [canonical_url(url) for url in SPELLINGS]


def test_it_is_derived_from_the_records_own_url_and_not_from_some_other_field() -> None:
    """A field computed off the wrong column would still be a string, and still pass a sweep."""
    assert served(ANOTHER_OWNER) == canonical_url(ANOTHER_OWNER)
    assert served(ANOTHER_OWNER) != served(PLAIN)


# --- and it puts the right runs together ---------------------------------------

def test_the_four_spellings_of_one_repository_share_one_value() -> None:
    """The whole point: a person's paste and a git remote's URL are one group."""
    assert len({served(url) for url in SPELLINGS}) == 1


def test_those_four_spellings_really_are_four_different_urls() -> None:
    """Non-vacuity: four identical inputs would agree above without normalising anything."""
    assert len(set(SPELLINGS)) == len(SPELLINGS)


def test_two_owners_with_the_same_repository_name_stay_two_repositories() -> None:
    """The collision a looser rule would create, in a list a person reads as fact."""
    assert served(ANOTHER_OWNER) != served(PLAIN)


def test_the_same_path_on_another_forge_stays_another_repository() -> None:
    """Nothing about the host is normalised, and a fork elsewhere is not this repository."""
    assert served(ANOTHER_HOST) != served(PLAIN)


# --- it survives the form the history list is served in ------------------------

def test_the_field_survives_the_summary_the_list_is_built_from() -> None:
    """Where it is actually read: the list row, not the detail body."""
    assert summary(a_body(WITH_SUFFIX))[THE_FIELD] == canonical_url(WITH_SUFFIX)


def test_the_summary_drops_what_it_is_meant_to_and_not_this() -> None:
    """Non-vacuity on the check above: `summary` really does remove keys."""
    row = summary(a_body(PLAIN))
    assert "result" not in row
    assert THE_FIELD in row


# --- and no caller can pass a wrong one ----------------------------------------

def test_the_body_takes_no_canonical_url_from_its_caller() -> None:
    """Computed inside `body`, unlike the two flags: a route cannot hand it a wrong value.

    The two filesystem flags need a directory and a store query, so only a route
    can establish them and they are parameters. This one needs the record alone,
    and a parameter would be a way for one caller to disagree with the pipeline.
    """
    assert THE_FIELD not in inspect.signature(body).parameters


def test_it_is_not_a_stored_column() -> None:
    """Stored, it would be a second copy of a join key, frozen at the moment it was written."""
    assert THE_FIELD not in DURABLE_FIELDS


def test_the_record_it_is_computed_from_is_a_real_one() -> None:
    """Non-vacuity: a body built from nothing would satisfy the absences above."""
    assert a_body(PLAIN)["auditor"] == AUDITOR
    assert a_body(PLAIN)["started_at"] == WHEN
