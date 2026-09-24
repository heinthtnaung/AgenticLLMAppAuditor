"""Guards on a member's quotation in the terminal: whole, marked, and re-flowed word for word.

On a contested metric the quotation is the disagreement, so the terminal shows it
whole and between typographic marks, re-flowed rather than shortened. Every record
here comes out of a real chairman, through `council_runs`.
"""

from council_runs import (
    ADVISORY, DISSENTING, INVENTED, LONG_QUOTE, OTHER_QUOTE, answering, council_ran,
)
from report.record import build_report
from report.text_council import council_block
from report.text_layout import PAGE_WIDTH
from report_samples import PROVENANCE, catalogue, component, finding

DJANGO = component()

# Longer than the page, so the terminal has to re-flow it to show it whole.
LONG_QUOTATION = (
    "An attacker who can reach the administrative endpoint may supply a crafted template "
    "fragment, which the renderer evaluates before any authorisation check runs"
)
# Both members quote the long sentence verbatim and reach different values, so AC
# is contested over it.
ARGUED_AT_LENGTH = {
    "qwen2.5:7b": {"AC": answering("H", LONG_QUOTATION)},
    "gemma4:latest": {"AC": answering("L", LONG_QUOTATION)},
}
# Neither quotation is in the advisory, so nothing settles AV and both stay on show.
BOTH_INVENTED = {
    "qwen2.5:7b": {"AV": answering("N", INVENTED)},
    "gemma4:latest": {"AV": answering("A", INVENTED)},
}


def block(*outcomes) -> str:
    """Render the council block of a report carrying these outcomes."""
    raised = tuple(finding(DJANGO, advisory_id=one.advisory_id) for one in outcomes)
    return council_block(build_report(PROVENANCE, catalogue(DJANGO), raised, {}, outcomes))


def contested_block() -> str:
    """Render an advisory a real council of two families left AV contested on."""
    return block(council_ran(**DISSENTING))


def folded(rendered: str) -> str:
    """Fold a rendering to one line, so a re-flowed quotation can be looked for whole."""
    return " ".join(rendered.split())


def test_a_quotation_is_shown_whole_because_it_is_the_disagreement():
    # On a contested metric the quotation is the entire reason two models
    # reached different values.
    rendered = folded(contested_block())
    assert LONG_QUOTE in rendered
    assert OTHER_QUOTE in rendered


def test_a_quotation_too_long_for_the_page_is_re_flowed_and_not_shortened():
    rendered = block(council_ran(details=f"{ADVISORY} {LONG_QUOTATION}.", **ARGUED_AT_LENGTH))
    assert LONG_QUOTATION in folded(rendered)
    assert "..." not in rendered
    assert max(len(line) for line in rendered.split("\n")) <= PAGE_WIDTH


def test_whether_a_quotation_verified_is_said_and_not_merely_that_one_was_offered():
    # `quoted` and `found in the advisory` are different facts, and the evidence
    # rule turns entirely on the difference. A verified quotation settles its
    # metric unless another verified one disagrees, so the two marks are shown
    # by two runs and never by one metric.
    assert "quotation found in the advisory" in contested_block()
    assert "quotation not found in the advisory" in block(council_ran(**BOTH_INVENTED))
