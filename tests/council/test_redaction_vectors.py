"""Guards on what a member must not see: the published scores, in any spelling but words."""

import pytest

from council.redaction import VECTOR_MARKER, redact

from redaction_samples import PUBLISHED

BARE = "AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
BARE_V2 = "AV:N/AC:L/Au:N/C:P/I:P/A:P"
BARE_V4 = "AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
# Read by the parser now, so its Temporal tail has to go with it.
TEMPORAL = "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N/E:H/RL:O/RC:C"
BARE_TEMPORAL = "AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N/E:H"


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


def test_a_published_vector_is_marked_rather_than_deleted():
    redacted = redact(f"Scored {PUBLISHED} by the vendor.")
    assert redacted.text == f"Scored {VECTOR_MARKER} by the vendor."


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
