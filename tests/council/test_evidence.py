"""Guards on the quotation check: what counts as appearing in the advisory, and what does not."""

import pytest

from council.evidence import is_quotation_from, normalise
from council_samples import ACROSS_A_LINE_BREAK, ADVISORY, NETWORK_QUOTATION, NOT_IN_THE_ADVISORY


def test_a_verbatim_quotation_verifies():
    assert is_quotation_from(NETWORK_QUOTATION, ADVISORY)


def test_the_whole_advisory_quotes_itself():
    assert is_quotation_from(ADVISORY, ADVISORY)


def test_text_the_advisory_does_not_contain_is_refused():
    assert not is_quotation_from(NOT_IN_THE_ADVISORY, ADVISORY)


def test_a_quotation_spanning_a_line_break_verifies():
    # Where a feed wrapped its lines is a layout accident, not part of what the
    # advisory says, so a model that reflows it has still quoted it.
    assert is_quotation_from(ACROSS_A_LINE_BREAK, ADVISORY)


@pytest.mark.parametrize(
    "quotation",
    [
        "  unauthenticated   remote    attacker  ",
        "unauthenticated\nremote\tattacker",
        "unauthenticated remote attacker",
    ],
    ids=["padded and doubled", "newline and tab", "non-breaking space"],
)
def test_whitespace_is_folded_rather_than_matched(quotation):
    assert is_quotation_from(quotation, ADVISORY)


def test_a_typographic_apostrophe_verifies_against_a_straight_one():
    assert is_quotation_from("the host’s filesystem", ADVISORY)


def test_a_straight_apostrophe_verifies_against_a_typographic_one():
    curly = "The host’s filesystem was read."
    assert is_quotation_from("the host's filesystem", curly.lower())


def test_curly_double_quotes_fold_to_straight_ones():
    assert is_quotation_from('he said “no”', 'He said "no" to it.'.lower())


def test_case_is_not_folded():
    # A verbatim quotation reproduces the case it saw. Folding case is not what
    # lets a paraphrase through, but it is the first step of loosening, and
    # nothing observed so far needs it.
    assert not is_quotation_from("UNAUTHENTICATED REMOTE ATTACKER", ADVISORY)


@pytest.mark.parametrize(
    "quotation",
    ["a crafted request the attacker sends", "an attacker who is unauthenticated"],
    ids=["reordered", "reworded"],
)
def test_a_paraphrase_is_refused(quotation):
    # Every fold this check applies preserves the exact sequence of words, and a
    # paraphrase changes it. That is what stops the rule being loosened into one.
    assert not is_quotation_from(quotation, ADVISORY)


def test_a_dropped_word_is_refused():
    assert not is_quotation_from("unauthenticated attacker", ADVISORY)


@pytest.mark.parametrize(
    "quotation", ["", "   ", "\n\t", ".", " -- ", "..."], ids=[
        "empty", "spaces", "newlines", "full stop", "dashes", "ellipsis"
    ],
)
def test_a_quotation_with_no_word_in_it_is_refused(quotation):
    # Punctuation alone appears in almost any advisory and would verify every
    # time while supporting nothing.
    assert not is_quotation_from(quotation, ADVISORY)


def test_an_advisory_with_no_text_is_refused_rather_than_failing_every_member():
    # Returning False would mark all n members unverified and read as n models
    # having failed, when what happened is that the finding carried no text.
    with pytest.raises(ValueError, match="no advisory text"):
        is_quotation_from(NETWORK_QUOTATION, "   ")


def test_an_advisory_that_is_not_text_is_refused():
    with pytest.raises(TypeError, match="An advisory must be text"):
        is_quotation_from(NETWORK_QUOTATION, None)


def test_normalising_leaves_the_words_alone():
    assert normalise("  the   host’s \n filesystem ") == "the host's filesystem"


# The panel rule keeps the CVE id from the member, so the text it read is the
# redacted one and that is what its quotation has to be checked against.
RAW_ADVISORY = "CVE-2021-44228 lets an unauthenticated remote attacker load a class."
REDACTED_ADVISORY = "[redacted] lets an unauthenticated remote attacker load a class."
SPANS_THE_REDACTION = "[redacted] lets an unauthenticated remote attacker"


def test_a_quotation_spanning_a_redaction_verifies_against_the_text_the_member_saw():
    assert is_quotation_from(SPANS_THE_REDACTION, REDACTED_ADVISORY)


def test_the_unredacted_advisory_is_refused_rather_than_quietly_failing():
    # Silently returning False would put the metric at unresolved, which reads in
    # the report as the advisory having genuinely said nothing -- a wrong finding
    # in front of a human, wearing the look of a council that worked.
    with pytest.raises(ValueError) as refusal:
        is_quotation_from(SPANS_THE_REDACTION, RAW_ADVISORY)
    assert "CVE-2021-44228" in str(refusal.value)
    assert "redacted text the member read" in str(refusal.value)


def test_a_quotation_clear_of_the_redaction_still_verifies():
    assert is_quotation_from("unauthenticated remote attacker load a class", REDACTED_ADVISORY)


def test_a_lowercase_cve_id_is_caught_too():
    # A member recognises cve-2021-44228 as readily as the upper-case spelling,
    # so the panel rule is broken either way.
    with pytest.raises(ValueError, match="cve-2021-44228"):
        is_quotation_from("lets an unauthenticated", RAW_ADVISORY.lower())


@pytest.mark.parametrize(
    "placeholder", ["[redacted]", "CVE-XXXX-XXXXX", "a vulnerability", "CVE-2021"],
    ids=["bracketed", "masked", "removed", "truncated"],
)
def test_text_with_the_id_really_gone_passes_through(placeholder):
    # The guard is invisible when redaction did its job; only a still-matchable
    # id trips it.
    redacted = RAW_ADVISORY.replace("CVE-2021-44228", placeholder)
    assert is_quotation_from("lets an unauthenticated remote attacker", redacted)


@pytest.mark.parametrize("digits", [4, 5, 7, 8, 11], ids=lambda n: f"{n} digits")
def test_a_cve_sequence_number_of_any_length_is_caught(digits):
    # A sequence number has four digits or more and no upper bound. A pattern
    # that guesses one lets past exactly the ids the panel rule exists to stop,
    # which is a bug redaction shipped with a seven-digit bound and this side
    # would have caught.
    advisory = f"CVE-2021-{'1' * digits} lets an unauthenticated remote attacker in."
    with pytest.raises(ValueError, match="still contains CVE-2021"):
        is_quotation_from("unauthenticated remote attacker", advisory)
