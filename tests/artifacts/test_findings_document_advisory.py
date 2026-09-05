"""Coverage's advisory pairing: a snapshot is pinned, an absence claims nothing.

Split from test_findings_document.py the way the finding's advisory rules are
split from test_finding.py. The pairing is the point: "scanned with Trivy" with
a null date behind it is an undated claim, and a pin under `not_ingested` is a
claim about a scan that never ran.
"""

import pytest

from artifacts.findings_document import ADVISORY_NOT_INGESTED, ADVISORY_SNAPSHOT, coverage
from cli_helpers import STUB_ADVISORY_PIN
from findings_fixtures import RULE_ID

PIN_FIELDS = tuple(STUB_ADVISORY_PIN)


def snapshot_coverage(**overrides) -> dict:
    """A fully pinned snapshot coverage block, with any field overridable."""
    return coverage(3, [RULE_ID], ADVISORY_SNAPSHOT, **{**STUB_ADVISORY_PIN, **overrides})


@pytest.mark.parametrize("missing", PIN_FIELDS)
def test_a_snapshot_missing_any_pin_field_is_refused(missing: str) -> None:
    """All three or nothing: a partial pin is a claim with no version behind it."""
    with pytest.raises(ValueError, match="a snapshot needs its generator name"):
        snapshot_coverage(**{missing: None})


@pytest.mark.parametrize("named", PIN_FIELDS)
def test_no_ingestion_with_any_pin_field_is_refused(named: str) -> None:
    """No advisory data was read, so nothing may pin it -- not even one field."""
    with pytest.raises(ValueError, match="nothing may pin it"):
        coverage(3, [RULE_ID], ADVISORY_NOT_INGESTED, **{named: STUB_ADVISORY_PIN[named]})


def test_an_unreached_count_without_advisory_data_is_refused() -> None:
    """The count is what a scan left unreached, so it needs a scan behind it."""
    with pytest.raises(ValueError, match="needs advisory data behind it"):
        coverage(3, [RULE_ID], ADVISORY_NOT_INGESTED, advisory_unreached_component_count=1)


def test_a_pinned_snapshot_carries_all_three_pin_fields() -> None:
    """The happy path: generator, version and database date all reach the artifact."""
    built = snapshot_coverage()
    assert built["advisory_data"] == ADVISORY_SNAPSHOT
    assert all(built[field] == STUB_ADVISORY_PIN[field] for field in PIN_FIELDS)


ITEMS = [{"purl": "pkg:npm/a@1", "advisories": [{"id": "CVE-1", "severity": "LOW"}]},
         {"purl": "pkg:npm/b@2", "advisories": [{"id": "CVE-2", "severity": None},
                                                {"id": "CVE-3", "severity": "HIGH"}]}]


def test_a_snapshot_carries_the_unreached_count_and_its_list() -> None:
    """The remainder is copied back unchanged, count and itemized list together."""
    built = snapshot_coverage(advisory_unreached_component_count=2,
                              advisory_unreached_components=ITEMS)
    assert built["advisory_unreached_component_count"] == 2
    assert built["advisory_unreached_components"] == ITEMS
    empty = snapshot_coverage(advisory_unreached_component_count=0,
                              advisory_unreached_components=[])
    assert empty["advisory_unreached_component_count"] == 0
    assert empty["advisory_unreached_components"] == []


def test_the_unreached_list_and_its_count_must_be_null_together() -> None:
    """One fact at two grains: a list without a count, or a count without a list, is refused."""
    with pytest.raises(ValueError, match="null together"):
        snapshot_coverage(advisory_unreached_component_count=1,
                          advisory_unreached_components=None)
    with pytest.raises(ValueError, match="null together"):
        snapshot_coverage(advisory_unreached_component_count=None,
                          advisory_unreached_components=ITEMS)


def test_the_unreached_list_length_must_equal_its_count() -> None:
    """The count is the length of the list; a disagreement is a producer bug, refused."""
    with pytest.raises(ValueError, match="count says"):
        snapshot_coverage(advisory_unreached_component_count=5,
                          advisory_unreached_components=ITEMS)


def test_no_ingestion_leaves_every_advisory_field_null() -> None:
    """The default state: no pin, no count, and the state named rather than implied."""
    built = coverage(3, [RULE_ID])
    assert built["advisory_data"] == ADVISORY_NOT_INGESTED
    assert all(built[field] is None for field in PIN_FIELDS)
    assert built["advisory_unreached_component_count"] is None
