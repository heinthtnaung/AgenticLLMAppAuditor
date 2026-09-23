"""Guards on the page as a whole, and the one that matters: no figure the record lacks.

The central test renders **one record twice** and holds every number the page
states to the audit artefact for the same run. The project's rule is that every
score travels beside the vector it came from and re-derives; a page that can
show a figure the record does not carry breaks it the way a report that lies
does, so it is checkable here rather than trusted.

No test in this project renders a page in a browser. What these hold is what the
markup says -- never its tone, its contrast or its spacing.
"""

import re

from council_runs import INVENTED, OTHER_QUOTE, answering, council_ran
from organisation.approval import Approval, Decision
from organisation.risk import assess, per_source
from report.council_record import CouncilAssessment, CouncilNotAsked, CouncilWithoutVector
from report.html_report import as_html
from report.json_report import as_dictionary
from report.provenance import RunProvenance, UnknownAdvisoryDatabase
from report.record import Report, build_report
from report_samples import (
    CONFIDENTIALITY_ONLY,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    TOTAL_LOSS,
    VERSION_2_VECTOR,
    advisory,
    catalogue,
    component,
    finding,
    unidentified,
)
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer
from scoring.scale import MAXIMUM_CATEGORY_SCORE

DJANGO = component()
PYYAML = component("pyyaml", "5.1")
FLASK = component("flask", "1.0")

# A real council run, because only `SettledMetric` carries a basis and a
# hand-built ruling can quietly assert a shape no chairman emits.
DISSENTING = {"gemma4:latest": {"AC": answering("H", OTHER_QUOTE), "AV": answering("A", INVENTED)}}

APPROVAL = Approval("hein", Decision.APPROVED, "2026-09-22T09:00:00Z", "shipped")

# The classes a figure is written in. Everything else on the page is prose, a
# name, a vector or a date, and none of those is a number off the record.
FIGURE_CLASSES = frozenset(
    ("count", "spread", "value", "answer-value", "answer-value flag", "category-total",
     "answer-weight", "weighting")
)
ELEMENT = re.compile(r'<(span|p) class="([a-z- ]+)">([^<]*)</\1>')
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
SEPARATOR_SPAN = '<span class="separator">·</span>'
WEIGHTING = re.compile(r'<p class="weighting">([^<]*)</p>')

# `of 100` is the scale a category is written on, not a figure read off a record.
CATEGORY_SCALE = f"{MAXIMUM_CATEGORY_SCORE:g}"


def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


ANSWERS = all_answers({"EXP-1": Answer.YES, "BUS-1": Answer.YES, "THR-1": Answer.UNKNOWN})


def full_report() -> Report:
    """One record carrying every kind of thing the page has a shape for."""
    disagreeing = finding(DJANGO, vectors={"ghsa": LOW_CONFIDENTIALITY, "redhat": TOTAL_LOSS})
    agreeing = finding(PYYAML, advisory_id="CVE-2020-14343",
                       vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": CONFIDENTIALITY_ONLY})
    refused = finding(FLASK, advisory_id="CVE-2023-30861", vectors={"nvd": VERSION_2_VECTOR})
    raised = (disagreeing, agreeing, refused)
    council = (
        council_ran("CVE-2020-14343"),
        council_ran("CVE-2019-14234", **DISSENTING),
    )
    return build_report(
        PROVENANCE,
        catalogue(DJANGO, PYYAML, FLASK, unidentified=(unidentified(),)),
        raised,
        {"pkg:pypi/absent@1.0": (advisory(purl="pkg:pypi/absent@1.0"),)},
        council,
        [assess(one, ANSWERS, per_source(one)) for one in raised],
        APPROVAL,
        ("CVE-9999-0001",),
    )


def figures_on(page: str) -> set[str]:
    """Give every number the page states as a figure, by the classes figures are written in."""
    shown = ELEMENT.findall(page.replace(SEPARATOR_SPAN, " "))
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
    # The project's central rule, made checkable: every score on the page came
    # off the record beside the vector or the answer that produced it. A figure
    # here that the audit artefact does not carry is a second implementation.
    report = full_report()
    stated = figures_on(as_html(report))
    assert stated, "the page states no figure at all, so this guard checked nothing"
    assert stated - figures_in(as_dictionary(report)) == set()


def test_every_published_score_the_record_carries_reaches_the_page():
    report = full_report()
    published = {
        str(score["base_score"])
        for one in as_dictionary(report)["findings"]
        for score in one["scores"]
    }
    assert published
    assert published <= figures_on(as_html(report))


def test_every_organisation_score_the_record_carries_reaches_the_page():
    report = full_report()
    weighed = {
        str(one.score) for risk in report.risk.values() for one in risk.scores
    }
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
    carried = [str(one["weight"]) for one in weighed["category_weights"]]
    said = WEIGHTING.search(as_html(report)).group(1)
    assert NUMBER.findall(said) == carried


def test_the_page_fetches_nothing_because_a_scan_runs_offline():
    page = as_html(full_report())
    assert "<script" not in page
    assert "<link" not in page
    assert "http://" not in page and "https://" not in page


def test_the_page_is_one_document_a_browser_will_take():
    page = as_html(full_report())
    assert page.startswith("<!DOCTYPE html>\n<html lang=\"en\">")
    assert page.rstrip().endswith("</html>")
    assert '<meta name="viewport"' in page


def test_the_not_assessed_block_survives_even_on_a_full_record():
    # It is the last thing on the page and the first thing a layout would cut.
    page = as_html(full_report())
    assert "Not assessed" in page


def test_the_two_scales_are_named_before_a_reader_meets_either():
    page = as_html(full_report())
    legend = page.index("Organisation Risk Score")
    assert legend < page.index("Sources disagree")


def test_a_run_with_no_advisory_database_shouts_rather_than_looking_clean():
    unknown = UnknownAdvisoryDatabase("trivy said nothing")
    nothing = RunProvenance("fetched/vulnscout", "syft-under-test", "trivy-under-test", unknown)
    report = build_report(nothing, catalogue(DJANGO), (finding(DJANGO),), {})
    assert 'class="alarm">NO ADVISORY DATABASE DATE: trivy said nothing' in as_html(report)


# Every state the council record can be in. A new one that reaches a rendering
# as an `AttributeError` is the defect this closes: the type says a fact exists
# and the code that must read it does not know. Adding a fifth breaks this list
# before it breaks a run.
COUNCIL_STATES = (
    CouncilAssessment("CVE-SETTLED", TOTAL_LOSS, single_assessor=False),
    CouncilWithoutVector("CVE-OPEN", False, ("AV",), ()),
    CouncilNotAsked("CVE-PASSED", "no published source disagrees"),
)


def test_every_state_the_council_record_can_be_in_renders():
    raised = tuple(finding(DJANGO, advisory_id=one.advisory_id) for one in COUNCIL_STATES)
    report = build_report(PROVENANCE, catalogue(DJANGO), raised, {}, COUNCIL_STATES)
    page = as_html(report)
    assert [one.advisory_id for one in COUNCIL_STATES if one.advisory_id not in page] == []


def test_a_run_with_no_council_at_all_renders_and_names_the_absence():
    page = as_html(build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {}))
    assert "Council (" not in page
    assert "Council ruling" in page
