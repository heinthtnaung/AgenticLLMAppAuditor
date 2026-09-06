"""`assigned_name`: the single name an assignment writes to, and when there is none.

The attribute half is worth stating plainly, because its absence was a real
blindspot. `assigned_name` has one caller, `_prompt_from_assignment`, which
matches what comes back against `PROMPT_NAME_HINTS` -- so while an attribute
target answered `""`, every prompt a class held on itself was invisible:
`self.system_prompt = f"...{user}..."` extracted no surface at all, in any
class-based application.

Both halves are pinned here, because a fix that answered for *every* target
would be as wrong as the miss and harder to see: a subscript, an unpack or two
targets name no single thing, and a name matched against a hint has to be a
name.
"""

import ast

import pytest
from parsing.ast_utils import assigned_name

# The shapes that name no single thing, each a statement a real file could
# hold. The names are prompt-shaped on purpose: were any of these to answer,
# the prompt detector would report a surface for it. A starred target is listed
# on its own even though it only ever parses inside a tuple, because that is
# how a reader writes it and how it has to keep answering.
NAMELESS_ASSIGNMENTS = {
    "subscript": 'holder["system_prompt"] = "be helpful"',
    "tuple unpack": 'system_prompt, greeting = "be helpful", "hello"',
    "starred": 'first, *system_prompt = ["be helpful"]',
    "two targets": 'system_prompt = fallback_prompt = "be helpful"',
}


def parse_assignment(source: str) -> ast.Assign:
    """Parse one statement and return it, failing loudly if it is not an assignment."""
    statement = ast.parse(source).body[0]
    assert isinstance(statement, ast.Assign), f"not an assignment: {source}"
    return statement


def test_plain_variable_answers_with_its_own_name() -> None:
    """A bare name target answers with the name it binds."""
    assert assigned_name(parse_assignment('system_prompt = "be helpful"')) == "system_prompt"


def test_instance_attribute_answers_with_its_last_segment() -> None:
    """`self.system_prompt` answers `system_prompt`, which is what the prompt hints match."""
    assert assigned_name(parse_assignment('self.system_prompt = "be helpful"')) == "system_prompt"


def test_nested_attribute_answers_with_its_last_segment() -> None:
    """Only the last segment: who holds the value is not part of what the value is."""
    node = parse_assignment('self.config.instruction_template = "be helpful"')
    assert assigned_name(node) == "instruction_template"


@pytest.mark.parametrize(
    "source", list(NAMELESS_ASSIGNMENTS.values()), ids=list(NAMELESS_ASSIGNMENTS)
)
def test_assignment_naming_no_single_thing_answers_empty(source: str) -> None:
    """A subscript, an unpack, a starred target and two targets all still answer ''."""
    assert assigned_name(parse_assignment(source)) == ""
