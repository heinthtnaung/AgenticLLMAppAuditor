"""The three option tags are the three options, and what each costs actually reaches a reader.

The audit form offers three tags -- the semantic probe, a drafted key, model
comparison -- and each one costs something the reader is deciding about: a model
call, a file written, the audited source sent to a third party. Two agreements
make that work, and both fail silently.

**The keys are the request's own flags.** `PASS_THROUGH_FLAGS` in
`web/audit_request.py` is what becomes a command-line flag; a tag keyed on
anything else sets a field the request ignores, and the checkbox does nothing
with no error anywhere. `test_option_fields.py` holds the *form's initial
object* against the request; this holds the *tags* against it, which is a
different declaration in a different component.

**The model picker is gated on exactly those three.** `AuditRequest.refusals`
refuses a named local model when nothing would consult one -- an ordinary audit
makes no model call, so the name would be stored, replayed on a re-run and never
used. The page offers the picker only when one of the three is on, so it cannot
build that request at all. The two rules are written in two languages and the
sets have to be the same set; a page gated on fewer options offers a picker
whose value the server refuses, and the reader sees a 400 about a field they
were invited to fill in.

**A CSS tooltip is not announced, so the sentence rides twice.** `data-tip`
feeds `content: attr(data-tip)` on `.pick::after`, which is invisible to a
screen reader, so the same text is in `aria-label`. Three things have to line
up for the visible half to appear at all -- the attribute, the class the rule
selects, and the rule's own `content` -- and none of the three errors when it is
wrong; the tooltip simply never shows. The reveal is checked on focus as well as
hover, because a tag is a button and a keyboard reaches it.

Read as text: the JSX through `jsx_sweep.strip_comments`, the stylesheets
through `css_rules.py`, which finds rules and is not a cascade model. Nothing
here opens a browser, so whether the box is positioned where a reader can see it
is not shown. No fastapi and no node.
"""

import re

from audit_request import PASS_THROUGH_FLAGS

from .css_rules import declarations, rules_selecting
from .jsx_sweep import FRONTEND_SRC, strip_comments

OPTIONS_MENU = FRONTEND_SRC / "components" / "OptionsMenu.jsx"

# The option list the component declares, and one entry's key inside it.
OPTIONS_ARRAY = re.compile(r"const OPTIONS = \[(.*?)\n\];", re.DOTALL)
OPTION_KEY = re.compile(r'^\s*key: "([^"]*)",', re.MULTILINE)

# The one tag element, with its attributes.
TAG_ELEMENT = re.compile(r"<button key=\{option\.key\}(.*?)>", re.DOTALL)

# What gates the model picker: the page's own reading of "would anything here
# consult a model", which has to be the same three options the server names.
GATE = "OPTIONS.some((option) => values[option.key])"

# The class the tooltip rule selects, and what that rule must set for the
# attribute to render at all.
TAG_CLASS = ".pick"
TOOLTIP_RULE = ".pick::after"
CONTENT = "content"
FROM_THE_ATTRIBUTE = "attr(data-tip)"

# The two states the tooltip is revealed in. A button is focusable, so hover
# alone would put the sentence out of a keyboard reader's reach.
REVEALED_ON = (".pick:hover::after", ".pick:focus-visible::after")

# What each tag carries: the sentence, and the same sentence again where a
# screen reader will find it.
TIP_ATTRIBUTE = "data-tip={option.why}"
SPOKEN = "aria-label={`${option.name}. ${option.why}`}"


def menu_source() -> str:
    """The options component's own source, with its comments stripped."""
    return strip_comments(OPTIONS_MENU.read_text(encoding="utf-8"))


def option_keys() -> list[str]:
    """The keys the three tags set, in the order the component declares them."""
    found = OPTIONS_ARRAY.search(menu_source())
    assert found, f"{OPTIONS_MENU.name} declares no OPTIONS array this test can read"
    keys = OPTION_KEY.findall(found.group(1))
    assert keys, f"{OPTIONS_MENU.name}'s OPTIONS array has no entry this test can read"
    return keys


def tag_attributes() -> str:
    """The one tag element's attributes, insisting the component still renders one."""
    found = TAG_ELEMENT.search(menu_source())
    assert found, f"{OPTIONS_MENU.name} renders no option tag this test can read"
    return found.group(1)


def tooltip_declares(property_name: str) -> list[str]:
    """Every value the tooltip rule gives one property."""
    found = rules_selecting(TOOLTIP_RULE)
    assert found, f"no stylesheet declares {TOOLTIP_RULE}; the tag has no tooltip"
    return [value for rule in found
            for name, value in declarations(rule.block) if name == property_name]


# --- the tags are the request's own options -----------------------------------

def test_the_tags_set_exactly_the_options_the_request_turns_into_flags() -> None:
    """A tag keyed on anything else is a checkbox that does nothing, with no error."""
    assert set(option_keys()) == set(PASS_THROUGH_FLAGS)


def test_there_are_as_many_tags_as_options() -> None:
    """Said as a count too, so two entries sharing a key cannot pass the set check above."""
    assert len(option_keys()) == len(PASS_THROUGH_FLAGS)


def test_the_model_picker_is_gated_on_those_same_options() -> None:
    """So the page cannot build the request `AuditRequest.refusals` would refuse.

    The server refuses a named local model when nothing would consult one. The
    page derives "would anything consult one" from the same three options rather
    than from a second hand-written list, which is what keeps the two rules one
    rule.
    """
    assert GATE in menu_source()


# --- and what each one costs reaches a reader ---------------------------------

def test_every_tag_carries_its_sentence_as_an_attribute() -> None:
    """The visible half. `title` was tried and waits about a second, which is too long here."""
    assert TIP_ATTRIBUTE in tag_attributes()


def test_every_tag_carries_the_same_sentence_where_it_will_be_announced() -> None:
    """A CSS-generated box is not in the accessibility tree at all, so it rides twice."""
    assert SPOKEN in tag_attributes()


def test_the_tag_wears_the_class_the_tooltip_rule_selects() -> None:
    """Three things must line up and none of them errors: this is the middle one."""
    assert f'className={{`{TAG_CLASS.lstrip(".")}' in tag_attributes()


def test_the_tooltip_renders_the_attribute_rather_than_fixed_text() -> None:
    """A rule with its own `content` would show one sentence under all three tags."""
    assert tooltip_declares(CONTENT) == [FROM_THE_ATTRIBUTE]


def test_the_tooltip_is_revealed_on_focus_as_well_as_hover() -> None:
    """A tag is a button, so hover alone puts its cost out of a keyboard reader's reach."""
    for selector in REVEALED_ON:
        assert rules_selecting(selector), selector


def test_the_tag_itself_has_a_rule_so_the_tooltip_can_be_placed_against_it() -> None:
    """`position: relative` on the tag is what `bottom: calc(100% + 8px)` is measured from."""
    assert "relative" in [value for rule in rules_selecting(TAG_CLASS)
                          for name, value in declarations(rule.block)
                          if name == "position"]
