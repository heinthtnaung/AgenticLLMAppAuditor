"""The findings document: what was covered, what produced the prose, and the records.

`coverage` and `model_run` are the two blocks a reader consults before trusting
a short findings list, so both are checked here as closely as the records are.
The cross-record refusals live in test_findings_document_rules.py.
"""

import json

import pytest

from artifacts.finding import (
    SCHEMA_VERSION,
    INCONCLUSIVE,
    OWASP_IDS,
    SURFACE_SUBJECT,
    Probe,
)
from artifacts.findings_document import (
    ADVISORY_NOT_INGESTED,
    ADVISORY_SNAPSHOT,
    MODEL_DISABLED,
    MODEL_UNAVAILABLE,
    MODEL_USED,
    coverage,
    findings_to_json,
    model_run,
)
from findings_fixtures import (
    RULE_ID,
    SURFACE_FIELDS,
    build_document,
    confirmed_probe,
    static_finding,
)

MODEL = "qwen2.5-coder:7b-instruct"

# What the client really sends, so the artifact records a repeatable run.
DECODE_SETTINGS = {"temperature": 0, "seed": 0}

# Supply chain's id in the pre-2025 list, which is how a wrong id realistically
# gets written: an edition confused, not a value invented.
STALE_EDITION_RISK = "LLM05"


def test_coverage_sorts_the_checks_that_ran() -> None:
    """Input order must not reach the artifact, or two machines would differ."""
    assert coverage(19, ["undeclared_dependency", "high_privilege_tool"])["checks_run"] == [
        "high_privilege_tool", "undeclared_dependency",
    ]


def test_coverage_defaults_to_no_advisory_data() -> None:
    """Advisory ingestion has not landed, so the absence is stated rather than implied."""
    assert coverage(0, [])["advisory_data"] == ADVISORY_NOT_INGESTED


def test_coverage_accepts_a_snapshot() -> None:
    """The other documented value is available for when a snapshot is read from disk."""
    assert coverage(1, [RULE_ID], ADVISORY_SNAPSHOT)["advisory_data"] == ADVISORY_SNAPSHOT


def test_coverage_refuses_an_unknown_advisory_state() -> None:
    """A third value would let a reader believe advisories were consulted."""
    with pytest.raises(ValueError, match="unknown advisory state"):
        coverage(1, [RULE_ID], "maybe")


def test_coverage_refuses_a_negative_surface_count() -> None:
    """A negative count is not a coverage claim anyone could check."""
    with pytest.raises(ValueError, match="must not be negative"):
        coverage(-1, [RULE_ID])


def test_coverage_accepts_no_unresolved_count_at_all() -> None:
    """No mapping means nothing to resolve against, and null says so where 0 would not."""
    assert coverage(3, [RULE_ID])["unresolved_component_count"] is None


def test_coverage_carries_an_unresolved_count_it_was_given() -> None:
    """The number is copied from the mapping, so the block must hand it back unchanged."""
    assert coverage(3, [RULE_ID], unresolved_component_count=2)["unresolved_component_count"] == 2


def test_coverage_accepts_every_surface_being_unresolved() -> None:
    """An app whose imports resolve to nothing is a real audit, not a contradiction."""
    assert coverage(3, [RULE_ID], unresolved_component_count=3)["unresolved_component_count"] == 3


def test_coverage_refuses_a_negative_unresolved_count() -> None:
    """Fewer than none untraceable is not a number any mapping could produce."""
    with pytest.raises(ValueError, match="unresolved_component_count must not be negative, got -1"):
        coverage(3, [RULE_ID], unresolved_component_count=-1)


def test_coverage_refuses_more_unresolved_surfaces_than_it_considered() -> None:
    """The mapping holds one entry per surface, so a larger count contradicts the surfaces."""
    with pytest.raises(ValueError, match="4 exceeds the 3 surfaces considered"):
        coverage(3, [RULE_ID], unresolved_component_count=4)


def test_coverage_refuses_a_risk_class_outside_the_vocabulary() -> None:
    """An unknown id claims a class that does not exist, and the message has to name it."""
    with pytest.raises(ValueError, match="unknown risk classes") as refused:
        coverage(3, [RULE_ID], risk_classes_checked=["LLM06", STALE_EDITION_RISK])
    assert STALE_EDITION_RISK in str(refused.value)


def test_coverage_accepts_the_classes_a_run_really_covered() -> None:
    """A run covering two of the five records those two, sorted like every other list here."""
    covered = coverage(3, [RULE_ID], risk_classes_checked=["LLM06", "LLM03"])
    assert covered["risk_classes_checked"] == ["LLM03", "LLM06"]


def test_coverage_accepts_the_whole_vocabulary() -> None:
    """Every id in OWASP_IDS is valid input, or the field could never say all five were covered."""
    covered = coverage(3, [RULE_ID], risk_classes_checked=list(OWASP_IDS))
    assert covered["risk_classes_checked"] == sorted(OWASP_IDS)


def test_coverage_accepts_an_empty_risk_class_list() -> None:
    """No check could look, so the report must render all five as uncovered rather than refuse."""
    assert coverage(3, [RULE_ID], risk_classes_checked=[])["risk_classes_checked"] == []


def test_coverage_defaults_to_no_risk_classes_checked() -> None:
    """Omitting the argument claims coverage of nothing, which is the safe default."""
    assert coverage(3, [RULE_ID])["risk_classes_checked"] == []


def test_a_disabled_model_names_none_and_ranks_nothing() -> None:
    """Today's runs are static, so the block says so instead of leaving nulls unexplained."""
    run = model_run(MODEL_DISABLED)
    assert run["status"] == MODEL_DISABLED
    assert run["model_identifier"] is None
    assert run["model_settings"] == {}
    assert run["ranking"] is None


def test_a_used_model_records_the_settings_that_were_sent() -> None:
    """Reproducible prose rests on recording the decode settings, so they are stored."""
    run = model_run(MODEL_USED, MODEL, DECODE_SETTINGS)
    assert run["model_identifier"] == MODEL
    assert run["model_settings"] == DECODE_SETTINGS


def test_a_used_model_must_be_named() -> None:
    """Prose with no model behind it cannot be repeated by anyone."""
    with pytest.raises(ValueError, match="used model must be named"):
        model_run(MODEL_USED)


@pytest.mark.parametrize("status", (MODEL_DISABLED, MODEL_UNAVAILABLE))
def test_a_model_that_did_not_run_names_no_model(status: str) -> None:
    """Naming a model that wrote nothing would read as prose nobody can find."""
    with pytest.raises(ValueError, match="names no model"):
        model_run(status, MODEL)


def test_an_unknown_model_status_is_refused() -> None:
    """Three statuses cover it; a fourth would be unreadable to Phase 4."""
    with pytest.raises(ValueError, match="unknown model status"):
        model_run("maybe")


def test_the_document_reports_the_schema_version_and_both_counts() -> None:
    """A reader can sanity-check the file without counting the lists themselves."""
    document = build_document([static_finding()], [confirmed_probe()])
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["finding_count"] == len(document["findings"]) == 1
    assert document["probe_count"] == len(document["probes"]) == 1


def test_an_audited_app_with_nothing_found_is_a_valid_document() -> None:
    """`finding_count: 0` means "audited, clean", which the JS fixture depends on."""
    document = build_document([], surfaces_considered=5)
    assert document["finding_count"] == 0
    assert document["findings"] == []
    assert document["coverage"]["surfaces_considered"] == 5


def test_each_record_carries_its_derived_id() -> None:
    """The ids the ranking permutes are written out, not left to be recomputed."""
    probe = confirmed_probe()
    document = build_document([static_finding()], [probe])
    assert document["findings"][0]["finding_id"] == f"{SURFACE_FIELDS['surface_id']}:{RULE_ID}"
    assert document["probes"][0]["probe_id"] == probe.id


def test_probes_are_sorted_by_their_id() -> None:
    """Two runs must list the same probes in the same order."""
    late = Probe("z_check", SURFACE_SUBJECT, "b.py:1:TOOL_CALL:X", INCONCLUSIVE,
                 "no trace", "trace_left_static_analysis")
    document = build_document([], [late, confirmed_probe()])
    assert [p["probe_id"] for p in document["probes"]] == sorted(
        p["probe_id"] for p in document["probes"])


def test_findings_are_sorted_by_file_and_line() -> None:
    """Record order is the evidence's, so the order of the input cannot show through."""
    first = static_finding(surface_id="app/agent.py:3:TOOL_CALL:ShellTool", line=3)
    document = build_document([static_finding(), first])
    assert [f["line"] for f in document["findings"]] == [3, 12]


def test_the_json_is_key_sorted_and_ends_with_one_newline() -> None:
    """The stable on-disk form keeps two runs diffable."""
    text = findings_to_json(build_document([static_finding()]))
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert json.loads(text)["finding_count"] == 1
    assert text.index('"coverage"') < text.index('"model_run"') < text.index('"probes"')
