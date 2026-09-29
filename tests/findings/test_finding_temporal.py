"""Guards on a finding whose sources differ only in metrics the Base score does not read."""

from findings.finding import build_finding
from finding_samples import GHSA_VECTOR, advisory, component

# The same Base assessment as `GHSA_VECTOR`, but for Attack Complexity.
HARDER = GHSA_VECTOR.replace("AC:L", "AC:H")


def test_sources_that_differ_only_in_temporal_metrics_dispute_no_metric():
    # `E:H` against `E:U` is no disagreement about the assessment the score is
    # made of, so it must not file the finding among the disputes, nor put it
    # to the council.
    both = {"ghsa": f"{GHSA_VECTOR}/E:H", "nvd": f"{GHSA_VECTOR}/E:U/RL:O"}
    found = build_finding(component(), advisory(vectors=both))
    assert len(found.scores) == 2 and not found.unreadable
    assert found.disputed_metrics() == ()


def test_a_base_metric_still_disputes_beside_a_temporal_one():
    both = {"ghsa": f"{GHSA_VECTOR}/E:H", "nvd": HARDER}
    assert build_finding(component(), advisory(vectors=both)).disputed_metrics() == ("AC",)
