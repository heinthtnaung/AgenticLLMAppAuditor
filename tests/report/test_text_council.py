"""Guards on the council in a terminal: the metrics a reader must decide, and no less.

`docs/COUNCIL.md` keeps each member's answer and evidence per assessment, and the
terminal is the rendering most runs produce. So these hold it to the same facts
the web page shows: the chairman's basis, the quotation whole, whether that
quotation **verified**, and a run one member answered marked as one. Settled
metrics are counted by their basis rather than printed, because a metric the
chairman settled by overruling a dissenter reads nothing like one nobody argued
about.

**Every assessed record here comes out of a real chairman**, through
`council_runs`. A record filled in by hand can hold a shape no chairman emits, and
a test over it reports coverage of a path that never runs. A finding passed over
is built as `cli.council_run.passed_over` builds one, from its own reasons.
"""

from cli.council_run import NO_TEXT_TO_READ, SOURCES_AGREE
from council_runs import (
    ADVISORY, AGREED, ALONE, DECLINED_AND_GUESSED, DISSENTING, EVIDENCE, INVENTED, LONG_QUOTE,
    OTHER_QUOTE, UNPARSEABLE, UNTAGGED, answering, council_ran, declining, fell_back,
)
from report.council_record import CouncilNotAsked
from report.council_words import SINGLE_ASSESSOR
from report.record import build_report
from report.text_council import PAGE_WIDTH, council_block
from report_samples import PROVENANCE, TOTAL_LOSS, catalogue, component, finding

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


def test_a_run_with_no_council_shows_nothing():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert council_block(report) == ""


def test_a_contested_metric_shows_every_member_with_its_evidence():
    # The case the project exists for: two families, one advisory, different
    # values, each with a quotation. A count cannot express it, and a human
    # exercising an override needs to see who said what.
    rendered = contested_block()
    assert "AV  ·  contested  ·  2 members" in rendered
    assert "qwen2.5:7b (qwen2.5)  N  ·  high confidence" in rendered
    assert "gemma4:latest (gemma4)  A  ·  high confidence" in rendered


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


def test_a_metric_settled_over_a_dissent_is_told_apart_from_one_nobody_argued_about():
    # The basis is the answer to "why did this member win", and a bare `settled`
    # never says that the chairman had to overrule anybody.
    rendered = contested_block()
    assert "7 metrics settled" in rendered
    assert f"6  {AGREED}" in rendered
    assert f"1  {EVIDENCE}" in rendered


def test_the_settled_metrics_are_counted_rather_than_printed():
    # Eight metrics by n members for every finding is more page than anyone
    # reads, and most of it is agreement. AC was settled over a dissent and is
    # still only counted.
    rendered = contested_block()
    assert "AC  ·" not in rendered
    assert "PR  ·" not in rendered


def test_the_chairman_says_what_it_decided_on_a_metric_it_could_not_settle():
    assert "chairman: N  ·  fell back to ghsa" in block(fell_back())


def test_a_single_assessor_run_says_so_so_nobody_reads_a_council_into_it():
    # `docs/COUNCIL.md`: the record marks the run single-assessor, so no reader
    # takes council-grade confidence from one model.
    lone = council_ran(models=ALONE, **{"qwen2.5:7b": {"AC": declining()}})
    assert SINGLE_ASSESSOR in block(lone)


def test_a_settled_council_is_marked_single_assessor_too_when_one_member_ran():
    rendered = block(council_ran(models=ALONE))
    assert SINGLE_ASSESSOR in rendered
    # The vector `council_runs.LEGAL` answers, one value per metric.
    assert TOTAL_LOSS in rendered


def test_a_council_of_more_than_one_is_not_marked_single_assessor():
    assert SINGLE_ASSESSOR not in contested_block()


def test_a_member_whose_name_is_its_family_is_not_written_twice():
    unverified = {"gemma4": {"AC": answering("L", INVENTED)}}
    rendered = block(council_ran(models=UNTAGGED, **unverified))
    assert "gemma4 (gemma4)" not in rendered
    assert "gemma4  L" in rendered


def test_a_member_that_declined_is_told_apart_from_one_that_guessed():
    rendered = block(council_ran(**DECLINED_AND_GUESSED))
    assert "qwen2.5:7b (qwen2.5)  declined" in rendered
    assert "guessed R with nothing quoted" in rendered


def test_a_member_whose_call_failed_is_named_and_says_why_on_the_page():
    failed = [line for line in block(council_ran(**UNPARSEABLE)).split("\n") if "failed: " in line]
    assert len(failed) == 1
    assert "gemma4:latest (gemma4)  failed: " in failed[0]
    assert "()" not in failed[0]
    assert "'NONSENSE' is not a value of Attack Vector" in failed[0]


def test_a_council_that_settled_nothing_says_what_stopped_it():
    rendered = contested_block()
    assert "no vector" in rendered
    assert "could not settle AV" in rendered


def test_a_finding_the_council_was_not_put_to_is_named_with_the_reason():
    # A scoped run that left them out would say no council had run on them,
    # which is a different and false thing.
    rendered = block(
        council_ran(**DISSENTING),
        CouncilNotAsked("CVE-2", SOURCES_AGREE),
        CouncilNotAsked("CVE-3", SOURCES_AGREE),
    )
    assert "2 findings not asked" in rendered
    assert SOURCES_AGREE in rendered
    assert "CVE-2, CVE-3" in rendered


def test_the_reasons_a_finding_was_passed_over_are_kept_apart():
    rendered = block(
        CouncilNotAsked("CVE-2", SOURCES_AGREE), CouncilNotAsked("CVE-3", NO_TEXT_TO_READ)
    )
    assert SOURCES_AGREE in rendered
    assert NO_TEXT_TO_READ in rendered


def test_only_the_assessed_findings_are_counted_in_the_heading():
    # Counting the ones it was never put to would say the council did more than
    # it did, which is the claim the scoping has to not make.
    rendered = block(council_ran(**DISSENTING), CouncilNotAsked("CVE-2", SOURCES_AGREE))
    assert "COUNCIL (1)" in rendered
