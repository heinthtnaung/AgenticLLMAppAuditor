"""Guards on what a council run comes to: a vector where every metric settled, else what is open."""

import json

from cli.council_detail import rulings_of
from cli.council_outcome import VECTOR_VERSION, metrics_of, outcome_of
from cli.council_run import FALLBACKS, advisory_text, build_roster
from cli_samples import ADVISORY, LEGAL, LODASH, QUOTATION
from council.ruling import UnresolvedMetric
from council.runner import assess
from findings.finding import build_finding
from report.council_record import CouncilAssessment, CouncilWithoutVector

FINDING = build_finding(LODASH, ADVISORY)


def run_declining(declined: set[str]):
    """Run one member over the sample finding, declining the metrics named."""

    def said(member, prompt):
        """Decline a named metric, and quote the advisory for any other."""
        if prompt.metric in declined:
            return json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
        value = LEGAL[prompt.metric]
        return json.dumps({"value": value, "evidence": QUOTATION, "confidence": "high"})

    text = advisory_text(FINDING)
    run = assess(text, build_roster(("small",)), FALLBACKS, {"ollama": said}, order_check=True)
    return run, rulings_of(run, text)


def test_every_metric_settled_hands_over_the_vector_they_make():
    run, rulings = run_declining(set())
    outcome = outcome_of(FINDING, run, rulings)
    assert isinstance(outcome, CouncilAssessment)
    assert outcome.vector == f"CVSS:{VECTOR_VERSION}/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


def test_a_metric_left_open_hands_over_no_vector_and_names_it_in_specification_order():
    run, rulings = run_declining({"A", "AV"})
    outcome = outcome_of(FINDING, run, rulings)
    assert isinstance(outcome, CouncilWithoutVector)
    assert outcome.unresolved_metrics == metrics_of(run, UnresolvedMetric) == ("AV", "A")
