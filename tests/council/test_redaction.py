"""Guards on what a member must not see: the identifiers and the published scores."""

import pytest

from council.redaction import IDENTIFIER_MARKER, VECTOR_MARKER, redact

CVE_ID = "CVE-2021-44228"
GHSA_ID = "GHSA-jfh8-c2jp-5v3q"
PUBLISHED = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
BARE = "AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
BARE_V2 = "AV:N/AC:L/Au:N/C:P/I:P/A:P"
BARE_V4 = "AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
# Read by the parser now, so its Temporal tail has to go with it.
TEMPORAL = "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N/E:H/RL:O/RC:C"
BARE_TEMPORAL = "AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N/E:H"

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


@pytest.mark.parametrize("vector", [PUBLISHED, TEMPORAL])
def test_a_published_vector_never_reaches_the_member(vector):
    # Showing the published score measures whether a model can copy one, and no
    # `/E:H` fragment of it is left behind either.
    redacted = redact(f"The vendor scores this {vector} on release.")
    assert redacted.text == f"The vendor scores this {VECTOR_MARKER} on release."
    assert redacted.removed == (vector,)


@pytest.mark.parametrize("vector", [BARE, BARE_V2, BARE_V4, BARE_TEMPORAL])
def test_a_vector_written_without_its_prefix_is_the_same_published_score(vector):
    # The sharpest form of the leak: a member asked for Attack Vector, handed
    # `AV:N` in the text it is meant to reason from. The prefix is typography.
    redacted = redact(f"The vendor scores this {vector} on release.")
    assert "AV:N" not in redacted.text
    assert redacted.removed == (vector,)


def test_part_of_a_vector_is_still_part_of_a_published_score():
    redacted = redact("The published metrics begin AV:N/AC:L for this flaw.")
    assert redacted.removed == ("AV:N/AC:L",)


def test_a_prefixed_vector_is_recorded_once_and_not_twice():
    # Two patterns can now match the same characters. The bare one runs second,
    # by which point the prefixed one has already replaced them, so a record of
    # what was withheld stays a count of vectors rather than of patterns.
    assert redact(f"Scored {PUBLISHED}.").removed == (PUBLISHED,)


@pytest.mark.parametrize(
    "text",
    [
        "See http://user:p/path:x for the report.",
        "The preview renders at 16:9/4:3 in the console.",
        "Replace the DSA-1024 key with an RSA-2048 one.",
        "Fixed in 1.11.23, 2.1.11 and 2.2.4.",
    ],
)
def test_text_that_only_looks_like_a_vector_is_left_alone(text):
    # Measured over 1,187 advisories from seven Trivy scans: the bare pattern
    # fires on one, and that one really does carry a vector. Requiring a named
    # CVSS metric to open the run is what buys that -- anchored on any
    # `word:letter` these four would all go.
    assert redact(text).text == text


def test_an_identifier_is_marked_rather_than_deleted():
    redacted = redact(f"{CVE_ID} allows remote code execution.")
    assert redacted.text == f"{IDENTIFIER_MARKER} allows remote code execution."


def test_a_published_vector_is_marked_rather_than_deleted():
    redacted = redact(f"Scored {PUBLISHED} by the vendor.")
    assert redacted.text == f"Scored {VECTOR_MARKER} by the vendor."


def test_what_was_withheld_is_logged_in_the_order_the_patterns_run():
    # Not the order the strings stood in the advisory. A reader taking `removed`
    # for a reading order, or for a set, is reading it wrong, so the docstring
    # says which it is and this holds it to that.
    redacted = redact(f"{CVE_ID} is scored {PUBLISHED} and tracked as {GHSA_ID}.")
    assert redacted.removed == (PUBLISHED, CVE_ID, GHSA_ID)


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


# The sentence the module docstring quotes, from `GHSA-pw6j-qg29-8w7f` -- the
# one advisory of 1,187 that carries a prose score. Kept verbatim so the gap
# below is the real one and not a constructed one.
TORNADO = (
    f"Proposed CVSS 3.1:\n`{PUBLISHED}` (5.9, medium); attack complexity is\n"
    "High because exploitation depends on the application using differing "
    "per-request options on a shared client."
)


def test_a_score_written_as_prose_is_a_gap_this_module_knowingly_leaves_open():
    # The closable half. A pattern keyed on the severity word beside the number
    # would fire once in 1,187 and eat nothing -- and it is still not written,
    # for the reason the next test holds.
    assert "(5.9, medium)" in redact(TORNADO).text


def test_a_metric_value_written_in_words_is_the_half_no_pattern_reaches():
    # Why the gap above stays open rather than half closing. `attack complexity
    # is High` is the published AC value, in the same clause, and it is the
    # metric a member asked about AC has to decide. Nothing catches it that does
    # not also eat the advisory's reasoning. Withholding the number while this
    # stands would make the guarantee wrong in the one case anyone can show.
    assert "attack complexity is\nHigh" in redact(TORNADO).text


def test_an_identifier_in_another_namespace_is_a_gap_this_module_leaves_open():
    # SNYK once in 1,187 advisories, in a reference URL, and no PYSEC, RUSTSEC,
    # OSV, DSA, USN or RHSA at all. A namespace list would be several live
    # English acronyms for one occurrence, so the docstring names the gap
    # instead. Re-measure against a database that indexes those namespaces.
    text = "See https://snyk.io/vuln/SNYK-JS-ANGULAR-570058 for the advisory."
    assert redact(text).text == text


def test_an_advisory_with_no_text_is_refused_rather_than_prompted_with():
    with pytest.raises(ValueError, match="no advisory text"):
        redact("   ")


def test_something_that_is_not_text_is_refused_by_type():
    with pytest.raises(TypeError, match="must be text, not int"):
        redact(7)
