"""Guards on what the explainer is asked: the disagreement alone, the advisory redacted, pinned."""

from hashlib import sha256

import pytest

from council.explanation_prompt import (
    EXPLANATION_PROMPT_VERSION,
    ITEMS_FIELD,
    METRIC_FIELD,
    QUOTATION_FIELD,
    WHY_FIELD,
    build_explanation_prompt,
)
from council.ollama import PINNED_SEED, LocalModel, build_request
from council.prompt import build_prompt
from council_samples import QUOTABLE, RAW_ADVISORY

# Sources disagreeing on AV and A; every other metric they agree on is never named.
DISAGREEMENT = {"AV": {"nvd": "N", "ghsa": "L"}, "A": {"nvd": "H", "ghsa": "N", "redhat": "L"}}
AGREED = ("AC", "PR", "UI", "S", "C", "I")
PINNING = LocalModel(model="big:27b", context_tokens=8_192, host="http://127.0.0.1:11434")

# The wording, fingerprinted as the member prompt's is (`tests/council/test_prompt.py`).
EXPLANATION_FINGERPRINTS = {
    "sources-differ-1": "afad607c4cddf57cbf58b0541cf2fbc7590b4abc1fb2f438538fca42dcebce14",
}


def asked():
    """Build the explainer's prompt for the sample advisory and disagreement."""
    return build_explanation_prompt(RAW_ADVISORY, DISAGREEMENT)


def test_the_wording_has_not_moved_without_the_version_moving():
    assert EXPLANATION_PROMPT_VERSION in EXPLANATION_FINGERPRINTS, "bump the version, record it"
    prompt = asked()
    digest = sha256("\n".join([prompt.system, prompt.user]).encode("utf-8")).hexdigest()
    assert digest == EXPLANATION_FINGERPRINTS[EXPLANATION_PROMPT_VERSION]


def test_each_source_s_value_on_each_disputed_metric_is_given_and_nothing_else():
    system = asked().system
    assert "AV (Attack Vector): ghsa L, nvd N" in system
    assert "A (Availability): ghsa N, nvd H, redhat L" in system
    assert not any(f"{metric} (" in system for metric in AGREED)


def test_no_vector_and_no_identifier_reaches_the_explainer():
    prompt = asked()
    turns = prompt.system + prompt.user
    assert "CVSS:3.1" not in turns and "CVE-2021-44228" not in turns
    vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
    assert set(prompt.withheld) == {"CVE-2021-44228", vector}


def test_the_advisory_is_alone_in_its_turn_and_redacted_as_a_member_s_is():
    prompt = asked()
    assert prompt.advisory_shown == build_prompt("AV", RAW_ADVISORY).advisory_shown
    assert prompt.user.startswith(prompt.advisory_shown.strip())
    assert "Attack Vector" not in prompt.user and QUOTABLE in prompt.user


def test_the_reply_asked_for_is_one_item_per_disputed_metric_with_three_fields():
    user = asked().user
    assert f'"{ITEMS_FIELD}"' in user
    assert all(f'"{field}"' in user for field in (METRIC_FIELD, WHY_FIELD, QUOTATION_FIELD))
    assert "one of AV, A" in user


def test_the_explainer_is_asked_as_a_member_is_pinned_and_not_thinking():
    request = build_request(asked(), PINNING)
    options = request["options"]
    assert (options["temperature"], options["seed"], request["think"]) == (0, PINNED_SEED, False)
    assert (request["format"], options["num_ctx"]) == ("json", 8_192)


def test_an_explanation_too_long_for_the_window_is_refused_and_says_what_it_was():
    narrow = LocalModel(model="big:27b", context_tokens=64, host="http://127.0.0.1:11434")
    with pytest.raises(ValueError, match="This explanation prompt is roughly"):
        build_request(asked(), narrow)


@pytest.mark.parametrize(
    ("published", "said"),
    [
        ({}, "no disputed metric"),
        ({"AV": {"nvd": "N", "ghsa": "N"}}, "The sources agree on AV"),
        ({"AV": {"nvd": "N"}}, "The sources agree on AV"),
        ({"AV": {"nvd": "N", "ghsa": "Q"}}, "is not a value of"),
    ],
    ids=["nothing disputed", "one value", "one source", "a value the metric does not have"],
)
def test_a_prompt_with_no_disagreement_to_explain_is_refused(published, said):
    with pytest.raises(ValueError, match=said):
        build_explanation_prompt(RAW_ADVISORY, published)
