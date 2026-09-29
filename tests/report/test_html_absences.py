"""Guards on the Inventory tab and the two overview cards: the kinds of nothing, and a human act.

An advisory matching no component is a CVE that fell out of the join, which is a
report that looks clean and is not; a component nothing was published against is
only a component nobody published against; an artifact Syft could not identify
was never joinable at all. One number covering all three hides the middle one, so
these hold them apart. `Not assessed` is a card on the overview and never cut.
"""

from council_runs import passed_over_entirely
from full_runs import fully_assessed
from organisation.approval import Approval, Decision
from report.absences import (
    NOTHING_ABSENT, NOTHING_WAS_PUT_TO_IT, NO_COUNCIL_RUN, UNREAD_MANIFEST, Coverage,
)
from report.html_absences import (
    approval_card, inventory_panel, not_assessed_card,
)
from report.record import build_report
from report_samples import PROVENANCE, advisory, catalogue, component, finding, unidentified

DJANGO = component()
PYYAML = component("pyyaml", "5.1")
ABSENT = "pkg:pypi/absent@1.0"


def report_of(**overrides):
    """Build a report from whatever a test is about."""
    fields = {
        "findings": (finding(DJANGO),),
        "advisories_by_purl": {},
        "catalogue": catalogue(DJANGO, PYYAML),
    }
    fields.update(overrides)
    return build_report(
        PROVENANCE,
        fields["catalogue"],
        fields["findings"],
        fields["advisories_by_purl"],
        fields.get("council", ()),
        (),
        fields.get("approval"),
        fields.get("overridden", ()),
    )


def test_the_three_kinds_of_nothing_are_counted_apart():
    report = report_of(advisories_by_purl={ABSENT: (advisory(purl=ABSENT),)})
    page = inventory_panel(report)
    assert "Components with no advisory (1)" in page
    assert "1 advisories matched no component" in page


def test_the_components_list_shows_the_component_and_is_searchable():
    page = inventory_panel(report_of())
    assert 'data-filter-for="purl-list"' in page
    assert 'id="purl-list"' in page
    assert PYYAML.purl in page


def test_an_advisory_matching_no_component_can_be_opened_to_check_it():
    page = inventory_panel(report_of(advisories_by_purl={ABSENT: (advisory(purl=ABSENT),)}))
    assert "<details>" in page
    assert ABSENT in page


def test_an_override_that_matched_no_finding_is_named_rather_than_silent():
    page = inventory_panel(report_of(overridden=("CVE-9999-0001",)))
    assert "1 answer override matched no finding: CVE-9999-0001" in page


def test_an_artifact_that_could_never_be_joined_is_catalogued_not_dropped():
    named = catalogue(DJANGO, PYYAML, unidentified=(unidentified(),))
    page = inventory_panel(report_of(catalogue=named))
    assert "Could not be identified (1)" in page
    assert "./local-action" in page
    assert "github-action" in page


def test_a_run_with_nothing_unidentified_shows_no_group_for_it():
    assert "Could not be identified" not in inventory_panel(report_of())


def test_an_approval_card_names_who_decided_what_and_when():
    decided = Approval("hein", Decision.OVERRIDDEN, "2026-09-22T09:00:00Z", "accepted the risk")
    page = approval_card(report_of(approval=decided))
    assert "overridden by hein at 2026-09-22T09:00:00Z" in page
    assert "accepted the risk" in page


def test_nobody_having_approved_is_said_on_the_card_and_the_absence():
    assert "no approval recorded" in approval_card(report_of())
    assert "nobody has approved or overridden this audit" in not_assessed_card(report_of())


def test_what_the_run_did_not_assess_is_named_with_the_reason_it_did_not():
    page = not_assessed_card(report_of())
    assert "Organisation Risk Score" in page
    assert "no organisation answers were supplied" in page
    assert "Council ruling" in page


def test_an_absence_puts_what_is_missing_and_why_on_their_own_lines():
    page = not_assessed_card(report_of())
    assert '<span class="absence-what">Council ruling</span>' in page
    assert '<span class="absence-why">' in page


def test_a_council_put_to_no_finding_is_told_apart_from_no_council_at_all():
    passed_over = not_assessed_card(report_of(council=passed_over_entirely()))
    assert NOTHING_WAS_PUT_TO_IT in passed_over
    assert NO_COUNCIL_RUN not in passed_over
    assert NO_COUNCIL_RUN in not_assessed_card(report_of())


def test_a_run_that_left_nothing_out_says_so_on_the_card():
    page = not_assessed_card(fully_assessed())
    assert '<p class="eyebrow">Not assessed</p>' in page
    assert f'<p class="note">{NOTHING_ABSENT}</p>' in page
    assert '<ul class="absences">' not in page


def test_a_run_that_left_something_out_does_not_say_nothing_was():
    assert NOTHING_ABSENT not in not_assessed_card(report_of())


def test_a_manifest_nothing_was_read_from_is_named_with_why():
    page = not_assessed_card(fully_assessed(Coverage(unread_manifests=("package.json",))))
    assert '<span class="absence-what">package.json</span>' in page
    assert UNREAD_MANIFEST in page
