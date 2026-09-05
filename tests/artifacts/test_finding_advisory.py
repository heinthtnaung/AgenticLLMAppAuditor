"""The advisory fields belong to the advisory check alone, in both directions.

Split from test_finding.py the way the check's own tests are split from the
runner's: that file holds the evidence rules every finding obeys, this one the
four fields only `known_advisory` may set. The pairing is enforced in the
constructor, so a finding quoting a CVE under the wrong rule -- or the rule
claiming no CVE -- can never reach the artifact Phase 4 grades.
"""

import pytest

from advisory_fixtures import ADVISORY_ID, advisory_finding
from artifacts.finding import ADVISORY_RULE, sort_key
from findings_fixtures import RULE_ID, SURFACE_ID, static_finding

SECOND_ADVISORY = "CVE-2024-0002"


def test_an_advisory_id_under_another_rule_is_refused() -> None:
    """A CVE quoted by the permission check would be evidence no rule produced."""
    with pytest.raises(ValueError, match="come together"):
        static_finding(advisory_id=ADVISORY_ID)


def test_the_advisory_rule_without_an_advisory_id_is_refused() -> None:
    """The check's one claim is a named advisory, so a finding without one cites nothing."""
    with pytest.raises(ValueError, match="come together"):
        advisory_finding(advisory_id=None, advisory_fixed_version=None,
                         advisory_cvss_vector=None, advisory_cvss_source=None)


def test_a_severity_word_without_its_source_is_refused() -> None:
    """The severity is a quotation, so it may not appear without the source that attributes it."""
    with pytest.raises(ValueError, match="advisory_severity needs advisory_cvss_source"):
        advisory_finding(advisory_severity="HIGH", advisory_cvss_source=None)


def test_advisory_evidence_without_an_advisory_id_is_refused() -> None:
    """A fixed version or a vector with no advisory behind it is a dangling quotation."""
    with pytest.raises(ValueError, match="need an advisory_id"):
        static_finding(advisory_fixed_version="0.3.26")


def test_the_finding_id_gains_the_advisory_suffix() -> None:
    """Three advisories on one surface are three findings, so the id must carry the CVE."""
    finding = advisory_finding()
    assert finding.id == f"{SURFACE_ID}:{ADVISORY_RULE}:{ADVISORY_ID}"


def test_a_finding_without_an_advisory_keeps_the_two_part_id() -> None:
    """No advisory, no suffix: the id stays exactly what it was before version 4."""
    assert static_finding().id == f"{SURFACE_ID}:{RULE_ID}"


def test_two_same_surface_findings_sort_by_advisory_id() -> None:
    """The advisory id is the last tiebreak, so the same evidence always serialises alike."""
    second = advisory_finding(advisory_id=SECOND_ADVISORY)
    first = advisory_finding()
    assert sorted([second, first], key=sort_key) == [first, second]
