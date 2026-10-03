"""Council records in which two members quote the same words and read different values.

As `council_runs` does: a roster, the real runner, the real chairman and the
real conversion in `cli.council_detail`, and nothing that opens a socket. On AV
Qwen quotes the advisory's first sentence and reads N, and Gemma quotes the
start of that sentence and reads A. Its twin reads the same values from two
different sentences, so only the flag tells the two apart.
"""

from dataclasses import replace

from council_runs import LONG_QUOTE, OTHER_QUOTE, QUOTED, answering, council_ran
from organisation.risk import assess, per_source
from report.council_record import CouncilWithoutVector
from report.record import Report, build_report
from report_pages import ANSWERS, APPROVAL
from report_samples import PROVENANCE, catalogue, component, finding

SAME_WORDS = {
    "qwen2.5:7b": {"AV": answering("N", LONG_QUOTE)},
    "gemma4:latest": {"AV": answering("A", QUOTED)},
}
APART = {
    "qwen2.5:7b": {"AV": answering("N", LONG_QUOTE)},
    "gemma4:latest": {"AV": answering("A", OTHER_QUOTE)},
}


def same_words(advisory_id: str = "CVE-SAME-WORDS") -> CouncilWithoutVector:
    """Give a real record whose AV two members read apart from the same words."""
    return council_ran(advisory_id=advisory_id, **SAME_WORDS)


def apart(advisory_id: str = "CVE-APART") -> CouncilWithoutVector:
    """Give a real record whose AV two members read apart from two different sentences."""
    return council_ran(advisory_id=advisory_id, **APART)


def unflagged(outcome: CouncilWithoutVector) -> CouncilWithoutVector:
    """Give the same record with every same-evidence flag taken down and nothing else changed."""
    rulings = tuple(replace(one, same_evidence_different_reading=False) for one in outcome.rulings)
    return replace(outcome, rulings=rulings)


def av_of(outcome: CouncilWithoutVector):
    """Give a record's ruling on AV."""
    return next(one for one in outcome.rulings if one.metric == "AV")


def report_of(outcome: CouncilWithoutVector) -> Report:
    """Put one council record in a scored and approved report of its one finding."""
    django = component()
    one = finding(django, advisory_id=outcome.advisory_id)
    risk = [assess(one, ANSWERS, per_source(one))]
    return build_report(PROVENANCE, catalogue(django), (one,), {}, (outcome,), risk, APPROVAL)
