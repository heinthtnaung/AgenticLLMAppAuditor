"""What Tasks 3.2 and 3.3's checks really produce on the three corpus fixtures.

The recorded SBOM stands in for Syft, so this runs offline. The claims are
scoped to the two static checks those tasks built -- `run_static_checks` --
rather than to the whole document, so a later check landing beside them can
neither mask a miss here nor turn a true statement about these two into a
failure. The document-level tests below are the ones that must hold whatever
else runs: coverage, the model block, and the clean fixture's silence.
"""

from artifacts.finding import STATIC
from artifacts.findings_document import ADVISORY_NOT_INGESTED, MODEL_DISABLED
from artifacts.mapping import USED_BUT_UNDECLARED
from artifacts.surface import DATA_SOURCE
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.run_checks import CHECK_NAMES
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from conftest import app_path, ground_truth, require_corpus
from dependency_fixtures import (
    LANGGRAPHJS_STARTER,
    REACT_AGENT,
    SUPPORT_AGENT,
    corpus_sbom,
    js_sbom,
)
from main import declared_ecosystems, dependencies_readable
from findings_fixtures import (
    corpus_findings,
    corpus_findings_without_mapping,
    corpus_static_check_findings,
)

# Verified by hand against each fixture at its pinned commit.
SUPPORT_AGENT_SURFACE_COUNT = 19
STARTER_SURFACE_COUNT = 5
REACT_AGENT_SURFACE_COUNT = 4

# The clean fixture is JavaScript, and the taint trace reads an `ast` tree, so
# only these two checks had anything to examine there.
STARTER_CHECKS = sorted((PERMISSION_CHECK, SUPPLY_CHAIN_CHECK))

# The clean Python fixture declares its dependencies in pyproject.toml and pins
# them in uv.lock, neither of which this tool reads, so there is no bill of
# materials for the supply-chain check to search -- but there is Python to trace.
REACT_AGENT_CHECKS = sorted((PERMISSION_CHECK, TAINT_CHECK))

# The one surface the Python app's undeclared dependency is reached through.
UNDECLARED_SURFACE_ID = "utils.py:75:DATA_SOURCE:yaml.load"
UNDECLARED_COMPONENT = "pyyaml"


def support_agent_static_findings() -> list:
    """Run the supply-chain and permission checks over the vulnerable Python app."""
    return corpus_static_check_findings(SUPPORT_AGENT, corpus_sbom())


def test_the_two_static_checks_yield_exactly_one_finding() -> None:
    """Of the pair, only the supply-chain check fires on this app, and it fires once."""
    findings = support_agent_static_findings()
    assert len(findings) == 1
    assert findings[0].rule_id == SUPPLY_CHAIN_CHECK


def test_the_finding_is_the_undeclared_pyyaml_dependency() -> None:
    """LLM03, anchored on the yaml.load surface the mapping flagged."""
    finding = support_agent_static_findings()[0]
    assert finding.owasp_id == "LLM03"
    assert finding.component_name == UNDECLARED_COMPONENT
    assert finding.mapping_reason == USED_BUT_UNDECLARED


def test_the_finding_points_at_the_yaml_load_surface() -> None:
    """The exact file, line, kind and name the grading key records."""
    finding = support_agent_static_findings()[0]
    assert finding.surface_id == UNDECLARED_SURFACE_ID
    assert (finding.file, finding.line) == ("utils.py", 75)
    assert (finding.surface_kind, finding.surface_name) == (DATA_SOURCE, "yaml.load")
    assert finding.detection == STATIC


def test_the_support_agent_reports_no_privileged_tool() -> None:
    """Its graded LLM06 is a missing authorisation check, which this rule cannot reach."""
    assert [f for f in support_agent_static_findings() if f.rule_id == PERMISSION_CHECK] == []


def test_the_permission_check_ran_on_the_support_agent_and_found_nothing() -> None:
    """No clean fixture uses a shell, interpreter or requests tool, so zero is the honest result.

    The zero is only readable as a result because coverage names the check as
    having run: without that, it is indistinguishable from a check that never
    executed at all.
    """
    document = corpus_findings(SUPPORT_AGENT, corpus_sbom())
    assert [f for f in document["findings"] if f["rule_id"] == PERMISSION_CHECK] == []
    assert PERMISSION_CHECK in document["coverage"]["checks_run"]


def test_the_permission_check_ran_on_the_clean_fixture_and_found_nothing() -> None:
    """The same statement about the app whose key claims it is clean."""
    document = corpus_findings(LANGGRAPHJS_STARTER, js_sbom())
    assert [f for f in document["findings"] if f["rule_id"] == PERMISSION_CHECK] == []
    assert PERMISSION_CHECK in document["coverage"]["checks_run"]


def test_the_undeclared_dependency_reaches_the_document() -> None:
    """The check's finding survives assembly, with its derived id intact."""
    document = corpus_findings(SUPPORT_AGENT, corpus_sbom())
    ids = [f["finding_id"] for f in document["findings"] if f["rule_id"] == SUPPLY_CHAIN_CHECK]
    assert ids == [f"{UNDECLARED_SURFACE_ID}:{SUPPLY_CHAIN_CHECK}"]


def test_the_support_agent_coverage_names_what_was_searched() -> None:
    """19 surfaces, and every check named because Python and a mapping gave all three a subject."""
    document_coverage = corpus_findings(SUPPORT_AGENT, corpus_sbom())["coverage"]
    assert document_coverage["surfaces_considered"] == SUPPORT_AGENT_SURFACE_COUNT
    assert document_coverage["checks_run"] == sorted(CHECK_NAMES)
    assert document_coverage["advisory_data"] == ADVISORY_NOT_INGESTED


def test_the_support_agent_run_used_no_model() -> None:
    """Phase 3's static checks write no prose, so every narrative is null."""
    document = corpus_findings(SUPPORT_AGENT, corpus_sbom())
    assert document["model_run"]["status"] == MODEL_DISABLED
    assert all(finding["narrative"] is None for finding in document["findings"])


def test_the_clean_fixture_produces_no_finding() -> None:
    """Its key asserts the app is clean, so anything reported here is a false positive."""
    assert corpus_findings(LANGGRAPHJS_STARTER, js_sbom())["findings"] == []


def test_the_clean_fixture_was_searched_by_the_checks_that_could_search_it() -> None:
    """Zero findings mean something only because those checks ran over its five surfaces."""
    document_coverage = corpus_findings(LANGGRAPHJS_STARTER, js_sbom())["coverage"]
    assert document_coverage["surfaces_considered"] == STARTER_SURFACE_COUNT
    assert document_coverage["checks_run"] == STARTER_CHECKS


def test_the_check_that_could_not_search_the_clean_fixture_is_absent() -> None:
    """The trace reads Python and this app is JavaScript, so naming it would claim a clean run."""
    checks_run = corpus_findings(LANGGRAPHJS_STARTER, js_sbom())["coverage"]["checks_run"]
    assert TAINT_CHECK not in checks_run


def test_the_clean_fixtures_key_agrees_it_is_clean() -> None:
    """The zero above is only a result because the key claims completeness."""
    truth = ground_truth(LANGGRAPHJS_STARTER)
    assert truth["finding_count"] == 0 and truth["findings_complete"]


def react_agent_document() -> dict:
    """Build the clean Python fixture's document; no manifest this tool reads means no mapping."""
    return corpus_findings_without_mapping(REACT_AGENT)


def test_the_clean_python_fixture_produces_no_finding() -> None:
    """The false-positive count on Python: its key lists no finding, so anything here is one."""
    document = react_agent_document()
    assert document["finding_count"] == 0
    assert document["findings"] == []


def test_the_check_that_could_not_search_the_javascript_fixture_ran_here() -> None:
    """The trace reads an `ast` tree and this app is Python, so the zero above covers it too."""
    assert TAINT_CHECK in react_agent_document()["coverage"]["checks_run"]


def test_the_clean_python_fixture_was_searched_over_its_four_surfaces() -> None:
    """Four is what the extractor produces, not what the app contains, so a wider detector vocabulary fails here, not drifts."""
    document_coverage = react_agent_document()["coverage"]
    assert document_coverage["surfaces_considered"] == REACT_AGENT_SURFACE_COUNT
    assert document_coverage["checks_run"] == REACT_AGENT_CHECKS


def test_the_fixture_with_no_readable_manifest_leaves_the_component_count_unknown() -> None:
    """Null rather than zero: no bill of materials was built, so nothing was left over."""
    assert react_agent_document()["coverage"]["unresolved_component_count"] is None


def test_the_supply_chain_check_is_absent_where_no_bill_of_materials_exists() -> None:
    """Naming the check, or LLM03, would claim a supply chain examined and found sound."""
    document_coverage = react_agent_document()["coverage"]
    assert SUPPLY_CHAIN_CHECK not in document_coverage["checks_run"]
    assert "LLM03" not in document_coverage["risk_classes_checked"]


def test_the_clean_python_fixtures_key_agrees_it_is_clean() -> None:
    """The zero above is only a result because this key claims to list every finding."""
    truth = ground_truth(REACT_AGENT)
    assert truth["finding_count"] == 0 and truth["findings_complete"]


def test_the_clean_python_fixture_really_declares_no_manifest_this_tool_reads() -> None:
    """The premise behind every no-mapping assertion above, taken from the fixture itself.

    Those tests hand `build_findings` a `None` mapping, so they certify the
    plumbing rather than the app. This pins the fact that makes the `None`
    real: `pyproject.toml` and `uv.lock` are what this fixture ships, and
    neither is a manifest the tool reads. It fails the day one of them is
    supported, which is exactly when the claims above stop holding.
    """
    require_corpus(REACT_AGENT)
    assert declared_ecosystems(app_path(REACT_AGENT)) == []
    assert dependencies_readable(app_path(REACT_AGENT)) == (False, "no dependency manifest found")
