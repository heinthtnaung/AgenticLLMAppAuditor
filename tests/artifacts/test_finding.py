"""A finding cites its evidence, or it cannot be constructed at all.

The refusals below are the schema's point: a finding with nothing behind it,
or one that copies its surface only half way, would reach Phase 4 as something
nobody can check. Enforcing that in the constructor means no later phase has to
remember to.
"""

import pytest

from artifacts.finding import PROBE, STATIC, Finding, sort_key
from findings_fixtures import (
    OWASP_ID,
    RULE_ID,
    SURFACE_FIELDS,
    SURFACE_ID,
    TITLE,
    confirmed_probe,
    static_finding,
)

# The four fields a finding must copy from the surface it cites.
COPIED_SURFACE_FIELDS = ("surface_kind", "surface_name", "file", "line")

# Paths that describe one machine rather than the audited repository.
MACHINE_PATHS = ("/home/hein/app/agent.py", "C:/app/agent.py", "app\\agent.py")


def test_a_static_finding_copies_its_surface_whole() -> None:
    """The cited surface's kind, name, file and line travel with the finding."""
    finding = static_finding()
    assert finding.surface_id == SURFACE_ID
    assert finding.surface_kind == "TOOL_CALL"
    assert finding.surface_name == "ShellTool"
    assert (finding.file, finding.line) == ("app/agent.py", 12)


def test_finding_id_is_the_surface_id_and_the_rule() -> None:
    """The id is derived from what the finding is, never from a counter."""
    assert static_finding().id == f"{SURFACE_ID}:{RULE_ID}"


def test_finding_id_falls_back_to_the_component_name() -> None:
    """A component-anchored finding has no surface, so the component names it."""
    finding = Finding(OWASP_ID, RULE_ID, TITLE, STATIC, component_name="pyyaml")
    assert finding.id == f"pyyaml:{RULE_ID}"


def test_finding_id_falls_back_to_the_probe() -> None:
    """A probe-anchored finding is named by the probe that confirmed it."""
    probe = confirmed_probe()
    finding = Finding(OWASP_ID, RULE_ID, TITLE, PROBE, probe_id=probe.id)
    assert finding.id == f"{probe.id}:{RULE_ID}"


def test_a_finding_citing_nothing_is_refused() -> None:
    """No surface, no component, no probe: there is nothing for a reader to check."""
    with pytest.raises(ValueError, match="must cite a surface, a component or a probe"):
        Finding(OWASP_ID, RULE_ID, TITLE, STATIC)


def test_a_probe_finding_without_a_probe_is_refused() -> None:
    """`detection: probe` claims a probe reached it, so it must name which one."""
    with pytest.raises(ValueError, match="must name the probe"):
        static_finding(detection=PROBE)


def test_a_static_finding_naming_a_probe_is_refused() -> None:
    """A static finding did not run a probe, so citing one would misreport how it was reached."""
    with pytest.raises(ValueError, match="static finding names no probe"):
        static_finding(probe_id=confirmed_probe().id)


def test_an_unknown_owasp_id_is_refused() -> None:
    """Classification is what Phase 4 scores, so the vocabulary is closed."""
    with pytest.raises(ValueError, match="unknown owasp id"):
        static_finding(owasp_id="LLM99")


def test_the_grading_keys_either_is_not_an_emittable_detection() -> None:
    """`either` describes a finding class; the tool records what happened this run."""
    with pytest.raises(ValueError, match="unknown detection"):
        static_finding(detection="either")


@pytest.mark.parametrize("field", ("rule_id", "title"))
def test_a_finding_without_a_rule_or_a_title_is_refused(field: str) -> None:
    """Both are constants on the check; an empty one leaves the finding unreadable."""
    with pytest.raises(ValueError, match="needs a rule_id and a title"):
        static_finding(**{field: ""})


@pytest.mark.parametrize("field", COPIED_SURFACE_FIELDS)
def test_a_half_copied_surface_is_refused(field: str) -> None:
    """Citing a surface id without its details would force Phase 4 to parse the id."""
    with pytest.raises(ValueError, match="must copy its kind, name, file and line"):
        static_finding(**{field: None})


@pytest.mark.parametrize("path", MACHINE_PATHS)
def test_a_path_that_is_not_repo_relative_is_refused(path: str) -> None:
    """An absolute or Windows path records this machine's layout, which no artifact may."""
    with pytest.raises(ValueError, match="repo-relative posix path"):
        static_finding(file=path)


@pytest.mark.parametrize("line", (0, -1))
def test_a_line_below_one_is_refused(line: int) -> None:
    """Line numbers are 1-based, and a 0 would silently miss the join window."""
    with pytest.raises(ValueError, match="line must be 1 or greater"):
        static_finding(line=line)


def test_a_component_anchored_finding_needs_no_surface() -> None:
    """A supply-chain finding may have no code location at all, and that is valid."""
    finding = Finding("LLM03", "undeclared_dependency", "Undeclared", STATIC,
                      purl="pkg:pypi/pyyaml", component_name="pyyaml")
    assert finding.surface_id is None
    assert (finding.file, finding.line) == (None, None)


def test_sort_key_substitutes_for_the_nullable_fields() -> None:
    """A component-anchored finding sorts without ever comparing None to a string."""
    component = Finding("LLM03", RULE_ID, TITLE, STATIC, component_name="pyyaml")
    assert sort_key(component) == ("", -1, "LLM03", RULE_ID, "", "")


def test_sort_key_orders_by_file_then_line() -> None:
    """Two findings in one file are ordered by the line they sit on."""
    first = static_finding(**{**SURFACE_FIELDS, "line": 3,
                              "surface_id": "app/agent.py:3:TOOL_CALL:ShellTool"})
    assert sort_key(first) < sort_key(static_finding())
