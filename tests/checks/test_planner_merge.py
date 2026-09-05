"""`merge_monotonically` attacked directly, on the argument its callers never vary.

`test_planner_monotone.py` reaches the merge through `order_checks`, which
always hands it the `eligible` list `run_checks` built -- non-empty, with
distinct names. So every test there varies the *first* argument, the model's
list, and none of them varies the second. This file does the other half.

Nothing here can be reached in production, and that is the point: the docstring
makes a claim about what the merge returns, and a claim only about the inputs
one caller happens to produce is a weaker claim than the one written down.
"""

from checks import planner
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK

# A name the model can ask for that is in no eligible list under test.
INVENTED_CHECK = "check_the_vibes"


def test_merging_into_no_eligible_checks_returns_nothing() -> None:
    """With nothing to run, the model's preference must not invent work."""
    assert planner.merge_monotonically([TAINT_CHECK, PERMISSION_CHECK], []) == []


def test_merging_nothing_into_nothing_returns_nothing() -> None:
    """Both arguments empty: the degenerate case, so neither loop can fail on it."""
    assert planner.merge_monotonically([], []) == []


def test_a_duplicated_eligible_name_the_model_names_collapses_to_one() -> None:
    """Asserted as built, and this is the case "a permutation of the **distinct** names" describes.

    The merge appends only names not already preferred, so once the model has
    named the check the second copy is dropped. `run_checks` never produces an
    `eligible` list with a repeat, so this pins behaviour, not a requirement.
    """
    assert planner.merge_monotonically([TAINT_CHECK], [TAINT_CHECK, TAINT_CHECK]) == [TAINT_CHECK]


def test_a_duplicated_eligible_name_the_model_does_not_name_survives_twice() -> None:
    """Asserted as built, and it is the limit of the "distinct names" wording.

    With the duplicate absent from `model_order` nothing is preferred, so the
    tail comprehension copies `eligible` whole and the repeat survives. The
    invariant that matters is unharmed -- no eligible check is lost, which is
    the only thing the planner may not do -- but "always a permutation of the
    distinct names" holds for the case above and not for this one.
    """
    duplicated = [PERMISSION_CHECK, PERMISSION_CHECK]
    assert planner.merge_monotonically([], duplicated) == duplicated


def test_a_model_naming_only_invented_checks_leaves_duplicates_alone_too() -> None:
    """The same tail path, reached by a model that named something outside `eligible`."""
    duplicated = [PERMISSION_CHECK, PERMISSION_CHECK]
    assert planner.merge_monotonically([INVENTED_CHECK], duplicated) == duplicated


def test_an_invented_name_is_never_added_to_the_order() -> None:
    """The monotone rule's other half: the model may move work, never create it."""
    merged = planner.merge_monotonically([INVENTED_CHECK, TAINT_CHECK], [TAINT_CHECK])
    assert merged == [TAINT_CHECK]
