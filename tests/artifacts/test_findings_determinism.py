"""findings.json is byte-identical except for the two fields a model writes.

`SCHEMAS.md` exempts exactly `model_run.ranking` and each finding's
`narrative`. Everything else -- the evidence, the counts, the record order --
keeps the guarantee every other artifact makes, so a diff between two runs
shows a change in what was found rather than a change in wording.
"""

from artifacts.findings_document import (
    MODEL_AUTHORED_DOCUMENT_FIELD,
    MODEL_AUTHORED_FINDING_FIELD,
    MODEL_USED,
    findings_to_json,
    model_run,
    strip_model_authored,
)
from dependency_fixtures import string_values
from findings_fixtures import build_document, confirmed_probe, static_finding

MODEL = "qwen2.5-coder:7b-instruct"

# Two runs of the same evidence, differing only in what the model wrote.
FIRST_NARRATIVE = "The tool exposes a shell to the agent."
SECOND_NARRATIVE = "This tool hands the model an operating-system shell."


def two_findings() -> tuple:
    """Build the same two findings twice, so a ranking has something to permute."""
    return static_finding(), static_finding(rule_id="other_rule")


def run_with(narrative: str, reverse_ranking: bool) -> dict:
    """Build one whole document with a given narrative and ranking order."""
    findings = [static_finding(narrative=narrative),
                static_finding(rule_id="other_rule", narrative=narrative)]
    ranking = [f.id for f in findings]
    if reverse_ranking:
        ranking.reverse()
    return build_document(findings, run=model_run(MODEL_USED, MODEL, {"seed": 0}, ranking))


def test_stripping_removes_the_ranking_and_every_narrative() -> None:
    """The two exempt fields are the two that go."""
    stripped = strip_model_authored(run_with(FIRST_NARRATIVE, reverse_ranking=False))
    assert MODEL_AUTHORED_DOCUMENT_FIELD not in stripped["model_run"]
    assert all(MODEL_AUTHORED_FINDING_FIELD not in f for f in stripped["findings"])


def test_stripping_removes_nothing_else() -> None:
    """A wider exception would quietly excuse evidence from the comparison."""
    document = run_with(FIRST_NARRATIVE, reverse_ranking=False)
    stripped = strip_model_authored(document)
    assert set(stripped) == set(document)
    assert set(stripped["model_run"]) == set(document["model_run"]) - {"ranking"}
    assert stripped["model_run"]["model_settings"] == {"seed": 0}
    assert stripped["model_run"]["model_identifier"] == MODEL
    assert [set(f) for f in stripped["findings"]] == [
        set(f) - {"narrative"} for f in document["findings"]]


def test_stripping_leaves_the_original_document_untouched() -> None:
    """The projection is a copy, so a caller can still write the real file after it."""
    document = run_with(FIRST_NARRATIVE, reverse_ranking=False)
    strip_model_authored(document)
    assert document["model_run"]["ranking"] is not None
    assert document["findings"][0]["narrative"] == FIRST_NARRATIVE


def test_different_prose_and_ranking_leave_an_identical_projection() -> None:
    """This is the guarantee: two runs differ only where the schema says they may."""
    first = run_with(FIRST_NARRATIVE, reverse_ranking=False)
    second = run_with(SECOND_NARRATIVE, reverse_ranking=True)
    assert findings_to_json(strip_model_authored(first)) == findings_to_json(
        strip_model_authored(second))


def test_record_order_never_depends_on_the_model() -> None:
    """`findings` is sorted by evidence, so a reordered ranking moves nothing."""
    first = run_with(FIRST_NARRATIVE, reverse_ranking=False)
    second = run_with(SECOND_NARRATIVE, reverse_ranking=True)
    assert [f["finding_id"] for f in first["findings"]] == [
        f["finding_id"] for f in second["findings"]]


def test_a_run_with_no_model_is_byte_identical_in_full() -> None:
    """With the model disabled, nothing is exempt: the whole file must repeat exactly."""
    probe = confirmed_probe()
    first = findings_to_json(build_document(two_findings(), [probe]))
    second = findings_to_json(build_document(two_findings(), [probe]))
    assert first == second


def test_input_order_does_not_reach_the_file() -> None:
    """Two machines walking the repo in different orders must write the same bytes."""
    findings = two_findings()
    assert findings_to_json(build_document(findings)) == findings_to_json(
        build_document(list(reversed(findings))))


def test_no_absolute_path_reaches_the_artifact() -> None:
    """A path in a finding is repo-relative, so the file describes the app, not the machine."""
    document = run_with(FIRST_NARRATIVE, reverse_ranking=False)
    absolute = [value for value in string_values(document) if value.startswith("/")]
    assert absolute == []
