"""A probe record keeps "we did not look" distinct from "we looked and found nothing".

That distinction is the whole reason the record exists, so it is enforced in
the constructor: an outcome that concluded nothing must say why, and one that
concluded must not pretend it had a reason not to.
"""

import pytest

from artifacts.finding import (
    CONFIRMED,
    INCONCLUSIVE,
    NOT_RUN,
    PROBE_REASONS,
    REFUTED,
    SURFACE_SUBJECT,
    UNRESOLVED_OUTCOMES,
    Probe,
)
from findings_fixtures import PROBE_NAME, SURFACE_ID, confirmed_probe

# The outcomes that reached a conclusion, so they carry no reason.
CONCLUDED_OUTCOMES = (CONFIRMED, REFUTED)

DETAIL = "the tool holds a shell"


def test_probe_id_is_the_name_and_the_subject() -> None:
    """The handle a finding cites is derived from the probe, never from a counter."""
    assert confirmed_probe().id == f"{PROBE_NAME}:{SURFACE_ID}"


def test_an_unknown_outcome_is_refused() -> None:
    """A fifth outcome would be a conclusion no reader of the schema can interpret."""
    with pytest.raises(ValueError, match="unknown probe outcome"):
        Probe(PROBE_NAME, SURFACE_SUBJECT, SURFACE_ID, "maybe", DETAIL)


def test_an_unknown_subject_kind_is_refused() -> None:
    """A probe runs against a surface or a component; there is no third thing."""
    with pytest.raises(ValueError, match="unknown subject kind"):
        Probe(PROBE_NAME, "REPOSITORY", SURFACE_ID, CONFIRMED, DETAIL)


def test_an_empty_subject_is_refused() -> None:
    """A probe against nothing has no id and nothing to attach its outcome to."""
    with pytest.raises(ValueError, match="subject_id must not be empty"):
        Probe(PROBE_NAME, SURFACE_SUBJECT, "", CONFIRMED, DETAIL)


@pytest.mark.parametrize("outcome", UNRESOLVED_OUTCOMES)
def test_an_unresolved_outcome_without_a_reason_is_refused(outcome: str) -> None:
    """Reaching no conclusion is reportable only when the record says why."""
    with pytest.raises(ValueError, match="needs a reason"):
        Probe(PROBE_NAME, SURFACE_SUBJECT, SURFACE_ID, outcome, DETAIL)


@pytest.mark.parametrize("outcome", UNRESOLVED_OUTCOMES)
def test_an_unresolved_outcome_with_an_unlisted_reason_is_refused(outcome: str) -> None:
    """The reasons are a fixed vocabulary, so a report can count them."""
    with pytest.raises(ValueError, match="needs a reason"):
        Probe(PROBE_NAME, SURFACE_SUBJECT, SURFACE_ID, outcome, DETAIL, "it felt hard")


@pytest.mark.parametrize("outcome", CONCLUDED_OUTCOMES)
def test_a_concluded_outcome_carrying_a_reason_is_refused(outcome: str) -> None:
    """A probe that concluded has no excuse to record, and one would read as doubt."""
    with pytest.raises(ValueError, match="concluded, so it carries no reason"):
        Probe(PROBE_NAME, SURFACE_SUBJECT, SURFACE_ID, outcome, DETAIL, PROBE_REASONS[0])


@pytest.mark.parametrize("reason", PROBE_REASONS)
def test_every_listed_reason_is_accepted_and_kept(reason: str) -> None:
    """Each documented reason builds a record that still carries it."""
    probe = Probe(PROBE_NAME, SURFACE_SUBJECT, SURFACE_ID, INCONCLUSIVE, DETAIL, reason)
    assert probe.reason == reason


def test_a_planned_probe_that_never_ran_is_representable() -> None:
    """`not_run` with a reason is how a planned check reports its own absence."""
    probe = Probe(PROBE_NAME, SURFACE_SUBJECT, SURFACE_ID, NOT_RUN, DETAIL, "app_not_runnable")
    assert (probe.outcome, probe.reason) == (NOT_RUN, "app_not_runnable")


def test_a_confirmed_probe_carries_no_reason() -> None:
    """The normal confirming case leaves `reason` null, which the schema requires."""
    assert confirmed_probe().reason is None
