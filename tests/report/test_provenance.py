"""Guards on what produced a run: a database there or named missing, and every field asked."""

import json

import pytest

from report.html_report import as_html
from report.json_report import as_json
from report.model_identity import MEMBER_ROLE, ModelDigest, OllamaVersion
from report.provenance import AdvisoryDatabase, LocalModels, RunProvenance, UnknownAdvisoryDatabase
from report.record import build_report
from report.text_report import as_text
from report_samples import DATABASE, PROVENANCE, catalogue, component
from scoring.version import SCORING_RULES_VERSION


def local_models(models):
    """Build a local-model record with the given models, every other setting fixed."""
    return LocalModels(
        server="http://127.0.0.1:11434", context_tokens=8192, timeout_seconds=180.0,
        temperature=0, seed=11, think=False, order_check=True, escalation_model=None,
        ollama_version=OllamaVersion("0.34.3"), models=models,
    )


@pytest.mark.parametrize("built", ["", "   "], ids=["empty", "blank"])
def test_a_database_naming_no_build_date_is_refused(built):
    with pytest.raises(ValueError, match="must give the date it was built"):
        AdvisoryDatabase(built)


def test_a_missing_database_date_must_say_why():
    with pytest.raises(ValueError, match="must say why it is missing"):
        UnknownAdvisoryDatabase("")


def test_an_unreadable_database_is_not_the_same_as_a_fresh_one():
    unknown = UnknownAdvisoryDatabase("no metadata.json on this machine")
    assert not isinstance(unknown, AdvisoryDatabase)
    assert not hasattr(unknown, "built_at")


@pytest.mark.parametrize(
    "field", ["repository", "syft_version", "trivy_version", "scoring_rules_version"]
)
def test_provenance_a_reader_could_not_reproduce_the_run_from_is_refused(field):
    fields = {"repository": "r", "syft_version": "s", "trivy_version": "t", "database": DATABASE}
    with pytest.raises(ValueError, match=f"needs {field}"):
        RunProvenance(**{**fields, field: ""})


@pytest.mark.parametrize("given", [None, "2026-09-22", 0], ids=["none", "str", "int"])
def test_provenance_without_a_real_database_is_refused(given):
    with pytest.raises(TypeError, match="needs a database"):
        RunProvenance("r", "s", "t", given)


def test_a_record_of_a_council_that_asked_no_model_is_refused():
    with pytest.raises(ValueError, match="asks at least one model"):
        local_models(())


def test_a_record_of_one_asked_model_stands():
    asked = local_models((ModelDigest("qwen2.5:7b", MEMBER_ROLE, "845dbda0ea48ed749caafd"),))
    assert len(asked.models) == 1


def test_a_run_records_the_scoring_rules_this_code_scores_by():
    fields = {"repository": "r", "syft_version": "s", "trivy_version": "t", "database": DATABASE}
    assert RunProvenance(**fields).scoring_rules_version == SCORING_RULES_VERSION


def test_every_rendering_names_the_scoring_rules_in_its_provenance():
    report = build_report(PROVENANCE, catalogue(component()), (), {})
    said = f"scoring rules {SCORING_RULES_VERSION}"
    assert as_text(report).split("\n")[2] == f"  {said}"
    assert json.loads(as_json(report))["run"]["scoring_rules_version"] == SCORING_RULES_VERSION
    assert f'<span class="separator">·</span>{said}</p>' in as_html(report)
