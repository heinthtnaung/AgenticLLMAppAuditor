"""Reading an inline chat message back off the tree, and the node order that reaches it.

The detector reports the message dict as a surface; this is the other half.
`template_text` reads the same `content` value back out, so the model is shown
the text that actually reaches it rather than the whole literal with its role,
its keys and its braces around it -- a question about punctuation nobody wrote.

`_node_at` is pinned here too, and it is not incidental. Without `ast.Dict` in
`PROMPT_NODES` the dict branch of `template_text` is unreachable, every inline
message answers "", and the probe refuses each one as *"the template's text is
not written literally at this line"* -- a surface reported and never judged. The
*order* carries as much as the membership: a call wins over the dict inside it,
so `create(messages=[{...}])` written on one line is still read as the call, and
that is decided here rather than by `ast.walk`, whose order is an accident of
tree shape.

Its own file rather than a section of `test_semantic_probe_reading.py`, which is
at rule 18's ~200-line ceiling. Every tree comes from a file the test writes into
`tmp_path`, and a one-file synthetic app is weaker than a real one: nothing
oversized, nothing malformed, no message shape nobody thought of.
"""

import ast

from artifacts.finding import REFUTED
from artifacts.surface import PROMPT_TEMPLATE, Surface
from checks.semantic_probe import (
    PROMPT_NODES,
    STATIC_REFUTATION,
    _node_at,
    interpolates_anything,
    judge,
    template_text,
)
from parsing.extractor_python import parse_file
from parsing.languages import PYTHON
from semantic_probe_fixtures import FILE, Answering, write_app

# The surface name the detector gives every one of these, spelled out because
# the probe never reads it back: nothing but this ties the two halves' vocabulary
# together in one file.
INLINE_NAME = "inline_message"

# A message dict on its own line inside a chat call: the shape the whole change
# is about, and the one line a real surface is anchored on.
INLINE_MESSAGE_APP = '''reply = client.chat(
    messages=[
        {"role": "user", "content": f"Analyze this: {content}"},
    ],
)
'''
MESSAGE_LINE = 3
MESSAGE_TEXT = "Analyze this: {content}"

# The same shape carrying fixed text, so the check's own verdict is reached on a
# message rather than on a template constructor.
STATIC_MESSAGE_APP = '''history = [
    {"role": "system", "content": "You summarise web pages."},
]
'''
STATIC_LINE = 2
STATIC_TEXT = "You summarise web pages."

# A dict that is not a message. Its own line, so the dict really is what gets
# read: written as `roles = {...}` the assignment would answer first and this
# would pass without `_message_text` running at all.
NO_CONTENT_KEY_APP = '''history = [
    {"role": "admin", "name": "ops"},
]
'''
NO_CONTENT_KEY_LINE = 2

# One line holding a call, an assignment and the dict inside both.
CALL_AND_DICT_APP = ('reply = client.chat(messages=['
                     '{"role": "user", "content": f"Analyze this: {content}"}])\n')

# One line holding an assignment and the dict it binds, and no call at all.
ASSIGN_AND_DICT_APP = 'message = {"role": "user", "content": f"Analyze this: {content}"}\n'

# What the probe must read out of that line: the message's content, not the
# whole literal and not "".
ASSIGN_AND_DICT_TEXT = "Analyze this: {content}"

ONE_LINE = 1

# A stand-in that would flag anything at all, so a refusal below can only have
# been reached without asking it.
FLAGGING_REPLY = "VULNERABLE\nThe message drops a value into the instructions."


def tree_of(tmp_path, source: str) -> ast.AST:
    """Write the source into an empty repository and parse it the way an audit does."""
    return parse_file(write_app(tmp_path, source) / FILE)


def message_surface(line: int) -> Surface:
    """The surface the detector reports for an inline message, built for `judge` to take."""
    return Surface(PROMPT_TEMPLATE, INLINE_NAME, FILE, line, PYTHON,
                   detail="inline dict message with string")


def test_template_text_reads_the_content_an_inline_message_carries(tmp_path) -> None:
    """The text judged is the message's own content, without its role or its braces."""
    tree = tree_of(tmp_path, INLINE_MESSAGE_APP)
    assert template_text(tree, MESSAGE_LINE) == MESSAGE_TEXT


def test_the_text_it_reads_keeps_the_interpolation_point_intact(tmp_path) -> None:
    """That pairing is the finding: text that is instructions, with a runtime value in it."""
    text = template_text(tree_of(tmp_path, INLINE_MESSAGE_APP), MESSAGE_LINE)
    assert interpolates_anything(text) is True


def test_a_static_message_is_read_and_then_refuted_without_asking_a_model(tmp_path) -> None:
    """Read, not unread: the text arrives whole, holds no runtime value, and settles it.

    The difference that matters is against an empty read. Both end in no
    finding, but "" is an inconclusive probe -- nobody looked -- while this is
    the one verdict the check reaches on its own.
    """
    text = template_text(tree_of(tmp_path, STATIC_MESSAGE_APP), STATIC_LINE)
    assert text == STATIC_TEXT
    assert interpolates_anything(text) is False
    ask = Answering(FLAGGING_REPLY)
    finding, probe = judge(message_surface(STATIC_LINE), text, ask)
    assert finding is None
    assert (probe.outcome, probe.detail) == (REFUTED, STATIC_REFUTATION)
    assert ask.prompts == []


def test_a_line_holding_a_call_and_a_dict_is_read_as_the_call(tmp_path) -> None:
    """`create(messages=[{...}])` on one line is the call, not the message inside it.

    The preference every existing template rests on: a constructor's argument is
    where the text lives. What it costs is on the next line -- the argument here
    is a list `_render` cannot rebuild, so the probe records that it read
    nothing rather than judging the message.
    """
    tree = tree_of(tmp_path, CALL_AND_DICT_APP)
    assert isinstance(_node_at(tree, ONE_LINE), ast.Call)
    assert template_text(tree, ONE_LINE) == ""


def test_a_message_bound_to_a_name_is_read_through_to_its_content(tmp_path) -> None:
    """The assignment still wins the line, and the probe reads the message inside it.

    This pinned `""` when it was written, with a docstring calling that the
    honest cost of the ordering. It was worse than a cost: the detector anchors
    a surface on this line, so `judge` published "the template's text is not
    written literally at this line" about a line where the text is plainly
    there -- the same false-probe defect fixed in `taint` for name reuse.
    `template_text` reads through an assignment whose value is a message dict,
    so the sentence is true again.
    """
    tree = tree_of(tmp_path, ASSIGN_AND_DICT_APP)
    assert isinstance(_node_at(tree, ONE_LINE), ast.Assign)
    assert template_text(tree, ONE_LINE) == ASSIGN_AND_DICT_TEXT


def test_a_dict_with_no_content_key_reads_as_no_text(tmp_path) -> None:
    """Not every dict on a surface line is a message, and one that is not carries nothing."""
    tree = tree_of(tmp_path, NO_CONTENT_KEY_APP)
    assert isinstance(_node_at(tree, NO_CONTENT_KEY_LINE), ast.Dict)
    assert template_text(tree, NO_CONTENT_KEY_LINE) == ""


def test_the_dict_is_the_last_preference_the_probe_reads_a_line_for() -> None:
    """Cheap guard on the tuple itself: dropping `ast.Dict` makes the branch above unreachable."""
    assert PROMPT_NODES == (ast.Call, ast.Assign, ast.Dict)
