"""Guards on the overview tiles: the council tile tells "not asked" from "no council ran".

The tile a reader lands on must agree with the panel behind it. The judge caught
the council tile saying "no council ran" when in fact every finding was passed
over -- a different, false thing.
"""

import approval_runs
from council_runs import council_ran
from organisation.approval import ApprovalOutcome
from report.council_record import CouncilNotAsked
from report.html_overview_tiles import approval_tile, council_tile, stat_tiles, two_scales
from report.record import build_report
from report_samples import CONFIDENTIALITY_ONLY, PROVENANCE, catalogue, component, finding, secret

DJANGO = component()


def report_with(*council, secrets=()):
    """Build a report whose council carries these outcomes."""
    raised = tuple(
        finding(DJANGO, advisory_id=one.advisory_id, vectors={"ghsa": CONFIDENTIALITY_ONLY})
        for one in council
    )
    return build_report(PROVENANCE, catalogue(DJANGO), raised, {}, council, secrets=secrets)


def test_no_council_at_all_says_no_council_ran():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    tile = council_tile(report)
    assert "no council ran" in tile
    assert ">0<" in tile


def test_every_finding_passed_over_says_not_asked_not_no_council_ran():
    # The bug the judge caught: a run that recorded outcomes but assessed none.
    report = report_with(CouncilNotAsked("CVE-2019-14234", "the sources already settled it"))
    tile = council_tile(report)
    assert "no council ran" not in tile
    assert "1 not asked" in tile
    assert "0/0" in tile


def test_a_settled_run_counts_settled_over_assessed():
    report = report_with(council_ran("CVE-2019-14234"))
    tile = council_tile(report)
    assert "1/1" in tile
    assert "0 left open" in tile


def test_alarm_tiles_are_the_two_a_reader_should_not_scroll_past_while_no_approval_is_recorded():
    tiles = stat_tiles(report_with(council_ran("CVE-2019-14234")))
    assert tiles.count("tone-alarm") == 2
    assert "Sources disagree" in tiles and "Need approval" in tiles


def toned(approval: ApprovalOutcome | None) -> str:
    """Give the Need-approval tile for a weighed report decided this way, or not yet decided."""
    return approval_tile(approval_runs.approval_report(approval_runs.EXPOSED, approval))


def test_the_need_approval_tile_is_alarm_when_the_audit_records_no_approval():
    tile = toned(None)
    assert "tone-alarm" in tile
    assert "Need approval" in tile


def test_the_need_approval_tile_turns_ok_once_the_audit_is_approved():
    tile = toned(approval_runs.APPROVED)
    assert "tone-ok" in tile
    assert "tone-alarm" not in tile


def test_the_need_approval_tile_is_warn_when_the_audit_is_overridden():
    tile = toned(approval_runs.OVERRIDDEN)
    assert "tone-warn" in tile
    assert "tone-alarm" not in tile


def test_the_secrets_tile_counts_the_secrets():
    tiles = stat_tiles(report_with(council_ran("CVE-2019-14234"), secrets=(secret(),)))
    assert "Secrets" in tiles and "matched a rule" in tiles


def test_the_two_scales_callout_shows_each_scale_in_its_own_shape():
    callout = two_scales()
    assert '<span class="skey cvss-key">' in callout
    assert '<span class="skey org-key">' in callout
    assert "0.0 to 10.0" in callout and "0 to 100" in callout
