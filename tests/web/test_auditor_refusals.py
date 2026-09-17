"""The three reasons a name is not a usable auditor, written once and used twice.

`run_record.auditor_refusals` is the whole rule. It is called by
`run_routes.audit`, which turns the list into a 400 before any row is written,
and by `RunRecord.__post_init__`, which raises on the first entry. Written
twice it had already grown two different spellings of "printable", which is the
defect this function exists to close -- so the join is asserted here rather than
described: every name the list refuses is a name the record refuses, **with the
same sentence**.

The name is free text on an endpoint with no authentication, so it is a claim
and not an identity. What the rules are for is narrower than it sounds: it is
the one operator-supplied string that is not a URL, and the page renders it.

No fastapi here -- `run_record.py` is free of it on purpose -- so this runs on a
clean checkout with no web extra installed. The HTTP half, that a refused name
comes back as a 400 carrying this sentence, is `test_api_refusals.py`.
"""

import pytest

from run_record import MAX_AUDITOR_LENGTH, RunRecord, auditor_refusals

URL = "https://example.invalid/owner/demo-app"
WHEN = "2026-09-09T12:00:00+00:00"
RUN_ID = "a" * 32

# The four names the rules refuse, one per reason. The blank and the
# whitespace-only one meet the same `.strip()`, which is the point: a padded
# browser field is nobody, not a person named by three spaces.
BLANK_AUDITOR = ""
WHITESPACE_AUDITOR = "   \t "
TOO_LONG_AUDITOR = "a" * (MAX_AUDITOR_LENGTH + 1)
CONTROL_CHARACTER_AUDITOR = "Quokka\nReviewer"
REFUSED_AUDITORS = (BLANK_AUDITOR, WHITESPACE_AUDITOR, TOO_LONG_AUDITOR,
                    CONTROL_CHARACTER_AUDITOR)

# An ordinary name, so every refusal above is shown to be about the name and not
# about the function.
ACCEPTED_AUDITOR = "Quokka Reviewer"

# The sentences, spelled as the module writes them. The length one counts two
# numbers, so it is matched by its opening and its contents rather than
# transcribed and left to drift.
NO_AUDITOR = "an audit records who asked for it; give an auditor name"
CONTROL_CHARACTERS = "the auditor name must not contain control characters"
TOO_LONG_OPENING = "the auditor name is"


def a_record(auditor: str) -> RunRecord:
    """One accepted run under a given name, which is where the record applies the rules."""
    return RunRecord(run_id=RUN_ID, repo_url=URL, auditor=auditor,
                     options={"url": URL}, started_at=WHEN)


# --- the rules themselves ------------------------------------------------------

def test_an_ordinary_name_is_refused_for_nothing() -> None:
    """Non-vacuity: a name that breaks no rule returns an empty list, not a message."""
    assert auditor_refusals(ACCEPTED_AUDITOR) == []


def test_a_blank_name_is_refused() -> None:
    """A run records who asked for it, and this endpoint has no authentication to ask."""
    assert auditor_refusals(BLANK_AUDITOR) == [NO_AUDITOR]


def test_a_name_of_only_whitespace_is_refused_as_blank() -> None:
    """The same `.strip()` the URL gets: a padded browser field is not a name."""
    assert auditor_refusals(WHITESPACE_AUDITOR) == [NO_AUDITOR]


def test_a_name_over_the_cap_is_refused_and_both_numbers_are_counted() -> None:
    """Capped because it is the one operator-supplied string that is not a URL."""
    refused = auditor_refusals(TOO_LONG_AUDITOR)
    assert len(refused) == 1
    assert refused[0].startswith(TOO_LONG_OPENING)
    assert str(len(TOO_LONG_AUDITOR)) in refused[0]
    assert str(MAX_AUDITOR_LENGTH) in refused[0]


def test_a_name_at_the_cap_is_refused_for_nothing() -> None:
    """Non-vacuity: the rule is about the length, not about a name being long."""
    assert auditor_refusals("a" * MAX_AUDITOR_LENGTH) == []


def test_a_name_carrying_a_control_character_is_refused() -> None:
    """It is rendered on a page, so a newline or a tab in it is refused rather than shown."""
    assert auditor_refusals(CONTROL_CHARACTER_AUDITOR) == [CONTROL_CHARACTERS]


def test_the_cap_is_the_one_the_module_publishes() -> None:
    """Guard: a cap of zero would make the two length tests above agree about nothing."""
    assert MAX_AUDITOR_LENGTH > len(ACCEPTED_AUDITOR)


# --- one spelling, used twice --------------------------------------------------

@pytest.mark.parametrize("auditor", REFUSED_AUDITORS)
def test_the_record_refuses_exactly_what_the_rules_refuse(auditor) -> None:
    """The join: the record raises the list's own first sentence, never a second wording.

    This is the defect the shared function closes. The request path and the
    record path had each grown their own idea of what "printable" meant, so a
    name one accepted the other rejected -- after the 400 had already been
    passed.
    """
    with pytest.raises(ValueError) as refused:
        a_record(auditor)
    assert str(refused.value) == auditor_refusals(auditor)[0]


def test_a_name_the_rules_accept_builds_a_record() -> None:
    """Non-vacuity for the four above: the refusals are the name's, not the constructor's."""
    assert a_record(ACCEPTED_AUDITOR).auditor == ACCEPTED_AUDITOR


def test_a_name_at_the_cap_builds_a_record_too() -> None:
    """The boundary on the record side as well, since it applies the rule rather than repeats it."""
    at_the_cap = "a" * MAX_AUDITOR_LENGTH
    assert a_record(at_the_cap).auditor == at_the_cap
