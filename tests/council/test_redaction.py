"""Guards on what a member must not see: the identifiers and the published scores."""

import pytest

from council.redaction import IDENTIFIER_MARKER, VECTOR_MARKER, redact

CVE_ID = "CVE-2021-44228"
GHSA_ID = "GHSA-jfh8-c2jp-5v3q"
PUBLISHED = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"

PLAIN = "A remote attacker can send a crafted request and read arbitrary files."


def test_a_cve_id_never_reaches_the_member():
    # The whole reason the council is measurable: a model that recognises the id
    # recites the answer from training instead of reading the advisory.
    redacted = redact(f"{CVE_ID} allows remote code execution.")
    assert CVE_ID not in redacted.text
    assert redacted.removed == (CVE_ID,)


def test_a_ghsa_id_never_reaches_the_member():
    redacted = redact(f"{GHSA_ID} allows remote code execution.")
    assert GHSA_ID not in redacted.text
    assert redacted.removed == (GHSA_ID,)


def test_a_published_vector_never_reaches_the_member():
    # Showing the published score measures whether a model can copy one.
    redacted = redact(f"The vendor scores this {PUBLISHED} on release.")
    assert "AV:N" not in redacted.text
    assert redacted.removed == (PUBLISHED,)


def test_an_identifier_is_marked_rather_than_deleted():
    redacted = redact(f"{CVE_ID} allows remote code execution.")
    assert redacted.text == f"{IDENTIFIER_MARKER} allows remote code execution."


def test_a_published_vector_is_marked_rather_than_deleted():
    redacted = redact(f"Scored {PUBLISHED} by the vendor.")
    assert redacted.text == f"Scored {VECTOR_MARKER} by the vendor."


def test_every_mention_goes_not_only_the_first():
    redacted = redact(f"{CVE_ID} supersedes {CVE_ID}, and see also {GHSA_ID}.")
    assert CVE_ID not in redacted.text and GHSA_ID not in redacted.text
    assert redacted.removed == (CVE_ID, CVE_ID, GHSA_ID)


@pytest.mark.parametrize(
    "identifier",
    ["CVE-2021-4422", "CVE-2021-44228", "CVE-2021-1234567", "CVE-2021-12345678"],
)
def test_a_cve_id_goes_however_long_its_sequence_number_is(identifier):
    # The format is four digits or more, with no upper limit. A pattern that
    # guessed one would let a member see the id, which is the panel rule broken
    # at the one point this module exists to hold it.
    assert identifier not in redact(f"{identifier} allows code execution.").text


def test_a_ghsa_id_goes_whatever_shape_it_is():
    # The published format is three groups of four, but nothing this module can
    # see guarantees GitHub keeps issuing that shape.
    longer = "GHSA-abcde-fghij-klmno-pqrst"
    assert longer not in redact(f"{longer} allows code execution.").text


def test_the_word_ghsa_on_its_own_is_not_an_identifier():
    text = "The GHSA database lists this advisory."
    assert redact(text).text == text


def test_nothing_a_marker_leaves_behind_still_looks_like_an_identifier():
    # What the marker replaces the id with must not itself match: the guard in
    # `council.evidence` refuses text still carrying a CVE id, and a marker that
    # kept a matchable shape would trip it on text that was properly redacted.
    redacted = redact("CVE-2021-44228 and CVE-2021-12345678 are both fixed.")
    assert redact(redacted.text).removed == ()


def test_an_identifier_in_lower_case_is_still_an_identifier():
    redacted = redact("cve-2021-44228 allows remote code execution.")
    assert "44228" not in redacted.text


def test_an_advisory_with_nothing_to_hide_comes_back_untouched():
    redacted = redact(PLAIN)
    assert redacted.text == PLAIN
    assert redacted.removed == ()


def test_a_version_number_is_not_mistaken_for_an_identifier():
    # Fixed versions are the most useful thing an advisory says. Eating them
    # would cost a member evidence to buy nothing.
    text = "Fixed in 1.11.23, 2.1.11 and 2.2.4."
    assert redact(text).text == text


def test_an_advisory_with_no_text_is_refused_rather_than_prompted_with():
    with pytest.raises(ValueError, match="no advisory text"):
        redact("   ")


def test_something_that_is_not_text_is_refused_by_type():
    with pytest.raises(TypeError, match="must be text, not int"):
        redact(7)
