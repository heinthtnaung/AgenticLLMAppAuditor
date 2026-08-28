"""The rules one record cannot check alone, so the document checks them.

A probe finding must cite a probe that actually confirmed, ids must be unique,
and the model's ranking must permute exactly those ids. Each spans the whole
file, which is why none of them can live on the record.
"""

import pytest

from artifacts.finding import (
    INCONCLUSIVE,
    REFUTED,
    SURFACE_SUBJECT,
    Probe,
)
from artifacts.findings_document import MODEL_USED, model_run
from findings_fixtures import (
    PROBE_NAME,
    SURFACE_ID,
    build_document,
    confirmed_probe,
    probe_finding,
    static_finding,
)

MODEL = "qwen2.5-coder:7b-instruct"

DETAIL = "the tool holds a shell"


def unconfirmed_probe(outcome: str) -> Probe:
    """Build a probe with the same id as the confirming one, but no confirmation."""
    reason = "trace_left_static_analysis" if outcome == INCONCLUSIVE else None
    return Probe(PROBE_NAME, SURFACE_SUBJECT, SURFACE_ID, outcome, DETAIL, reason)


def used_run(ranking: list[str] | None) -> dict:
    """Build a model_run block carrying a ranking, which is the only way to test one."""
    return model_run(MODEL_USED, MODEL, {"temperature": 0}, ranking)


def test_a_probe_finding_citing_a_confirmed_probe_is_accepted() -> None:
    """The supported case: the probe ran, confirmed, and the finding names it."""
    probe = confirmed_probe()
    document = build_document([probe_finding(probe)], [probe])
    assert document["findings"][0]["probe_id"] == probe.id


def test_a_probe_finding_citing_no_recorded_probe_is_refused() -> None:
    """Without the probe record, nothing says the check ever ran."""
    with pytest.raises(ValueError, match="confirmed nothing"):
        build_document([probe_finding(confirmed_probe())], [])


@pytest.mark.parametrize("outcome", (INCONCLUSIVE, REFUTED))
def test_a_probe_finding_citing_a_probe_that_did_not_confirm_is_refused(outcome: str) -> None:
    """A probe that concluded nothing, or concluded against, is not evidence for a finding."""
    probe = unconfirmed_probe(outcome)
    with pytest.raises(ValueError, match="confirmed nothing"):
        build_document([probe_finding(confirmed_probe())], [probe])


def test_two_findings_sharing_an_id_are_refused() -> None:
    """The same surface and the same rule is the same finding reported twice."""
    with pytest.raises(ValueError, match="two findings share an id"):
        build_document([static_finding(), static_finding()])


def test_the_same_surface_under_two_rules_is_two_findings() -> None:
    """The rule is part of the id, so one surface can legitimately raise two."""
    document = build_document([static_finding(), static_finding(rule_id="other_rule")])
    assert len({f["finding_id"] for f in document["findings"]}) == 2


def test_a_ranking_permuting_every_id_is_accepted() -> None:
    """The model may reorder its own list, as long as it ranks exactly what was found."""
    findings = [static_finding(), static_finding(rule_id="other_rule")]
    ranking = [findings[1].id, findings[0].id]
    assert build_document(findings, run=used_run(ranking))["model_run"]["ranking"] == ranking


def test_a_ranking_missing_a_finding_is_refused() -> None:
    """A partial ranking silently drops a finding from whatever reads the order."""
    findings = [static_finding(), static_finding(rule_id="other_rule")]
    with pytest.raises(ValueError, match="permutation of every finding id"):
        build_document(findings, run=used_run([findings[0].id]))


def test_a_ranking_naming_something_that_was_not_found_is_refused() -> None:
    """A ranking is over the evidence, so an invented id is the model writing a finding."""
    with pytest.raises(ValueError, match="permutation of every finding id"):
        build_document([static_finding()], run=used_run(["app/agent.py:1:TOOL_CALL:X:rule"]))


def test_no_ranking_is_a_valid_document() -> None:
    """`ranking: null` is how a run with no model says it ordered nothing."""
    assert build_document([static_finding()])["model_run"]["ranking"] is None
