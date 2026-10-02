"""Guards on the report-side queries over a council's record: what it ran on, and what it flagged.

These read the projection and decide nothing new, so a change here is a change to
what the renderers that share them are shown, not to the record itself.
"""

from cli.council_run import SOURCES_AGREE
from council_runs import DISSENTING, council_ran
from report.council_queries import flagged_metrics, was_assessed
from report.council_record import CouncilAssessment, CouncilNotAsked, CouncilWithoutVector
from same_evidence_runs import same_words, unflagged


def test_a_finding_passed_over_is_not_a_finding_that_was_assessed():
    settled, still_open = council_ran(), council_ran(**DISSENTING)
    assert (type(settled), type(still_open)) == (CouncilAssessment, CouncilWithoutVector)
    assert was_assessed(CouncilNotAsked("CVE-1", SOURCES_AGREE)) is False
    assert was_assessed(settled) is True
    assert was_assessed(still_open) is True


def test_flagged_metrics_names_only_the_rulings_read_two_ways_from_the_same_words():
    assert flagged_metrics(same_words()) == ("AV",)
    assert flagged_metrics(unflagged(same_words())) == ()
    assert flagged_metrics(CouncilNotAsked("CVE-1", "the sources agreed")) == ()
