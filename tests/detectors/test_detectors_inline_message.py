"""The inline chat message: prompt text written straight into a dict, with no name.

`{"role": "user", "content": f"Analyze: {text}"}` is how an application calls an
OpenAI-style API directly, and until `_prompt_from_inline_message` shipped it
extracted nothing at all. The dict carries no name, so `_prompt_from_assignment`
had no hint to match against `PROMPT_NAME_HINTS`, and it is not a template
constructor, so `_prompt_from_call` never saw it either: a whole class of
application put untrusted text in front of a model and reported no prompt
surface, which means no check downstream had anything to read.

Half of what is asserted here is what must *not* become a surface. The detector
now looks at every dict in every audited file, so a rule a shade too generous
turns configuration, routing tables and API payloads into prompt templates, and
each one becomes text the semantic probe asks a model about.

Its own file rather than a section of `test_detectors_prompt_agent.py`, which
rule 18's ~200-line ceiling leaves no room in. Every tree is parsed from a
snippet written here, and a snippet is weaker than a real file: nothing
oversized, nothing malformed, no message shape nobody thought of.
"""

from detector_helpers import FILE, parse_snippet
from detectors.detectors import find_prompt_templates
from artifacts.surface import PROMPT_TEMPLATE

# What a reader of `surfaces.json` sees for one of these. Spelled out rather
# than imported, so renaming the constant in `detectors.py` shows up here as a
# changed published name instead of passing silently.
INLINE_NAME = "inline_message"
F_STRING_DETAIL = "inline dict message with f-string"
STRING_DETAIL = "inline dict message with string"

# One message written into an OpenAI-style call, the shape this detector exists
# for. The dict sits on its own line, which is where the surface is anchored.
INLINE_MESSAGE_SOURCE = '''
def summarise(page_text):
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": f"Summarise this page: {page_text}"},
        ],
    )
'''
INLINE_MESSAGE_LINE = 5

# The same shape with fixed text: a surface too, and a differently built one.
STATIC_MESSAGE_SOURCE = '''
history = [
    {"role": "system", "content": "You summarise web pages."},
]
'''
STATIC_MESSAGE_LINE = 2

# A prompt the class built for itself and the message that carries it. The dict
# names a string rather than writing one, so the assignment on line 3 is the
# surface and the message is not -- one fact, reported once.
NAMED_CONTENT_SOURCE = '''
class SupportAgent:
    def __init__(self, user):
        self.system_prompt = f"You are helping {user}."

    def ask(self, client):
        return client.chat(messages=[
            {"role": "system", "content": self.system_prompt},
        ])
'''
NAMED_PROMPT_LINE = 3

# A dict with no content key at all: a role table, not a message.
NO_CONTENT_KEY_SOURCE = 'roles = {"role": "admin", "name": "ops"}\n'

# `{**spread}` gives `ast.Dict` a `None` in `keys`, which is not a node and has
# no `.value`. Reading it as one raises, so the shape is here twice: alone, and
# beside a real content key that must still be found past it.
SPREAD_ONLY_SOURCE = 'payload = {**base_message}\n'
SPREAD_WITH_CONTENT_SOURCE = 'payload = {**base_message, "content": f"Summarise {page}"}\n'

# Content the tree cannot read as text: a list of parts, and a value a call
# returns. Neither is a literal, so neither is text this could show a model.
NON_TEXT_CONTENT_SOURCE = '''
first = {"role": "user", "content": ["one", "two"]}
second = {"role": "user", "content": load_prompt("brief.txt")}
'''

# Two messages in one call, which is what every chat request actually looks
# like. They differ in how each was built and in nothing else.
TWO_MESSAGES_SOURCE = '''
reply = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You summarise web pages."},
        {"role": "user", "content": f"Summarise this page: {page_text}"},
    ],
)
'''
TWO_MESSAGES_LINES = (4, 5)


def prompts_in(source: str) -> list:
    """Find the prompt surfaces in one snippet, the way an audit of a file would."""
    return find_prompt_templates(parse_snippet(source), FILE)


def test_finds_an_inline_message_built_from_an_f_string() -> None:
    """The message an app writes into its own API call is a PROMPT_TEMPLATE at the dict's line."""
    found = prompts_in(INLINE_MESSAGE_SOURCE)
    assert len(found) == 1
    assert (found[0].kind, found[0].name, found[0].file, found[0].line) == (
        PROMPT_TEMPLATE, INLINE_NAME, FILE, INLINE_MESSAGE_LINE)


def test_the_inline_message_detail_names_how_its_text_was_built() -> None:
    """`f-string` is the published word for it, and it is what tells two messages apart."""
    assert prompts_in(INLINE_MESSAGE_SOURCE)[0].detail == F_STRING_DETAIL


def test_finds_an_inline_message_written_as_a_plain_string() -> None:
    """A fixed system message is a surface too: the probe is what decides it is harmless."""
    found = prompts_in(STATIC_MESSAGE_SOURCE)
    assert len(found) == 1
    assert (found[0].name, found[0].line, found[0].detail) == (
        INLINE_NAME, STATIC_MESSAGE_LINE, STRING_DETAIL)


def test_a_message_naming_a_prompt_built_elsewhere_is_not_a_second_surface() -> None:
    """`{"content": self.system_prompt}` carries a name, not text: the assignment is the surface.

    Reported twice, the same prompt would be judged twice and counted twice, and
    the copy at the message would carry no text for the probe to read.
    """
    found = prompts_in(NAMED_CONTENT_SOURCE)
    assert [(surface.name, surface.line) for surface in found] == [
        ("system_prompt", NAMED_PROMPT_LINE)]


def test_a_dict_with_no_content_key_is_not_a_message() -> None:
    """Every dict in the file is walked now, so the content key is what makes one a message."""
    assert prompts_in(NO_CONTENT_KEY_SOURCE) == []


def test_a_spread_entry_is_skipped_rather_than_read_as_a_key() -> None:
    """`{**base}` puts `None` in `keys`: read as a node it raises, so this must return cleanly."""
    assert prompts_in(SPREAD_ONLY_SOURCE) == []


def test_a_content_key_written_after_a_spread_is_still_found() -> None:
    """The guard on the test above: skipping the `None` key must not stop the scan of the dict."""
    found = prompts_in(SPREAD_WITH_CONTENT_SOURCE)
    assert len(found) == 1
    assert (found[0].name, found[0].detail) == (INLINE_NAME, F_STRING_DETAIL)


def test_content_that_is_not_written_as_text_is_not_a_surface() -> None:
    """A list of parts and a call's return value are both text this cannot show a model."""
    assert prompts_in(NON_TEXT_CONTENT_SOURCE) == []


def test_each_message_in_one_call_is_its_own_surface_on_its_own_line() -> None:
    """The dict has no name, so the line is the only thing telling two messages apart."""
    found = prompts_in(TWO_MESSAGES_SOURCE)
    assert len(found) == 2
    assert {surface.line: surface.detail for surface in found} == {
        TWO_MESSAGES_LINES[0]: STRING_DETAIL,
        TWO_MESSAGES_LINES[1]: F_STRING_DETAIL,
    }
    assert {surface.name for surface in found} == {INLINE_NAME}
