"""Why the published sources differ, on the disagreement card, beside them and never in a score.

Embedded in each contested finding's card rather than on a tab of its own: the
explanation answers the question that card raises, so it belongs where the reader
is asking it. Per disputed metric it shows what each source read, the model's
`why` marked as the model's, and the quotation that was checked, in full. A
finding a model could not explain says why. A run that asked no model has no block
at all, and says so under Not assessed.

The sentences this shares with the terminal are `report.explanation_words`.
"""

from report.explanation_record import ExplainedMetric, SourcesExplained, SourcesNotExplained
from report.explanation_words import (
    CHECKED,
    HEADING,
    MODEL_WRITTEN,
    explained_by,
    not_explained,
    sources_on,
)
from report.html_layout import separated, tag, text

CHECK_OK = f'<span aria-hidden="true">&check;</span> {CHECKED}'


def why_block(report, finding) -> str:
    """Give one contested finding's why-the-sources-differ block, or nothing where there is none.

    Called only for a contested finding, so an agreeing card never carries one.
    """
    record = report.explanations.get(finding.advisory.advisory_id)
    if record is None:
        return ""
    if not isinstance(record, SourcesExplained):
        return wrap(not_explained_line(record))
    items = "".join(item_block(finding, one) for one in record.items)
    return wrap(why_title(record) + items)


def wrap(body: str) -> str:
    """Wrap the explanation in the block the stylesheet sets off from the card above it."""
    return tag("div", body, "why")


def why_title(record: SourcesExplained) -> str:
    """Head the block, naming the model that wrote it and any item it did not keep."""
    by = separated([text(one) for one in explained_by(record)])
    return tag("div", tag("h4", text(HEADING)) + tag("span", by, "muted small"), "why-title")


def not_explained_line(record: SourcesNotExplained) -> str:
    """Say a finding's sources were not explained, and why."""
    return tag("div", tag("p", text(not_explained(record)), "fine"), "why-title")


def item_block(finding, item: ExplainedMetric) -> str:
    """Give one disputed metric: what each source read, the model's words, the quotation whole."""
    head = tag("div", metric_code(item.metric) + readings(finding, item.metric), "why-head")
    prose = tag("span", text(MODEL_WRITTEN), "tag tag-warn") + " " + text(item.why)
    quoted = tag("blockquote", text(item.evidence), "evidence")
    checked = tag("span", CHECK_OK, "check ok")
    return tag("div", head + tag("p", prose, "why-text") + quoted + checked, "why-item")


def metric_code(metric: str) -> str:
    """Name the disputed metric by its CVSS code, the way the vector writes it."""
    return tag("abbr", text(metric), "mcode")


def readings(finding, metric: str) -> str:
    """Show what each source read for one metric, in source-name order."""
    return tag("span", "".join(reading(one) for one in sources_on(finding, metric)), "readings")


def reading(said: str) -> str:
    """Give one source's reading of a metric: the source, then the value it published."""
    source, _, value = said.partition(" ")
    return tag("span", tag("span", text(source), "src") + tag("b", text(value)), "reading")
