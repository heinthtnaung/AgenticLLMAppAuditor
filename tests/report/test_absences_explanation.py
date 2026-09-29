"""Guards on the one absence of an explanation: why no finding's sources were explained."""

import pytest

from explanation_runs import EXPLAINER, disputed, explained_report, replying, INVENTED
from cli.explanation_run import explanations
from report.absences import (
    EXPLANATION,
    NO_EXPLAINER_ASKED,
    NONE_EXPLAINED,
    NOTHING_TO_EXPLAIN,
    Coverage,
)
from council.transport import ModelUnavailable
from report.record import build_report
from report_samples import PROVENANCE, catalogue, component, finding

COUNCIL_NAMED = Coverage(council_named=True)


def timing_out(member, prompt):
    """Fail as a slow server fails, so nothing is quoted at all."""
    raise ModelUnavailable("did not answer within 180 s")


def explanation_absence(report) -> list[str]:
    """Give why the report says no explanation was kept, if it says so."""
    return [one.because for one in report.not_assessed if one.what == EXPLANATION]


def test_a_run_that_named_no_council_says_no_model_was_asked():
    report = build_report(PROVENANCE, catalogue(component()), (disputed("CVE-1"),), {})
    assert explanation_absence(report) == [NO_EXPLAINER_ASKED]


def test_a_council_run_with_no_disagreement_says_there_was_nothing_to_explain():
    agreeing = (finding(component()),)
    report = build_report(PROVENANCE, catalogue(component()), agreeing, {}, coverage=COUNCIL_NAMED)
    assert explanation_absence(report) == [NOTHING_TO_EXPLAIN]


@pytest.mark.parametrize("model", [replying(INVENTED), {"ollama": timing_out}],
                         ids=["every item dropped", "the call failed"])
def test_a_council_run_that_kept_no_explanation_says_so_whatever_stopped_it(model):
    found = (disputed("CVE-1"),)
    records = explanations(found, EXPLAINER, model)
    report = build_report(
        PROVENANCE, catalogue(component()), found, {}, coverage=COUNCIL_NAMED, explanations=records
    )
    assert explanation_absence(report) == [NONE_EXPLAINED]
    assert NONE_EXPLAINED.endswith("and no explanation was kept")


def test_one_explanation_kept_is_no_absence_whatever_the_others_came_to():
    assert explanation_absence(explained_report()) == []
