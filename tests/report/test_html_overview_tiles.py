"""Guards on the overview tiles: the council tile tells "not asked" from "no council ran".

The tile a reader lands on must agree with the panel behind it. The judge caught
the council tile saying "no council ran" when in fact every finding was passed
over -- a different, false thing.
"""

from council_runs import council_ran
from report.council_record import CouncilNotAsked
from report.html_overview_tiles import council_tile, stat_tiles, two_scales
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


def test_the_alarm_tiles_are_the_two_a_reader_should_not_scroll_past():
    tiles = stat_tiles(report_with(council_ran("CVE-2019-14234")))
    assert tiles.count("tone-alarm") == 2
    assert "Sources disagree" in tiles and "Need approval" in tiles


def test_the_secrets_tile_counts_the_secrets():
    tiles = stat_tiles(report_with(council_ran("CVE-2019-14234"), secrets=(secret(),)))
    assert "Secrets" in tiles and "matched a rule" in tiles


def test_the_two_scales_callout_shows_each_scale_in_its_own_shape():
    callout = two_scales()
    assert '<span class="skey cvss-key">' in callout
    assert '<span class="skey org-key">' in callout
    assert "0.0 to 10.0" in callout and "0 to 100" in callout
