"""The sentences both renderings of an explanation say, in one place so the two cannot drift.

**What a model wrote is labelled as that, every time.** The `why` is the
model's own prose and nothing checked it; only the quotation beside it was held
to the advisory. A reader who takes the prose for a finding of this tool has
been misled, so the label sits on the prose itself, not in a legend.
"""

from report.council_words import VERIFIED, counted
from report.explanation_record import SourcesExplained, SourcesNotExplained

HEADING = "Why the sources differ"
LEDE = (
    "Written by a model from the advisory text, for each metric the published sources read "
    "differently. Only each quotation is checked: an item is kept where its quotation is in the "
    "advisory, one per disputed metric. The explanation beside it is the model's own words, and "
    "no score or ruling is computed from it."
)
MODEL_WRITTEN = "model-written, not checked"
EXPLAINED_BY = "explained by"
NOT_EXPLAINED = "not explained"
DROPPED = "not kept"
# Every item kept carries a quotation found in the advisory; nothing else is kept.
CHECKED = VERIFIED


def explained_by(record: SourcesExplained) -> list[str]:
    """Say which model explained a finding, and how many of its items were not kept."""
    named = [f"{EXPLAINED_BY} {record.model}"]
    if not record.dropped:
        return named
    return [*named, f"{counted(record.dropped, 'item')} {DROPPED}"]


def not_explained(record: SourcesNotExplained) -> str:
    """Say that a finding was not explained, and why."""
    return f"{NOT_EXPLAINED}: {record.because}"


def sources_on(finding, metric: str) -> list[str]:
    """Give what each readable source published for one metric, in source-name order."""
    return [f"{score.source} {score.parsed_vector.metrics[metric]}" for score in finding.scores]
