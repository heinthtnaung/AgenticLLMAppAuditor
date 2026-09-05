"""What a snippet may not contain, rule by rule, on and off.

The prohibition on model-written fixes was replaced by a check on the model's
answer, and these are that check. Each rule is exercised twice: once with an
answer that breaks it, once with one that does not, because a guard that
refuses everything is as useless as one that refuses nothing.
"""

import pytest

from artifacts.advice_rules import MAX_SNIPPET_LINES, MAX_SNIPPETS_PER_FINDING, judge
from artifacts.remediation import (
    NAMES_APP_IDENTIFIER,
    REJECTED,
    SAFER_LABEL,
    SNIPPET_IS_A_DIFF,
    SNIPPET_LABELS,
    SNIPPET_TOO_LONG,
    UNKNOWN_LABEL,
    UNKNOWN_LANGUAGE,
    WRITTEN,
)
from parsing.languages import PYTHON
from remediation_fixtures import CLEAN_GUIDANCE, finding_record, snippet

# A component and a package url on the finding, so the two evidence fields that
# the default fixture leaves null are exercised as well.
COMPONENT = "langchain-community"
PURL = "pkg:pypi/langchain-community@0.2.1"
MODULE = "agent_runtime"

# The app's own top-level modules, passed in beside the finding's evidence.
APP_MODULES = ("tools", "transaction_db")


def evidence_finding() -> dict:
    """A finding carrying every evidence field a snippet may not quote back."""
    return finding_record(component_name=COMPONENT, purl=PURL, module=MODULE)


def judge_code(code: str, module_names: tuple[str, ...] = ()) -> tuple:
    """Judge one snippet of code against the fully-evidenced finding."""
    return judge(evidence_finding(), CLEAN_GUIDANCE, [snippet(code)], module_names)


def test_neither_snippet_label_reads_as_an_instruction_to_apply_it() -> None:
    """The vocabulary itself carries the boundary: both values name an illustration."""
    assert SNIPPET_LABELS
    assert all(label.startswith("illustration_of_") for label in SNIPPET_LABELS)


@pytest.mark.parametrize("label", ["apply_this_patch", "fix", ""])
def test_a_snippet_with_a_label_the_model_invented_is_refused(label: str) -> None:
    """The label is written by this code; one arriving from a model is not in the vocabulary."""
    assert judge(finding_record(), CLEAN_GUIDANCE, [snippet(label=label)]) == (
        REJECTED, UNKNOWN_LABEL, "label")


def test_a_snippet_with_no_label_at_all_is_refused() -> None:
    """A missing key must refuse rather than fall through to the code checks."""
    assert judge(finding_record(), CLEAN_GUIDANCE,
                 [{"language": PYTHON, "code": "value = run()"}]) == (
        REJECTED, UNKNOWN_LABEL, "label")


def test_clean_advice_is_accepted() -> None:
    """A guard that refused everything would be no guard at all."""
    assert judge_code("value = fetch_text()\nchecked = approve(value)") == (WRITTEN, None, None)


@pytest.mark.parametrize("code", [
    'ShellTool()',
    'source = open("app/agent.py")',
    'source = open("agent.py")',
    'requirements.append("langchain-community")',
    '# see pkg:pypi/langchain-community@0.2.1',
    'agent_runtime.start()',
])
def test_a_snippet_quoting_the_findings_own_evidence_is_refused(code: str) -> None:
    """Naming the surface, the file, its basename, the component, the purl or the module."""
    assert judge_code(code) == (REJECTED, NAMES_APP_IDENTIFIER, "code")


def test_a_snippet_naming_one_of_the_apps_own_modules_is_refused() -> None:
    """The app's modules are not in the finding, so they are passed in separately."""
    assert judge_code("tools.lookup(value)", APP_MODULES) == (
        REJECTED, NAMES_APP_IDENTIFIER, "code")


def test_a_snippet_naming_no_module_of_this_app_is_accepted() -> None:
    """A generic helper name must survive the module list, or nothing would pass."""
    assert judge_code("helpers.lookup(value)", APP_MODULES) == (WRITTEN, None, None)


@pytest.mark.parametrize("code", [
    "diff --git a/agent.py b/agent.py",
    "@@ -1,3 +1,4 @@\n context",
    "--- before\n+++ after",
    "+checked = approve(value)",
    "-value = raw_input()",
    "    + checked = approve(value)",
])
def test_a_snippet_in_patch_form_is_refused(code: str) -> None:
    """Anything a reader could feed to `git apply` is a patch, whatever it is called."""
    assert judge_code(code) == (REJECTED, SNIPPET_IS_A_DIFF, "code")


def test_a_snippet_that_merely_subtracts_is_not_a_patch() -> None:
    """The diff check keys on line starts, so arithmetic mid-line stays advice."""
    assert judge_code("remaining = budget - spent") == (WRITTEN, None, None)


def numbered_lines(count: int) -> str:
    """Return that many harmless, identifier-free lines of code."""
    return "\n".join(f"step_{index} = run()" for index in range(count))


def test_a_snippet_longer_than_the_cap_is_refused() -> None:
    """A snippet long enough to be a replacement module is a patch by volume."""
    assert judge_code(numbered_lines(MAX_SNIPPET_LINES + 1)) == (
        REJECTED, SNIPPET_TOO_LONG, "code")


def test_a_snippet_exactly_at_the_cap_is_accepted() -> None:
    """The cap is a maximum, not a limit one line below itself."""
    assert judge_code(numbered_lines(MAX_SNIPPET_LINES)) == (WRITTEN, None, None)


def test_more_snippets_than_the_cap_are_refused_on_the_list() -> None:
    """The volume rule applies to the answer as a whole, so it names `snippets`."""
    too_many = [snippet() for _ in range(MAX_SNIPPETS_PER_FINDING + 1)]
    assert judge(finding_record(), CLEAN_GUIDANCE, too_many) == (
        REJECTED, SNIPPET_TOO_LONG, "snippets")


def test_exactly_the_capped_number_of_snippets_is_accepted() -> None:
    """Two illustrations -- the problem and a safer pattern -- is the intended shape."""
    allowed = [snippet() for _ in range(MAX_SNIPPETS_PER_FINDING)]
    assert judge(finding_record(), CLEAN_GUIDANCE, allowed) == (WRITTEN, None, None)


@pytest.mark.parametrize("language", ["rust", "diff", "text", ""])
def test_a_snippet_in_an_unreadable_language_is_refused(language: str) -> None:
    """The fence language is part of the contract: only what the parser knows is allowed."""
    assert judge(finding_record(), CLEAN_GUIDANCE, [snippet(language=language)]) == (
        REJECTED, UNKNOWN_LANGUAGE, "language")


def test_a_snippet_with_no_language_at_all_is_refused() -> None:
    """A missing key must refuse rather than fall through to the code checks."""
    assert judge(finding_record(), CLEAN_GUIDANCE,
          [{"label": SAFER_LABEL, "code": "value = run()"}]) == (
        REJECTED, UNKNOWN_LANGUAGE, "language")


def test_an_answer_with_no_snippet_at_all_is_accepted() -> None:
    """Prose alone is a complete answer; snippets are optional even when written."""
    assert judge(finding_record(), CLEAN_GUIDANCE, []) == (WRITTEN, None, None)
