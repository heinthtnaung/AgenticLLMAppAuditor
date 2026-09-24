"""Guards on a vector that carries Temporal or Environmental metrics after its Base ones.

A source that ends its vector in `/E:H` has still published a Base assessment,
and the Base score does not depend on the Temporal metrics (CVSS v3.1
specification, sections 2 and 7). So those are read, checked as strictly as the
Base ones, and left out of the parsed vector; the Environmental ones refuse it.
"""

import pytest

from cvss.score import base_score
from cvss.vector import parse

BASE = "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N"
# Every Temporal metric and value v3.0 and v3.1 define, written out again rather
# than imported, so that the table and the specification check each other.
TEMPORAL_VALUES = [
    *(("E", value) for value in ("X", "H", "F", "P", "U")),
    *(("RL", value) for value in ("X", "U", "W", "T", "O")),
    *(("RC", value) for value in ("X", "C", "R", "U")),
]
FORBIDDEN = [
    ("E:Z", "Exploit Code Maturity"), ("RL:Z", "Remediation Level"), ("RC:H", "Report Confidence"),
]
ENVIRONMENTAL = [
    "CR:H", "IR:M", "AR:L", "MAV:N", "MAC:L", "MPR:N", "MUI:N", "MS:U", "MC:H", "MI:H", "MA:H",
]


@pytest.mark.parametrize("metric, value", TEMPORAL_VALUES)
def test_every_temporal_value_is_read_and_leaves_the_base_vector_as_it_was(metric, value):
    assert parse(f"{BASE}/{metric}:{value}") == parse(BASE)


def test_the_base_score_is_the_same_with_or_without_temporal_metrics():
    assert base_score(parse(f"{BASE}/E:H/RL:O/RC:C")) == base_score(parse(BASE))


def test_a_version_3_0_vector_with_temporal_metrics_is_read():
    assert parse("CVSS:3.0/AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N/E:P/RL:T/RC:R").version == "3.0"


def test_the_parsed_vector_holds_the_base_metrics_and_nothing_else():
    # The published string, which the record quotes, is where `/E:H` survives.
    parsed = parse(f"{BASE}/E:H")
    assert str(parsed) == BASE
    with pytest.raises(ValueError, match="not a CVSS Base metric"):
        parsed.value("E")


@pytest.mark.parametrize("suffix, named", FORBIDDEN)
def test_a_value_a_temporal_metric_forbids_still_refuses_the_vector(suffix, named):
    with pytest.raises(ValueError, match=f"is not a value of {named}"):
        parse(f"{BASE}/{suffix}")


def test_a_temporal_metric_given_twice_still_refuses_the_vector():
    with pytest.raises(ValueError, match=r"Exploit Code Maturity \(E\) is given twice"):
        parse(f"{BASE}/E:H/E:F")


def test_a_value_only_a_temporal_metric_allows_is_still_refused_on_a_base_one():
    with pytest.raises(ValueError, match="is not a value of Attack Vector"):
        parse("CVSS:3.1/AV:X/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N")


def test_temporal_metrics_alone_are_not_a_vector():
    with pytest.raises(ValueError, match="needs all eight metrics"):
        parse("CVSS:3.1/E:H/RL:O/RC:C")


@pytest.mark.parametrize("pair", ENVIRONMENTAL)
def test_an_environmental_metric_refuses_the_vector_by_name(pair):
    # Accepted: an Environmental metric describes one deployment, which is what
    # the organisation's answers are for, so a source publishing one is refused
    # whole. Reading them turns this red.
    with pytest.raises(ValueError, match="is a CVSS Environmental metric"):
        parse(f"{BASE}/{pair}")
