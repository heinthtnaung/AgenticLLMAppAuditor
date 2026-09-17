"""What `key_drafting.draft` makes of a model's reply, including the replies it cannot read.

The model is handed the extracted surfaces and asked for a JSON array. It is a
model, so it will sometimes answer with prose, sometimes wrap the array in a
fence, and sometimes answer with something that is not an array at all. None of
those may raise: an unreadable reply means no entries, and
`compare_run.ensure_key` refuses to write an empty key rather than scoring
perfect recall over nothing.

The last section is the other half of that: a reply it *can* read, naming a
surface it was never shown or labelling an entry with a number. The parity
between the four fields that rule bounds is asserted against the rule itself --
`id` was the one it did not bound. What that cost is `test_drafted_key_ids.py`.

The `ask` here is a plain function the test writes, so no client and no server
is involved -- which is also what lets a test assert what the prompt contained.
"""

import json

import pytest

from artifacts.finding import OWASP_IDS
from ast_scan import get_call_keys, parse
from conftest import SRC_DIR
from artifacts.surface import PROMPT_TEMPLATE, TOOL_CALL, Surface
from keys.key_drafting import MAX_SURFACES, PROMPT, draft
from parsing.languages import PYTHON

FILE = "agent.py"
PROMPT_LINE = 6
TOOL_LINE = 7

# One entry in the shape the prompt asks for, written as a model would answer.
ENTRY = ('{"id": "K-01", "file": "agent.py", "line": 7, "owasp_id": "LLM06", '
         '"llm_surface": "TOOL_CALL", "surface_name": "ShellTool", "component": null, '
         '"detection": "static", "title": "A shell tool", "description": "why"}')
ARRAY = f"[{ENTRY}]"


def surfaces() -> list[Surface]:
    """The two surfaces every test below shows the model."""
    return [
        Surface(kind=PROMPT_TEMPLATE, name="ChatPromptTemplate.from_template", file=FILE,
                line=PROMPT_LINE, language=PYTHON, detail="", module=""),
        Surface(kind=TOOL_CALL, name="ShellTool", file=FILE, line=TOOL_LINE,
                language=PYTHON, detail="", module=""),
    ]


def answering(reply):
    """An `ask` that returns a fixed reply and records the prompt it was given."""
    seen: list[str] = []

    def ask(prompt: str):
        """Record the prompt and answer with whatever the test chose."""
        seen.append(prompt)
        return reply

    return ask, seen


def drafted(reply) -> list[dict]:
    """Draft against one canned reply and return the entries read out of it."""
    ask, _seen = answering(reply)
    return draft(surfaces(), ask, OWASP_IDS)


def refusing_ask(_prompt: str) -> str:
    """An `ask` that fails the test if a model is consulted at all."""
    raise AssertionError("the model was asked about a repository with no surfaces")


# --- the replies it can read --------------------------------------------------

def test_a_bare_array_yields_the_entry_the_model_named() -> None:
    """The happy path: one object in, one entry out, with its fields intact."""
    entries = drafted(ARRAY)
    assert [(entry["id"], entry["file"], entry["line"], entry["owasp_id"])
            for entry in entries] == [("K-01", FILE, TOOL_LINE, "LLM06")]


def test_an_array_wrapped_in_prose_and_a_fence_is_still_read() -> None:
    """Models pad their answers; the array is found by its brackets, not by position."""
    reply = f"Here is the key:\n\n```json\n{ARRAY}\n```\n\nHope that helps."
    assert [entry["id"] for entry in drafted(reply)] == ["K-01"]


# --- the replies it cannot ----------------------------------------------------

def test_a_reply_that_is_not_json_yields_no_entries() -> None:
    """Prose with no array is a failed answer, and a failed answer raises nothing."""
    assert drafted("I could not find any defects in this application.") == []


def test_a_reply_holding_broken_json_yields_no_entries() -> None:
    """Brackets are not a parse: a truncated array is unreadable, not half-readable."""
    assert drafted('[{"id": "K-01", "file": ') == []


def test_an_array_of_things_that_are_not_objects_yields_no_entries() -> None:
    """A key entry is an object; a list of strings names no defect the scorer can read."""
    assert drafted('["LLM01", "LLM06"]') == []


def test_a_reply_that_is_not_text_at_all_yields_no_entries() -> None:
    """`ask` promises a string; a client that broke that promise must not crash the run."""
    assert drafted(None) == []


def test_only_the_objects_in_a_mixed_array_are_kept() -> None:
    """One malformed element must not cost the reply its readable entries."""
    assert [entry["id"] for entry in drafted(f'["noise", {ENTRY}]')] == ["K-01"]


# --- what the model is shown --------------------------------------------------

def test_a_repository_with_no_surfaces_is_never_put_to_the_model() -> None:
    """Nothing to name a defect on, so there is nothing to ask and no call to pay for."""
    assert draft([], refusing_ask, OWASP_IDS) == []


def test_the_prompt_lists_each_surface_with_its_file_and_line() -> None:
    """The model may only anchor on what the extractor found, so it is shown exactly that."""
    ask, seen = answering(ARRAY)
    draft(surfaces(), ask, OWASP_IDS)
    assert f"- {TOOL_CALL} ShellTool at {FILE}:{TOOL_LINE}" in seen[0]
    assert f"- {PROMPT_TEMPLATE} ChatPromptTemplate.from_template at {FILE}:{PROMPT_LINE}" \
        in seen[0]


def test_the_prompt_names_every_risk_class_it_was_given() -> None:
    """The vocabulary comes from `artifacts.finding`, so the key cannot invent a class."""
    ask, seen = answering(ARRAY)
    draft(surfaces(), ask, OWASP_IDS)
    assert [risk for risk in OWASP_IDS if risk not in seen[0]] == []


def test_the_prompt_shows_no_more_surfaces_than_the_cap_allows() -> None:
    """A prompt naming every surface of a large app makes the model summarise, not read."""
    many = surfaces() * MAX_SURFACES
    ask, seen = answering(ARRAY)
    draft(many, ask, OWASP_IDS)
    listed = [line for line in seen[0].splitlines() if line.startswith("- ")]
    assert len(listed) == MAX_SURFACES


def test_the_prompt_is_the_one_the_module_declares() -> None:
    """Guard: the assertions above would pass against a prompt built anywhere else."""
    ask, seen = answering(ARRAY)
    draft(surfaces(), ask, OWASP_IDS)
    assert seen[0].startswith(PROMPT.split("{", 1)[0])


# --- what makes an entry grounded, field by field -----------------------------

# Every way one entry fails to be grounded, by the field that fails it. A table
# rather than four tests, because the claim is **parity**: `id` is bounded like
# the other three, and was not until a model reply labelled an entry `1` and the
# `(file, line, id)` sort raised `TypeError` out of a finished run. The off
# position is the first test in this file: the same entry, unmodified, is kept.
UNGROUNDED = {
    "owasp_id": {"owasp_id": "LLM99"},
    "file": {"file": "a-file-the-extractor-never-saw.py"},
    "line": {"line": 999},
    "id": {"id": 1},
}

# The module the guard reads the rule's fields off, rather than trusting the
# table above.
KEY_DRAFTING_SOURCE = SRC_DIR / "keys" / "key_drafting.py"

# One surface named twice, one entry labelled and one not. The reply that cost a
# finished run its drafted key.
MIXED_IDS = [{"id": 1}, {"id": "K-02"}]


def an_entry(**overrides) -> dict:
    """The entry above as a dict, with whichever fields a test replaces."""
    return {**json.loads(ENTRY), **overrides}


def reply_holding(*entries: dict) -> str:
    """A model reply naming these entries, in the array shape the prompt asks for."""
    return json.dumps([an_entry(**entry) for entry in entries])


@pytest.mark.parametrize("field", list(UNGROUNDED))
def test_an_entry_the_rule_cannot_ground_is_dropped(field: str) -> None:
    """Each field in turn: a risk class nobody named, a surface nobody found, a number for a label."""
    assert drafted(reply_holding(UNGROUNDED[field])) == []


def test_a_surface_named_twice_keeps_only_the_entry_that_was_labelled() -> None:
    """The measured reply, at the level that drops it rather than the one that sorted it.

    Dropped rather than renamed: an entry the model labelled with a number is an
    entry it did not label, and `K-04` invented for it names nothing.
    """
    assert [entry["id"] for entry in drafted(reply_holding(*MIXED_IDS))] == ["K-02"]


def test_every_field_the_grounding_rule_reads_has_a_row_in_that_table() -> None:
    """Read off `_is_grounded` itself, so a fifth field cannot be added without a case."""
    assert get_call_keys(parse(KEY_DRAFTING_SOURCE), "entry") == set(UNGROUNDED)
