"""What the prose half of an answer may not contain.

Prose is the other channel a model can write into, and for a while it was the
unwatched one: a whole unified diff reads as a paragraph, and rendered into
`remediation.md` with none of the warnings a snippet gets. So every patch-shaped
rule is exercised here as well -- diff form, both fence markers, an indented
block -- each with the off position that stops the rule over-reaching. A foreign
OWASP id is refused too, because `remediation.json` has no classification field
to check a re-classification against. Naming its own class, and its own file, is
allowed and useful, so that is asserted rather than left to chance.
"""

import pytest

from artifacts.finding import OWASP_IDS
from artifacts.advice_rules import MAX_GUIDANCE_CHARS, MAX_SNIPPET_LINES, judge
from artifacts.remediation import (
    CODE_FENCE_IN_GUIDANCE,
    EMPTY_ANSWER,
    GUIDANCE_TOO_LONG,
    RECLASSIFIES,
    REJECTED,
    SNIPPET_IS_A_DIFF,
    SNIPPET_TOO_LONG,
    WRITTEN,
)
from remediation_fixtures import CLEAN_GUIDANCE, finding_record, snippet

# The finding every case below is judged against, so "its own id" is well defined.
OWN_RISK = "LLM06"
FOREIGN_RISKS = [risk for risk in OWASP_IDS if risk != OWN_RISK]

# Long, but with no fence, no risk id and no identifier: only the length is wrong.
PADDING_WORD = "reviewed "

# A patch a reader could feed to `git apply`, written as a paragraph and fenced
# by nothing. This is the shape the guard used to let through.
UNFENCED_DIFF = """--- a/src/main.py
+++ b/src/main.py
@@ -12,3 +12,4 @@ def handle(query):
 answer = agent.run(query)
-return answer
+return sanitise(answer)"""


def judge_prose(guidance: str) -> tuple:
    """Judge prose against a finding classified as the app's own risk class."""
    return judge(finding_record(owasp_id=OWN_RISK), guidance, [snippet()])


def test_clean_prose_is_accepted() -> None:
    """The accepted path, so every refusal below is a refusal of something specific."""
    assert judge_prose(CLEAN_GUIDANCE) == (WRITTEN, None, None)


@pytest.mark.parametrize("guidance", ["", "   ", "\n\t "])
def test_prose_that_says_nothing_is_refused(guidance: str) -> None:
    """An empty answer is recorded as one, never as advice a reader could act on."""
    assert judge_prose(guidance) == (REJECTED, EMPTY_ANSWER, "guidance")


def test_prose_longer_than_the_cap_is_refused() -> None:
    """The volume cap applies to prose as well, and names the field it refused on."""
    long_enough = PADDING_WORD * (MAX_GUIDANCE_CHARS // len(PADDING_WORD) + 1)
    assert judge_prose(long_enough) == (REJECTED, GUIDANCE_TOO_LONG, "guidance")


def test_prose_just_under_the_cap_is_accepted() -> None:
    """The cap is a maximum, so an answer at its length still passes."""
    assert judge_prose(PADDING_WORD * (MAX_GUIDANCE_CHARS // len(PADDING_WORD))) == (
        WRITTEN, None, None)


def test_a_code_fence_smuggled_into_prose_is_refused() -> None:
    """A fence in prose is a snippet that skipped every snippet rule above."""
    assert judge_prose(f"{CLEAN_GUIDANCE}\n```python\nvalue = run()\n```") == (
        REJECTED, CODE_FENCE_IN_GUIDANCE, "guidance")


def test_even_a_bare_fence_marker_is_refused() -> None:
    """The check is on the marker, not on a well-formed block, so half a fence counts."""
    assert judge_prose(f"{CLEAN_GUIDANCE} ```") == (
        REJECTED, CODE_FENCE_IN_GUIDANCE, "guidance")


@pytest.mark.parametrize("foreign", FOREIGN_RISKS)
def test_prose_naming_another_risk_class_is_refused(foreign: str) -> None:
    """`remediation.json` has no classification field, so re-classifying happens in prose."""
    assert judge_prose(f"{CLEAN_GUIDANCE} Compare with {foreign}.") == (
        REJECTED, RECLASSIFIES, "guidance")


def test_prose_naming_the_findings_own_risk_class_is_accepted() -> None:
    """Its own class is the useful case: refusing it would gut the advice."""
    assert judge_prose(f"{CLEAN_GUIDANCE} This is a {OWN_RISK} problem.") == (
        WRITTEN, None, None)


def test_each_risk_class_is_foreign_only_to_the_others() -> None:
    """Every id in the vocabulary is its own finding's allowed id, not just LLM06."""
    for risk in OWASP_IDS:
        finding = finding_record(owasp_id=risk)
        assert judge(finding, f"{CLEAN_GUIDANCE} A {risk} issue.", []) == (WRITTEN, None, None)


def test_a_risk_id_inside_a_longer_word_does_not_reclassify() -> None:
    """The id check uses word boundaries, so a longer token is not a foreign class."""
    assert judge_prose(f"{CLEAN_GUIDANCE} The LLM01A convention is unrelated.") == (
        WRITTEN, None, None)


def test_prose_is_judged_before_any_snippet_is_looked_at() -> None:
    """A refused answer is refused whole, so the first reason reported is the prose one."""
    leaking = [snippet("ShellTool()")]
    assert judge(finding_record(owasp_id=OWN_RISK), "", leaking) == (
        REJECTED, EMPTY_ANSWER, "guidance")


def test_an_unfenced_diff_in_prose_is_refused_as_a_diff() -> None:
    """The hole this rule closed: a whole patch reads as a paragraph and skipped every check."""
    assert judge_prose(UNFENCED_DIFF) == (REJECTED, SNIPPET_IS_A_DIFF, "guidance")


def test_a_diff_buried_under_ordinary_prose_is_still_refused() -> None:
    """The refusal keys on any line in patch form, not on the answer opening with one."""
    assert judge_prose(f"{CLEAN_GUIDANCE}\n\n{UNFENCED_DIFF}") == (
        REJECTED, SNIPPET_IS_A_DIFF, "guidance")


def test_a_dash_used_as_punctuation_in_prose_is_not_a_diff() -> None:
    """The diff check keys on line starts, so a mid-sentence dash stays advice."""
    assert judge_prose("Validate the input - then call the model.") == (WRITTEN, None, None)


def test_a_tilde_fence_in_prose_is_refused_like_a_backtick_one() -> None:
    """Both markers open a block, so a guard watching one of them stops nothing."""
    assert judge_prose(f"{CLEAN_GUIDANCE}\n~~~python\nchecked = approve(value)\n~~~") == (
        REJECTED, CODE_FENCE_IN_GUIDANCE, "guidance")


def test_an_indented_block_in_prose_is_refused_as_a_fence() -> None:
    """Markdown renders four spaces as code, so an indented run is a block by another name."""
    assert judge_prose("Do this:\n    checked = approve(value)\n    run(checked)") == (
        REJECTED, CODE_FENCE_IN_GUIDANCE, "guidance")


def test_one_indented_line_alone_is_not_a_block() -> None:
    """The rule needs two consecutive lines, so a wrapped or padded sentence survives."""
    assert judge_prose("Do this:\n    checked = approve(value)\nThen run it.") == (
        WRITTEN, None, None)


def test_prose_naming_the_findings_own_file_and_surface_is_accepted() -> None:
    """Deliberate and documented: the reader has to be told where to look."""
    finding = finding_record(owasp_id=OWN_RISK)
    prose = f"Look at {finding['file']}, where {finding['surface_name']} is reached."
    assert judge(finding, prose, [snippet()]) == (WRITTEN, None, None)


def numbered_lines(count: int) -> str:
    """Return that many harmless, identifier-free lines of code."""
    return "\n".join(f"step_{index} = run()" for index in range(count))


def test_the_two_volume_reasons_are_distinct_values() -> None:
    """One reason for both channels would make the refusal counts unreadable."""
    assert GUIDANCE_TOO_LONG != SNIPPET_TOO_LONG


def test_each_volume_reason_names_the_channel_it_came_from() -> None:
    """Prose over the cap is a prose refusal; a long snippet is a snippet one."""
    long_prose = PADDING_WORD * (MAX_GUIDANCE_CHARS // len(PADDING_WORD) + 1)
    assert judge_prose(long_prose) == (REJECTED, GUIDANCE_TOO_LONG, "guidance")
    long_snippet = [snippet(numbered_lines(MAX_SNIPPET_LINES + 1))]
    assert judge(finding_record(owasp_id=OWN_RISK), CLEAN_GUIDANCE, long_snippet) == (
        REJECTED, SNIPPET_TOO_LONG, "code")
