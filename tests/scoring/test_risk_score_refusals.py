"""Guards on what the Organisation Risk Score refuses: a category in the wrong slot, or none."""

import pytest

from scoring.technical import from_cvss_base_score
from risk_score_samples import NO_BUSINESS_IMPACT, NO_THREAT, NOTHING_EXPOSED, scored


@pytest.mark.parametrize(
    ("slot", "wrong"),
    [("exposure", NO_BUSINESS_IMPACT), ("business", NO_THREAT), ("threat", NOTHING_EXPOSED)],
)
def test_a_category_handed_to_the_wrong_slot_is_refused(slot, wrong):
    # Every slot is guarded on its own line, so every slot is tested on its own:
    # deleting one guard left the whole suite green.
    with pytest.raises(ValueError, match="was given where"):
        scored(from_cvss_base_score(8.0, "ghsa"), **{slot: wrong})


@pytest.mark.parametrize("slot", ["exposure", "business", "threat"])
@pytest.mark.parametrize("given", [None, 80.0, "80"], ids=["none", "float", "str"])
def test_a_category_that_is_no_category_score_is_refused(slot, given):
    with pytest.raises(TypeError, match="must be a CategoryScore"):
        scored(from_cvss_base_score(8.0, "ghsa"), **{slot: given})
