"""One spelling of a repository URL, and the two things it may not normalise away.

`canonical_url` exists so a pin written `.../repo` matches a request for
`.../repo.git`: `destination_name` already strips the suffix, so both spellings
land on one directory, and without this the directory said "same repo" while
the pin said "different repo" and a re-audit of a correctly fetched tree was
refused. It shipped with no test anywhere, which is the rule-13 debt this file
pays.

Split from `test_repo_url.py`, whose subject is the trust boundary -- which
transports are refused, which last path segments are safe. This one is about
**identity**: when two URLs name one repository. The property that makes the
function worth more than `.rstrip("/")` is the last section: two owners'
same-named repositories are still two repositories, which is the collision the
pin exists to catch and the reason `pipeline._reused` compares pins at all.

Pure strings throughout -- no network, no filesystem, nothing fetched. What
`pipeline._reused` does with the answer is `tests/cli/test_pipeline_reuse_pin.py`.
"""

from functools import partial

import pytest

from guarded_read import refusal_from
from repo_url import canonical_url, destination_name

# One repository, written the four ways a person or a git remote writes it.
PLAIN = "https://github.com/owner/demo"
WITH_SUFFIX = "https://github.com/owner/demo.git"
WITH_SLASH = "https://github.com/owner/demo/"
WITH_BOTH = "https://github.com/owner/demo.git/"

# Another owner, same last segment: the collision `destination_name` creates by
# construction and the pin is there to catch.
ANOTHER_OWNER = "https://github.com/somebody-else/demo"

# Another host, same path: a fork on a different forge is not this repository.
ANOTHER_HOST = "https://gitlab.invalid/owner/demo"

# The same path in another case. Nothing about the host or the path is
# normalised, and this says so rather than leaving it to the docstring.
ANOTHER_CASE = "https://github.com/Owner/Demo"

# `.git` that is not a suffix: only a trailing one is one.
SUFFIX_INSIDE_THE_PATH = "https://github.com/owner.git/demo"

# What a hand-edited pin leaves where a URL belongs. `_reused` reads this file,
# so these are the values `canonical_url` would be handed without a type check.
NOT_A_URL = {"an int": 123, "a list": ["https://github.com/owner/demo"], "null": None}
NOT_A_URL_IDS = list(NOT_A_URL)
NOT_A_URL_SHAPES = list(NOT_A_URL.values())

# The two classes "this is not a string" reaches a caller as. Named because the
# test below asserts a class rather than a message.
NOT_A_STRING_CLASSES = (AttributeError, TypeError)


# --- what is taken off ----------------------------------------------------------

def test_a_trailing_slash_is_not_part_of_the_name() -> None:
    """A link copied from a browser's address bar carries one; the repository does not."""
    assert canonical_url(WITH_SLASH) == PLAIN


def test_the_git_suffix_is_not_part_of_the_name() -> None:
    """What `git clone` prints and `destination_name` already strips."""
    assert canonical_url(WITH_SUFFIX) == PLAIN


def test_a_suffix_and_a_slash_together_are_both_taken_off() -> None:
    """Both at once, in the order the function does them: slash first, then suffix."""
    assert canonical_url(WITH_BOTH) == PLAIN


def test_a_url_with_neither_is_returned_unchanged() -> None:
    """The off position: a plain link is already canonical and must not be rewritten."""
    assert canonical_url(PLAIN) == PLAIN


def test_only_a_trailing_git_is_a_suffix() -> None:
    """`.git` inside the path is somebody's account name, not a clone suffix."""
    assert canonical_url(SUFFIX_INSIDE_THE_PATH) == SUFFIX_INSIDE_THE_PATH


# --- what it was added to do ----------------------------------------------------

def test_the_two_spellings_of_one_repository_agree() -> None:
    """The behaviour the function exists for, and the one nothing asserted before it."""
    assert canonical_url(PLAIN) == canonical_url(WITH_SUFFIX)


def test_every_spelling_of_one_repository_agrees() -> None:
    """All four together, so a case that stopped being handled cannot hide behind the others."""
    assert len({canonical_url(url) for url in (PLAIN, WITH_SUFFIX, WITH_SLASH,
                                               WITH_BOTH)}) == 1


# --- what it must never do ------------------------------------------------------

def test_two_owners_of_one_name_are_still_two_repositories() -> None:
    """The property `_reused` depends on, and the reason this is not `.rstrip('/')`."""
    assert canonical_url(ANOTHER_OWNER) != canonical_url(WITH_SUFFIX)


def test_two_hosts_holding_one_path_are_still_two_repositories() -> None:
    """A fork on another forge shares the path and is not the tree that was pinned."""
    assert canonical_url(ANOTHER_HOST) != canonical_url(PLAIN)


def test_the_path_is_not_case_folded() -> None:
    """Nothing but the slash and the suffix is normalised; a different path is a different repo."""
    assert canonical_url(ANOTHER_CASE) != canonical_url(PLAIN)


def test_the_directory_collision_is_exactly_what_the_pin_has_to_catch() -> None:
    """Both halves in one test, because the pair is the whole argument for the pin.

    Two owners' `demo` land on one `fetched/demo` -- `destination_name` says so
    -- while their canonical URLs differ. If canonicalisation ever agreed here,
    `_reused` would audit one owner's tree for a request naming the other's.
    """
    assert destination_name(ANOTHER_OWNER) == destination_name(WITH_SUFFIX)
    assert canonical_url(ANOTHER_OWNER) != canonical_url(WITH_SUFFIX)


# --- and what it is not defined over --------------------------------------------

@pytest.mark.parametrize("shape", NOT_A_URL_SHAPES, ids=NOT_A_URL_IDS)
def test_a_value_that_is_not_a_string_has_no_canonical_form(shape: object) -> None:
    """Why `pipeline._reused` checks the type *before* calling this, not after.

    The comparison this replaced refused a non-string pin for free --
    `123 != "https://..."` is True -- and routing both sides through a function
    that calls `.rstrip` took that for granted. This is the fact that makes the
    caller's `isinstance` load-bearing rather than belt-and-braces.
    """
    raised = refusal_from(partial(canonical_url, shape), f"canonical_url({shape!r})")
    assert isinstance(raised, NOT_A_STRING_CLASSES), (
        f"canonical_url refused {shape!r} with {type(raised).__name__}. If it now "
        "refuses a non-string deliberately, pipeline._reused's type check should be "
        "revisited rather than deleted")
