"""Running the static checks over one app's artifacts and assembling findings.json.

The load-bearing part is `coverage.checks_run`: it names the checks that had
something to examine on this app. A check named there and silent examined its
subjects and cleared them, which is a result -- it leaves no probe record, and
that silence is the one a reader would misread as a clean bill. A check absent
from it could not look at all, so its absence is never a clean result.

The repository passed in is an empty directory, which is one half of that rule
by itself: with no Python file to read, the taint trace never had a subject.
"""

from pathlib import Path

from artifacts.findings_document import ADVISORY_NOT_INGESTED, MODEL_DISABLED
from artifacts.mapping import USED_BUT_UNDECLARED
from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks import permissions, supply_chain
from checks.run_checks import build_findings, run_static_checks
from parsing.languages import PYTHON

TOOL_SURFACE = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")
DATA_SURFACE = Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")

# The two checks under test here, whatever else runs beside them.
STATIC_CHECKS = (supply_chain.CHECK_NAME, permissions.CHECK_NAME)

MAPPING = {
    "entries": [{
        "surface_id": DATA_SURFACE.id,
        "reason": USED_BUT_UNDECLARED,
        "component_name": "pyyaml",
    }],
}


def findings_for(repo: Path, surfaces: list, mapping: dict | None) -> dict:
    """Assemble the findings document for a repository holding no source files."""
    return build_findings(str(repo), surfaces, mapping)


def test_a_check_that_examined_its_subjects_is_named_even_when_silent(tmp_path) -> None:
    """The permission check read the surface and cleared it, and coverage still names it."""
    document = findings_for(tmp_path, [DATA_SURFACE], None)
    assert document["findings"] == []
    assert permissions.CHECK_NAME in document["coverage"]["checks_run"]


def test_coverage_names_exactly_the_checks_that_had_a_subject_here(tmp_path) -> None:
    """A mapping to read and no Python to trace: two checks could look, the third could not."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], MAPPING)
    assert document["coverage"]["checks_run"] == sorted(STATIC_CHECKS)


def test_coverage_counts_the_surfaces_the_checks_saw(tmp_path) -> None:
    """A short findings list is read against how much was actually looked at."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], None)
    assert document["coverage"]["surfaces_considered"] == 2


def test_coverage_states_that_no_advisory_data_was_read(tmp_path) -> None:
    """An LLM03 finding here cites the mapping, and nothing about known vulnerabilities."""
    document = findings_for(tmp_path, [], None)
    assert document["coverage"]["advisory_data"] == ADVISORY_NOT_INGESTED


def test_the_model_is_recorded_as_disabled(tmp_path) -> None:
    """These checks read artifacts, so there is no prose and the block says why."""
    run = findings_for(tmp_path, [], None)["model_run"]
    assert run["status"] == MODEL_DISABLED
    assert run["ranking"] is None


def test_no_finding_carries_a_narrative_when_the_model_is_disabled(tmp_path) -> None:
    """The one model-authored field stays null unless a model actually wrote it."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], MAPPING)
    assert document["finding_count"] == 2
    assert all(finding["narrative"] is None for finding in document["findings"])


def test_both_static_checks_contribute_their_findings(tmp_path) -> None:
    """One privileged tool and one undeclared package produce one finding each."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], MAPPING)
    assert sorted(f["rule_id"] for f in document["findings"]) == sorted(STATIC_CHECKS)


def test_a_missing_mapping_silences_the_check_that_needs_one() -> None:
    """Without an SBOM there is no mapping, and the supply-chain check reports nothing."""
    findings = run_static_checks([TOOL_SURFACE, DATA_SURFACE], None)
    assert [finding.rule_id for finding in findings] == [permissions.CHECK_NAME]


def test_a_missing_mapping_leaves_its_check_out_of_coverage(tmp_path) -> None:
    """That check had nothing to read, so naming it would claim a clean result it never reached."""
    document = findings_for(tmp_path, [DATA_SURFACE], None)
    assert supply_chain.CHECK_NAME not in document["coverage"]["checks_run"]


def test_an_app_with_no_surfaces_produces_an_empty_document(tmp_path) -> None:
    """Audited and clean is a real result, distinct from never audited."""
    document = findings_for(tmp_path, [], None)
    assert document["finding_count"] == 0
    assert document["probes"] == []
