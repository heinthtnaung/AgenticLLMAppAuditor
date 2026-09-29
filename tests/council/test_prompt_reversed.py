"""Guards on the prompt with its options reversed: the same question, the list the other way."""

import re
from hashlib import sha256

import pytest

from council.definitions import definition_of
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION, build_prompt
from cvss.metrics import METRIC_ORDER
from council_samples import ADVISORY

# The reversed wording, fingerprinted as `test_prompt.py` fingerprints the other.
REVERSED_FINGERPRINT = "524ed7810f0dde0d744e4db05d868fba863457caec8ee4afd8bfcfeb50db23c0"


def fingerprint() -> str:
    """Fingerprint both turns of all eight reversed questions."""
    prompts = [build_prompt(metric, ADVISORY, reversed_options=True) for metric in METRIC_ORDER]
    turns = [one.system for one in prompts] + [one.user for one in prompts]
    return sha256("\n".join(turns).encode("utf-8")).hexdigest()


def test_the_reversed_wording_has_not_moved_without_its_version_moving():
    assert REVERSED_PROMPT_VERSION == "member-base-metric-3+reversed-1"
    assert fingerprint() == REVERSED_FINGERPRINT


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_every_option_is_listed_the_other_way_round_in_both_turns(metric):
    forward = list(definition_of(metric).value_meanings)
    asked = build_prompt(metric, ADVISORY, reversed_options=True)
    assert re.findall(r"^(\w+) = ", asked.system, flags=re.MULTILINE) == forward[::-1]
    listed = re.search(r'"value": "one of ([\w, ]+) --', asked.user).group(1).split(", ")
    assert listed == forward[::-1]


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_only_the_order_changes_and_the_version_says_so(metric):
    forward = build_prompt(metric, ADVISORY)
    asked = build_prompt(metric, ADVISORY, reversed_options=True)
    assert sorted(asked.system.splitlines()) == sorted(forward.system.splitlines())
    assert (asked.advisory_shown, asked.withheld) == (forward.advisory_shown, forward.withheld)
    assert (forward.version, asked.version) == (PROMPT_VERSION, REVERSED_PROMPT_VERSION)
