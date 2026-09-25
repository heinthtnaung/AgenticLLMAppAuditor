"""Guards on the variants: each changes the product's prompt in one way, under its own version."""

import re
from hashlib import sha256
from itertools import chain

import pytest

import eval_samples as samples
from council.definitions import definition_of
from council.ollama import LocalModel, build_request
from council.prompt import PROMPT_VERSION, MemberPrompt, build_prompt
from cvss.metrics import METRIC_ORDER
from council_eval.recording import request_digest
from council_eval.variants import (
    BASELINE,
    LIBRARY,
    LIBRARY_GUIDANCE,
    LIBRARY_LEAD,
    LIBRARY_REVERSED,
    REVERSED,
    VARIANTS,
    Variant,
    VariantMismatch,
    variant_asked,
    variant_prompt,
)

# The variants' words, fingerprinted as `tests/council/test_prompt.py` does the
# product's: wording that moves without its version moving fails here.
VARIANT_FINGERPRINTS = {
    "member-base-metric-3": "8968015d2da4ac497ce71786dd10659b9ba9a3b9dc970faf256ccc4bdc17073d",
    "member-base-metric-3+library-1":
        "803d5b7e7dfe8cd4e61c8683f453c7768098d42d7a5a7f4263a00b095d5e2334",
    "member-base-metric-3+reversed-1":
        "00d8305e46c26a9f08602dae431a9e65835147aca734b054c761416cb683b5fd",
    "member-base-metric-3+library-1+reversed-1":
        "1a9d513ca1f00a406abd02197905b2151ce64dd3ca9381f17cfb71bb675c77ea",
}


def asked(metric: str, variant: Variant) -> MemberPrompt:
    """Give one metric's prompt on the sample advisory, as a variant asks it."""
    return variant_prompt(build_prompt(metric, samples.ADVISORY_TEXT), variant)


def value_order(text: str) -> list[str]:
    """Read the order of the 'X = meaning' lines in a system turn."""
    return re.findall(r"^(\w+) = ", text, flags=re.MULTILINE)


def schema_order(text: str) -> list[str]:
    """Read the order of the values the reply schema lists."""
    return re.search(r'"value": "one of ([\w, ]+) --', text).group(1).split(", ")


def fingerprint(variant: Variant) -> str:
    """Fingerprint a variant's whole prompt: both turns of all eight questions."""
    prompts = [asked(metric, variant) for metric in METRIC_ORDER]
    turns = [one.system for one in prompts] + [one.user for one in prompts]
    return sha256("\n".join(turns).encode("utf-8")).hexdigest()


@pytest.mark.parametrize("variant", VARIANTS.values(), ids=VARIANTS)
def test_a_variant_s_wording_has_not_moved_without_its_version_moving(variant):
    assert fingerprint(variant) == VARIANT_FINGERPRINTS[variant.prompt_version]


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_the_baseline_asks_the_product_s_prompt_unchanged(metric):
    assert asked(metric, BASELINE) == build_prompt(metric, samples.ADVISORY_TEXT)


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_reversed_lists_every_option_the_other_way_round_in_both_turns(metric):
    forward = list(definition_of(metric).value_meanings)
    reversed_prompt = asked(metric, REVERSED)
    assert value_order(reversed_prompt.system) == forward[::-1]
    assert schema_order(reversed_prompt.user) == forward[::-1]


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_reversed_changes_nothing_but_the_order(metric):
    product = build_prompt(metric, samples.ADVISORY_TEXT)
    reversed_prompt = asked(metric, REVERSED)
    assert sorted(reversed_prompt.system.splitlines()) == sorted(product.system.splitlines())
    assert sorted(reversed_prompt.user) == sorted(product.user)


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_library_adds_the_guidance_after_the_values_and_nothing_else(metric):
    product = build_prompt(metric, samples.ADVISORY_TEXT)
    values = "\n".join(line for line in product.system.splitlines() if " = " in line)
    added = f"{values}\n\n{LIBRARY_LEAD}\n\n{LIBRARY_GUIDANCE}"
    library = asked(metric, LIBRARY)
    assert library.system == product.system.replace(values, added)
    assert library.user == product.user


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_both_is_the_reversal_and_the_guidance_together(metric):
    both = asked(metric, LIBRARY_REVERSED)
    assert value_order(both.system) == value_order(asked(metric, REVERSED).system)
    assert both.user == asked(metric, REVERSED).user
    assert LIBRARY_GUIDANCE in both.system


def value_names() -> set[str]:
    """Name every value of every metric in words: 'Network', 'Required', 'Unchanged' and so on."""
    groups = (definition_of(metric).value_meanings.values() for metric in METRIC_ORDER)
    return {meaning.split(".")[0].lower() for meaning in chain.from_iterable(groups)}


def test_the_guidance_names_no_metric_and_no_value():
    words = set(re.findall(r"[a-z]+", f"{LIBRARY_LEAD} {LIBRARY_GUIDANCE}".lower()))
    assert words.isdisjoint(value_names())
    assert not re.search(r"\b(AV|AC|PR|UI|S|C|I|A)\b", f"{LIBRARY_LEAD} {LIBRARY_GUIDANCE}")


def test_every_variant_asks_under_its_own_version_made_from_the_product_s():
    versions = [one.prompt_version for one in VARIANTS.values()]
    assert len(set(versions)) == len(VARIANTS)
    assert all(version.startswith(PROMPT_VERSION) for version in versions)
    assert BASELINE.prompt_version == PROMPT_VERSION


def test_every_variant_sends_a_request_of_its_own():
    pinning = LocalModel(model=samples.MODEL)
    sent = {request_digest(build_request(asked("S", one), pinning)) for one in VARIANTS.values()}
    assert len(sent) == len(VARIANTS)


@pytest.mark.parametrize("variant", VARIANTS.values(), ids=VARIANTS)
def test_a_variant_is_found_by_the_version_it_asks_under(variant):
    assert variant_asked(variant.prompt_version) == variant


def test_a_version_no_variant_asks_under_is_refused():
    with pytest.raises(ValueError, match="no variant asks under"):
        variant_asked("member-base-metric-2")


def test_a_variant_is_never_made_from_a_variant():
    with pytest.raises(VariantMismatch, match="a variant changes"):
        variant_prompt(asked("AV", LIBRARY), REVERSED)


def test_a_prompt_that_does_not_read_as_expected_stops_the_pass_rather_than_failing_a_member():
    # The runner records a ValueError as a member that failed; this must not be one.
    echoing = build_prompt("UI", f"{samples.ADVISORY_TEXT} It says one of N, R -- twice.")
    with pytest.raises(VariantMismatch, match="2 times, not once") as raised:
        variant_prompt(echoing, REVERSED)
    assert not isinstance(raised.value, ValueError)
