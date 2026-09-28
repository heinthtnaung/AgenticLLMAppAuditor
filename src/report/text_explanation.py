"""Why the published sources differ, on the terminal page, beside the sources and never in a score.

One entry per finding whose sources disagree, in the order `SOURCES DISAGREE`
lists them: the model that explained it, then each disputed metric with what
every source gave, the model's `why` labelled as the model's, and the quotation
that was checked. A finding a model could not explain says why. A run that asked
no model has no block at all, and says so under `NOT ASSESSED`.

The sentences this shares with the web page are `report.explanation_words`.
"""

from itertools import chain

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
from report.record import Report
from report.text_layout import SOURCE_SEPARATOR, indented, section, wrapped
from report.text_metric import CLOSE_QUOTE, OPEN_QUOTE

FINDING_DEPTH = 1
METRIC_DEPTH = 2
PROSE_DEPTH = 3


def explanation_block(report: Report) -> str:
    """Say why each disputed finding's sources differ, as a model wrote it, or why it cannot."""
    asked = [one for one in disputed(report) if one.advisory.advisory_id in report.explanations]
    if not asked:
        return ""
    entries = chain.from_iterable(entry_lines(report, one) for one in asked)
    return section(f"{HEADING.upper()} ({len(asked)})", [*wrapped(LEDE, FINDING_DEPTH), *entries])


def disputed(report: Report) -> tuple:
    """Give the findings whose sources disagree, most contested first, as the sources are listed."""
    return most_contested_first(tuple(one for one in report.findings if sources_disagree(one)))


def entry_lines(report: Report, finding) -> list[str]:
    """Give one finding's explanation, or the reason it has none."""
    record = report.explanations[finding.advisory.advisory_id]
    named = finding.advisory.advisory_id
    if not isinstance(record, SourcesExplained):
        return wrapped(f"{named}  {not_explained(record)}", FINDING_DEPTH)
    heading = SOURCE_SEPARATOR.join(explained_by(record))
    items = chain.from_iterable(item_lines(finding, one) for one in record.items)
    return [*wrapped(f"{named}  {heading}", FINDING_DEPTH), *items]


def item_lines(finding, item: ExplainedMetric) -> list[str]:
    """Give one disputed metric: what each source gave, the model's words, and its quotation."""
    sources = SOURCE_SEPARATOR.join(sources_on(finding, item.metric))
    quoted = f"{OPEN_QUOTE}{' '.join(item.evidence.split())}{CLOSE_QUOTE}"
    return [
        indented(METRIC_DEPTH, f"{item.metric}  {sources}"),
        *wrapped(f"{MODEL_WRITTEN}: {item.why}", PROSE_DEPTH),
        *wrapped(f"{quoted}{SOURCE_SEPARATOR}{CHECKED}", PROSE_DEPTH),
    ]
