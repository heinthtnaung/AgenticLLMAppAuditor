"""Guards on the prompt: one metric, the advisory only, a quotation, and a version."""

import json
from hashlib import sha256

import pytest

from council.definitions import definition_of
from council.prompt import (
    PROMPT_VERSION,
    build_prompt,
    reply_schema,
    system_prompt,
    user_prompt,
)
from council.reply_format import NO_EVIDENCE_VALUE, REQUIRED_FIELDS
from council_samples import ADVISORY
from cvss.metrics import METRIC_ORDER

CVE_ID = "CVE-2021-44228"
GHSA_ID = "GHSA-jfh8-c2jp-5v3q"
PUBLISHED = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"

IDENTIFIED_ADVISORY = (
    f"{CVE_ID}: a remote attacker can send a crafted request to the management port. "
    f"The vendor scores it {PUBLISHED}."
)

# The longest advisory of 1,187 read off this machine's database snapshot --
# seven offline Trivy scans across PyPI, npm, Go, Rust, Debian and Alpine, and
# the repository under test. Nearly four times the longest of that repository's
# 18 advisories, at 4,585, which is why the number is named with the corpus that
# produced it: a worst case is only ever the worst so far.
LONGEST_ADVISORY_CHARACTERS = 17_893

# Not a rule of thumb. The pinned model counted that advisory's prompt at 4,897
# tokens, of which 421 is the prompt with the advisory taken out, putting the
# advisory itself at almost exactly four characters to the token.
CHARACTERS_PER_TOKEN = 4
PINNED_CONTEXT_TOKENS = 8_192

# The wording of the prompt, fingerprinted. A prompt whose words move without
# `PROMPT_VERSION` moving makes two runs incomparable while the record claims
# they were asked the same question, so that failure is caught here.
PROMPT_FINGERPRINTS = {
    "member-base-metric-1": "55d2111e3f955a9abf4b149d4eebf4c4193051039efe18a098c9b56ee2ce7e79",
    "member-base-metric-2": "875008fcec523ea7220a4b175ebfd657717b0e91a91cd386dd2b3ce91a38e71c",
    "member-base-metric-3": "a35e8636a9a4c3cfc84fcef8f08bd7d3066df3b5385397bbc9c57ec730c06c98",
}


def said(text: str) -> str:
    """Give a prompt's words without its line breaks, so a test is about wording."""
    return " ".join(text.split())


def fingerprint() -> str:
    """Fingerprint the whole prompt: both turns of all eight questions."""
    turns = [system_prompt(metric) for metric in METRIC_ORDER]
    turns += [user_prompt(metric, ADVISORY) for metric in METRIC_ORDER]
    return sha256("\n".join(turns).encode("utf-8")).hexdigest()


def test_the_wording_has_not_moved_without_the_version_moving():
    assert PROMPT_VERSION in PROMPT_FINGERPRINTS, "bump the version, then record its fingerprint"
    assert fingerprint() == PROMPT_FINGERPRINTS[PROMPT_VERSION]


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_a_member_is_asked_about_one_metric_and_told_what_it_means(metric):
    asked = build_prompt(metric, ADVISORY)
    assert definition_of(metric).measures in asked.system


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_every_value_of_that_metric_is_offered_with_its_meaning(metric):
    asked = build_prompt(metric, ADVISORY)
    meanings = definition_of(metric).value_meanings
    assert all(meaning in asked.system for meaning in meanings.values())


def test_the_advisory_is_the_evidence_the_member_is_given():
    assert "read arbitrary files" in build_prompt("AV", ADVISORY).user


def test_the_member_is_never_shown_the_cve_id():
    asked = build_prompt("AV", IDENTIFIED_ADVISORY)
    assert CVE_ID not in asked.user
    assert CVE_ID not in asked.advisory_shown


def test_the_member_is_never_shown_a_published_score():
    asked = build_prompt("S", IDENTIFIED_ADVISORY)
    assert "S:C" not in asked.advisory_shown
    assert PUBLISHED not in asked.user


def test_the_prompt_says_what_it_withheld_so_a_record_can_show_it():
    asked = build_prompt("AV", IDENTIFIED_ADVISORY)
    assert asked.withheld == (PUBLISHED, CVE_ID)


def test_what_it_withheld_is_the_identifiers_as_well_as_the_scores():
    # Both halves of the panel rule, in the one tuple. A record that showed only
    # the scores would leave no evidence that the ids were held back at all.
    asked = build_prompt("AV", f"{IDENTIFIED_ADVISORY} Tracked as {GHSA_ID}.")
    assert asked.withheld == (PUBLISHED, CVE_ID, GHSA_ID)


def test_the_text_the_member_saw_is_what_a_quotation_is_checked_against():
    # The member can only quote the redacted text, so `council.evidence` has to
    # be given this and not the original, or a true quotation fails the check.
    asked = build_prompt("AV", IDENTIFIED_ADVISORY)
    assert asked.advisory_shown in asked.user


def test_a_quotation_is_asked_for_and_inventing_one_is_named_as_worse():
    instruction = said(system_prompt("AV"))
    assert "word for word" in instruction
    assert "Inventing a quotation is worse than declining" in instruction


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_the_definitions_are_not_in_the_turn_the_advisory_is_in(metric):
    # The whole of version 3. Measured on 144 replies of version 1, where the
    # two sat together: 20 of the 24 quotations that failed verification were
    # the model quoting the definitions back as evidence. Saying "do not quote
    # these" made it worse; separating the turns is what worked.
    asked = build_prompt(metric, ADVISORY)
    meanings = definition_of(metric).value_meanings.values()
    assert not any(meaning in asked.user for meaning in meanings)
    assert "may not quote it" in said(asked.system)


def test_declining_is_offered_as_a_correct_answer():
    assert NO_EVIDENCE_VALUE in system_prompt("AV")
    assert "Declining is a correct answer" in said(system_prompt("AV"))


def test_the_member_is_told_it_will_not_see_the_others():
    assert "not see what the others answered" in said(system_prompt("AV"))


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_the_reply_shape_names_exactly_the_fields_the_parser_requires(metric):
    # The prompt and `council.reply` are held to each other here: a field asked
    # for and not read, or read and not asked for, is a member failing on shape.
    assert tuple(json.loads(reply_schema(metric))) == REQUIRED_FIELDS


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_the_reply_shape_names_only_that_metric_s_own_values(metric):
    offered = json.loads(reply_schema(metric))["value"]
    allowed = definition_of(metric).value_meanings
    assert all(f" {value}" in offered for value in allowed)


def test_the_prompt_version_rides_on_the_question():
    assert build_prompt("AV", ADVISORY).version == PROMPT_VERSION


def test_a_metric_nobody_defined_is_refused_before_a_model_is_asked():
    with pytest.raises(ValueError, match="is not a CVSS Base metric"):
        build_prompt("XX", ADVISORY)


def test_an_advisory_with_no_text_is_refused():
    with pytest.raises(ValueError, match="no advisory text"):
        build_prompt("AV", "")


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_the_worst_case_advisory_still_fits_the_pinned_context(metric):
    longest = "word " * (LONGEST_ADVISORY_CHARACTERS // len("word "))
    asked = build_prompt(metric, longest)
    tokens = (len(asked.system) + len(asked.user)) / CHARACTERS_PER_TOKEN
    assert tokens < PINNED_CONTEXT_TOKENS
