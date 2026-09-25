"""Guards on redaction as a whole: what it records, what it leaves alone, what it refuses."""

import pytest

from council.redaction import redact

from redaction_samples import CVE_ID, GHSA_ID, PUBLISHED

PLAIN = "A remote attacker can send a crafted request and read arbitrary files."


def test_what_was_withheld_is_logged_in_the_order_the_patterns_run():
    # Not the order the strings stood in the advisory. A reader taking `removed`
    # for a reading order, or for a set, is reading it wrong, so the docstring
    # says which it is and this holds it to that.
    redacted = redact(f"{CVE_ID} is scored {PUBLISHED} and tracked as {GHSA_ID}.")
    assert redacted.removed == (PUBLISHED, CVE_ID, GHSA_ID)


def test_an_advisory_with_nothing_to_hide_comes_back_untouched():
    redacted = redact(PLAIN)
    assert redacted.text == PLAIN
    assert redacted.removed == ()


def test_an_advisory_with_no_text_is_refused_rather_than_prompted_with():
    with pytest.raises(ValueError, match="no advisory text"):
        redact("   ")


def test_something_that_is_not_text_is_refused_by_type():
    with pytest.raises(TypeError, match="must be text, not int"):
        redact(7)
