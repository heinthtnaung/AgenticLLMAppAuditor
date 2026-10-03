"""Guards that no figure on the page is one the record lacks, and every kept section survives.

The project's central rule is that every score travels beside the vector or answer
it came from and re-derives; a figure the record does not carry is a second sum.
The kept-section guards hold the parts the template has no place for -- Secrets and
the model digest -- and the alarms that must not read as a clean run.
"""

import re

from council_runs import council_states
from organisation.risk import FindingRisk
from report.html_report import as_html
from report.json_report import as_dictionary
from report.provenance import RunProvenance, UnknownAdvisoryDatabase
from report.record import build_report
from report_pages import DJANGO, full_report, report_with_models
from report_samples import PROVENANCE, catalogue, finding
from scoring.scale import MAXIMUM_CATEGORY_SCORE

FIGURE_CLASSES = frozenset(
    ("value", "answer-value", "answer-value flag", "category-total", "answer-weight", "weighting")
)
ELEMENT = re.compile(r'<(span|p) class="([a-z- ]+)">([^<]*)</\1>')
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
WEIGHTING = re.compile(r'<p class="weighting">([^<]*)</p>')
DOTSEP = '<span class="separator">·</span>'
CATEGORY_SCALE = f"{MAXIMUM_CATEGORY_SCORE:g}"


def figures_on(page: str) -> set[str]:
    """Give every number the page states as a figure, by the classes figures are written in."""
    shown = ELEMENT.findall(page.replace(DOTSEP, " "))
    said = " ".join(content for _, css_class, content in shown if css_class in FIGURE_CLASSES)
    return set(NUMBER.findall(said)) - {CATEGORY_SCALE}


def figures_in(record) -> set[str]:
    """Give every number the audit record carries, written the way the page writes one."""
    if isinstance(record, bool) or record is None:
        return set()
    if isinstance(record, (int, float)):
        return {str(record)}
    if isinstance(record, dict):
        return figures_in(list(record.values()))
    if isinstance(record, list):
        return set().union(set(), *(figures_in(one) for one in record))
    return set()


def test_the_page_states_no_figure_the_record_does_not_carry():
    report = full_report()
    stated = figures_on(as_html(report))
    assert stated, "the page states no figure at all, so this guard checked nothing"
    assert stated - figures_in(as_dictionary(report)) == set()


def published_scores(finding_record: dict) -> set[str]:
    """Give every published base score on one finding of the audit record."""
    return {str(score["base_score"]) for score in finding_record["scores"]}


def organisation_scores(risk: FindingRisk) -> set[str]:
    """Give every Organisation Risk Score weighed for one finding."""
    return {str(one.score) for one in risk.scores}


def test_every_published_score_the_record_carries_reaches_the_page():
    report = full_report()
    published = set().union(*map(published_scores, as_dictionary(report)["findings"]))
    assert published
    assert published <= figures_on(as_html(report))


def test_every_organisation_score_the_record_carries_reaches_the_page():
    report = full_report()
    weighed = set().union(*map(organisation_scores, report.risk.values()))
    assert weighed
    assert weighed <= figures_on(as_html(report))


def test_the_category_weighting_on_the_page_is_the_one_the_record_carries():
    # Membership alone is too weak for these: 0.25 and 0.2 are question weights
    # too, so a wrongly restated weighting could still name a figure the record
    # holds somewhere else. Ordered and exact.
    report = full_report()
    weighed = next(
        one["organisation_risk"]
        for one in as_dictionary(report)["findings"]
        if one["organisation_risk"]
    )
    carried = [str(weighed["scores"][0]["technical_weight"])]
    carried += [str(category["weight"]) for category in weighed["categories"].values()]
    said = WEIGHTING.search(as_html(report)).group(1)
    assert NUMBER.findall(said) == carried


def test_the_not_assessed_card_survives_even_on_a_full_record():
    assert "Not assessed" in as_html(full_report())


def test_the_two_scales_are_named_before_a_reader_meets_a_score_chip():
    page = as_html(full_report())
    callout = page.index("Two scores, never merged")
    assert callout < page.index('<span class="scale">cvss</span>')
    assert callout < page.index('<span class="scale">org</span>')


def test_the_secrets_section_is_kept_even_though_the_template_has_none():
    page = as_html(full_report())
    assert 'id="panel-secrets"' in page
    assert "config/settings.py:2" in page


def test_the_model_digest_line_lands_in_the_header_meta():
    page = as_html(report_with_models())
    assert '<p class="meta">models: qwen2.5:7b 845dbda0ea48' in page


def test_a_run_with_no_advisory_database_shouts_rather_than_looking_clean():
    unknown = UnknownAdvisoryDatabase("trivy said nothing")
    nothing = RunProvenance("fetched/vulnscout", "syft-under-test", "trivy-under-test", unknown)
    report = build_report(nothing, catalogue(DJANGO), (finding(DJANGO),), {})
    assert 'class="alarm">NO ADVISORY DATABASE DATE: trivy said nothing' in as_html(report)


def test_every_state_the_council_record_can_be_in_renders():
    states = council_states()
    raised = tuple(finding(DJANGO, advisory_id=one.advisory_id) for one in states)
    page = as_html(build_report(PROVENANCE, catalogue(DJANGO), raised, {}, states))
    assert [one.advisory_id for one in states if one.advisory_id not in page] == []


def test_a_run_with_no_council_at_all_renders_and_names_the_absence():
    page = as_html(build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {}))
    assert "No council ran on this audit." in page
    assert "Council ruling" in page
