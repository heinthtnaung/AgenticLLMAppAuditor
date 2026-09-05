"""The one join rule: which produced finding answers which grading-key entry.

Three test files used to spell this rule three different ways -- one symmetric
window, one wider below the anchor, one ignoring `line_end` -- so the suite
certified a join no scorer ran. It lives in `evaluation/grading.py` now, and
this file is where its edges are pinned: what the window is, what is compared,
and what is deliberately not.
"""

from dataclasses import asdict

from evaluation.grading import LINE_TOLERANCE, line_window, matches_key
from evaluation_fixtures import LINE, key_entry
from findings_fixtures import PROBE_NAME, SURFACE_ID, static_finding

# A key entry whose construct spans lines, so `line_end` has something to extend.
MULTI_LINE_END = LINE + 8


def produced(**overrides) -> dict:
    """The produced finding as the artifact holds it: a plain dict, not a record."""
    return asdict(static_finding(**overrides))


def test_the_documented_tolerance_is_three_lines() -> None:
    """SCHEMAS.md states the number; a silent change here rewrites every score."""
    assert LINE_TOLERANCE == 3


def test_the_window_runs_from_the_key_line_to_the_tolerance_below_it() -> None:
    """A single-line entry accepts the anchor and the three lines under it."""
    assert line_window(key_entry()) == (LINE, LINE + LINE_TOLERANCE)


def test_line_end_extends_the_window_to_the_end_of_the_construct() -> None:
    """A multi-line construct is matched anywhere in it, plus the tolerance."""
    entry = key_entry(line_end=MULTI_LINE_END)
    assert line_window(entry) == (LINE, MULTI_LINE_END + LINE_TOLERANCE)


def test_an_entry_without_a_line_end_field_falls_back_to_its_line() -> None:
    """`line_end` is absent on some keys and null on others; both mean the same thing."""
    assert line_window({"file": "a.py", "line": LINE}) == line_window(key_entry())


def test_a_finding_on_the_key_line_matches() -> None:
    """The ordinary case: same file, same class, same line, same surface."""
    assert matches_key(produced(), key_entry())


def test_a_finding_three_lines_below_the_anchor_still_matches() -> None:
    """A detector may report a few lines into a construct the human anchored at its first."""
    assert matches_key(produced(line=LINE + LINE_TOLERANCE), key_entry())


def test_a_finding_four_lines_below_the_anchor_does_not_match() -> None:
    """The window is bounded, and a failed match is never retried wider."""
    assert not matches_key(produced(line=LINE + LINE_TOLERANCE + 1), key_entry())


def test_a_finding_one_line_above_the_anchor_does_not_match() -> None:
    """The window opens at the key's line: it is not symmetric around it.

    This is the rule two of the old copies got wrong. A finding above the
    anchor is a different construct, so it must not be credited to this entry.
    """
    assert not matches_key(produced(line=LINE - 1), key_entry())


def test_a_finding_inside_a_multi_line_construct_matches() -> None:
    """`line_end` is why an entry spanning nine lines is matched at its last one."""
    assert matches_key(produced(line=MULTI_LINE_END), key_entry(line_end=MULTI_LINE_END))


def test_a_finding_in_another_file_does_not_match() -> None:
    """The file is the first thing compared; nothing else can rescue a wrong one."""
    assert not matches_key(produced(file="other.py",
                                    surface_id="other.py:12:TOOL_CALL:ShellTool"),
                           key_entry())


def test_a_finding_of_another_risk_class_does_not_match() -> None:
    """Classification is what Phase 4 scores, so a misfiled finding earns nothing."""
    assert not matches_key(produced(owasp_id="LLM01"), key_entry())


def test_a_finding_with_no_line_does_not_match() -> None:
    """A component-anchored finding has no line, and must not fall into a window."""
    component = produced(surface_id=None, surface_kind=None, surface_name=None,
                         file=None, line=None, component_name="pyyaml")
    assert not matches_key(component, key_entry())


def test_a_static_finding_answers_a_key_entry_marked_either() -> None:
    """The key's `either` says what could reach the finding; the tool says what did."""
    assert matches_key(produced(), key_entry(detection="either"))


def test_a_probe_finding_answers_a_key_entry_marked_static() -> None:
    """`detection` is never compared, so the two values need not agree at all."""
    probe = produced(detection="probe", probe_id=f"{PROBE_NAME}:{SURFACE_ID}")
    assert matches_key(probe, key_entry(detection="static"))


def test_a_key_entry_naming_a_surface_kind_requires_it() -> None:
    """Where the key names the kind, a finding on another kind is not that finding."""
    assert not matches_key(produced(), key_entry(llm_surface="PROMPT_TEMPLATE"))


def test_a_key_entry_naming_no_surface_kind_ignores_it() -> None:
    """A component-level entry names no surface, so the kind is not part of the join."""
    assert matches_key(produced(), key_entry(llm_surface=None))


def test_a_key_entry_naming_a_surface_name_requires_it() -> None:
    """Two tools on the same line are two findings; the name is what separates them."""
    assert not matches_key(produced(), key_entry(surface_name="OtherTool"))


def test_a_key_entry_naming_no_surface_name_ignores_it() -> None:
    """A key that left the name out is answered by any finding at that location."""
    assert matches_key(produced(surface_name="OtherTool"), key_entry(surface_name=None))


def test_the_title_and_narrative_are_never_compared() -> None:
    """Prose is descriptive only: a model-written narrative cannot move a score."""
    assert matches_key(produced(title="something else entirely",
                                narrative="the model's opinion"), key_entry())


# One component purl, spelled exactly as the SBOM writes it.
COMPONENT_PURL = "pkg:npm/%40langchain/community@0.3.3"


def test_a_key_entry_naming_a_component_requires_the_equal_purl() -> None:
    """Where the key names a component, a finding citing that exact purl answers it."""
    assert matches_key(produced(purl=COMPONENT_PURL), key_entry(component=COMPONENT_PURL))


def test_a_key_entry_naming_a_component_rejects_a_different_purl() -> None:
    """A finding on the right surface but the wrong component is not that finding."""
    assert not matches_key(produced(purl="pkg:pypi/pyyaml@5.3.1"),
                           key_entry(component=COMPONENT_PURL))


def test_a_key_entry_naming_a_component_rejects_a_finding_without_a_purl() -> None:
    """This clause keeps a component entry out of every baseline's reach: no purl, no credit."""
    assert not matches_key(produced(), key_entry(component=COMPONENT_PURL))


def test_a_key_entry_with_a_null_component_ignores_the_purl() -> None:
    """`component` is null on surface-level entries, so a purl-less finding still matches."""
    assert matches_key(produced(), key_entry(component=None))


def test_the_component_join_is_byte_for_byte_so_percent_encoding_matters() -> None:
    """The key spells the purl as the SBOM writes it; no decoding rescues a near-miss."""
    assert not matches_key(produced(purl="pkg:npm/@langchain/community@0.3.3"),
                           key_entry(component=COMPONENT_PURL))
