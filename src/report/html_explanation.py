"""Why the published sources differ, on the web page, beside the sources and never in a score.

One card per finding whose sources disagree, in the order the page lists them:
the model that explained it, then each disputed metric with what every source
gave, the model's `why` marked as the model's, and the quotation that was
checked, in full. A finding a model could not explain says why. A run that asked
no model has no section at all, and says so under Not assessed.

The sentences this shares with the terminal are `report.explanation_words`.
"""

from report.disagreement import most_contested_first, sources_disagree
from report.explanation_record import ExplainedMetric, SourcesExplained
from report.explanation_words import (
    CHECKED,
    HEADING,
    LEDE,
    MODEL_WRITTEN,
    explained_by,
    not_explained,
    sources_on,
)
from report.html_layout import listing, section, separated, tag, text
from report.record import Report


def explanation_section(report: Report) -> str:
    """Say why each disputed finding's sources differ, as a model wrote it, or why it cannot."""
    contested = [one for one in report.findings if sources_disagree(one)]
    ordered = most_contested_first(tuple(contested))
    asked = [one for one in ordered if one.advisory.advisory_id in report.explanations]
    if not asked:
        return ""
    cards = "".join(explanation_card(report, one) for one in asked)
    return section(f"{HEADING} ({len(asked)})", LEDE, cards)


def explanation_card(report: Report, finding) -> str:
    """Give one finding's explanation, or the reason it has none."""
    record = report.explanations[finding.advisory.advisory_id]
    named = tag("code", text(finding.advisory.advisory_id))
    if not isinstance(record, SourcesExplained):
        said = separated([named, text(not_explained(record))])
        return tag("article", tag("p", said, "explained-by"), "explanation")
    by = [text(one) for one in explained_by(record)]
    heading = tag("p", separated([named, *by]), "explained-by")
    items = listing([item_row(finding, one) for one in record.items], "explained")
    return tag("article", heading + items, "explanation")


def item_row(finding, item: ExplainedMetric) -> str:
    """Give one disputed metric: what each source gave, the model's words, the quotation whole."""
    given = [text(one) for one in sources_on(finding, item.metric)]
    sources = separated([tag("code", text(item.metric)), *given])
    why = tag("p", tag("span", text(MODEL_WRITTEN), "model-written") + text(f": {item.why}"), "why")
    quoted = tag("blockquote", text(item.evidence), "evidence")
    return tag("p", sources, "sources") + why + quoted + tag("span", text(CHECKED), "verified")
