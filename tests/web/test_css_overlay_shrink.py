"""The overlay card may shrink, which is the only reason the text inside it scrolls.

The second half of the file viewer defect a screenshot caught: the card was
wider than its own `max-width` and wider than the window, and the *page* carried
a horizontal scrollbar. `.overlay__card` is a grid item of `.overlay`, so its
`min-width` defaults to `auto` -- which refuses to go below the content's
min-content width -- and `.viewer__text` is `white-space: pre`, whose min-content
width is its longest line. One long line in a json document was enough.

**Two rules, and neither works alone.** `min-width: 0` on the card lets it obey
its cap; `overflow: auto` on the `<pre>` is what then moves the text instead of
the page. Without the floor the card grows and the `<pre>` never has anything to
scroll; without the overflow the text spills out of a card that now stays put.
So both are asserted here, in one file, rather than as two lines nobody would
connect -- `test_css_layering.py` is the same shape, where the wave layer's index
and the fill moving off `body` are one fix in two places.

**The premises are asserted too, and one of them fires on a change that would
also fix the bug.** `.overlay` is a grid, which is what makes `min-width: auto`
the card's default; `.viewer__text` is unwrapped, which is what makes its
min-content width unbounded. Wrap the text and the defect is gone and this file
fails -- correctly, because what fails is the *reason* the floor is there, and
the answer is to re-read it rather than to keep a rule nobody can justify.
`test_css_viewer_frame.py` already has that shape.

**And both are joined to the built bundle, by value.**
`test_built_styles_shipped.py` joins *selectors* and says in its own docstring
that a changed value is invisible to it -- which for a two-declaration fix means
the source could be right and the committed `dist/` could still serve the defect,
with the whole suite green. `dist/` is committed on purpose, so that is a live
failure mode rather than a hypothetical one.

**What this cannot do.** Nothing here lays the page out, so a card that is
centred, clipped, or off the window all read the same -- and whether the modal
is actually centred was checked by eye, not here. `css_rules.py` is not a
cascade model, so these are claims about which rules exist; an `!important`
elsewhere would win and be invisible. The at-rule a rule sits inside is also
invisible, so the card's two rules read alike whether or not one is inside a
media query. `docs/TODO.md` keeps that row.

Reads the overlay stylesheet, one component and this project's own build output
as text. No fastapi, no node, no build step.
"""

import re

from .containing_blocks import source_of
from .css_rules import FRONTEND_SRC, REPO_ROOT, Rule, rules_selecting, values_of

SHEET = "overlay.css"
VIEWER = FRONTEND_SRC / "components" / "FileViewer.jsx"
BUILT_STYLESHEET = REPO_ROOT / "frontend" / "dist" / "assets" / "index.css"

# The grid, the item in it, and the text that pushed the item past its cap.
THE_SCRIM = ".overlay"
THE_CARD = ".overlay__card"
THE_TEXT = ".viewer__text"

# What makes the card a grid item at all, and so `min-width: auto` its default.
LAYOUT = "display"
A_GRID = "grid"

# The fix, and the value that is the whole of it. `auto` is the default this
# replaces and `min-content` would be the same defect spelled out.
FLOOR = "min-width"
FLOORED_AT = "0"

# The cap the content overrode, which is what the floor lets the card obey.
CAP = "max-width"

# The other half of the pair: the rule that moves the text instead of the page,
# and the one that makes the text's min-content width its longest line.
OVERFLOW = "overflow"
SCROLLS = "auto"
WRAPPING = "white-space"
UNWRAPPED = "pre"

# Floors, so a renamed class cannot satisfy these checks by being unreadable.
MINIMUM_CARD_RULES = 1
MINIMUM_TEXT_RULES = 2

# How the pair reads once Vite has been over it: no spaces, and the properties
# in whatever order the minifier settled on.
MINIFIED_FLOOR = f"{FLOOR}:{FLOORED_AT}"
MINIFIED_OVERFLOW = f"{OVERFLOW}:{SCROLLS}"

# Planted below, because two of the checks pass over an absence either way: the
# card as it was written before the fix, and the default spelled out, which is
# the same refusal to shrink under another name.
A_CARD_WITH_NO_FLOOR = Rule(SHEET, THE_CARD,
                            "width: 100%; max-width: 44rem; margin: auto;")
THE_DEFAULT_SPELLED_OUT = Rule(SHEET, THE_CARD, "min-width: auto;")


def declared(selector: str, property_name: str) -> list[str]:
    """Every value the rules for one selector give a property, in source order."""
    return values_of(rules_selecting(selector), property_name)


def rules_for(selector: str) -> list[Rule]:
    """Every rule selecting this, insisting the stylesheets still have one."""
    found = rules_selecting(selector)
    assert found, f"no stylesheet declares {selector}; the panel is built out of something else"
    return found


def built_declarations(class_name: str) -> str:
    """Everything the shipped stylesheet declares on rules that select this class."""
    assert BUILT_STYLESHEET.is_file(), \
        f"no built stylesheet at {BUILT_STYLESHEET}; run `npm run build` in frontend/"
    pattern = re.compile(rf"\.{class_name}\b[^{{}}]*\{{([^{{}}]*)\}}")
    found = pattern.findall(BUILT_STYLESHEET.read_text(encoding="utf-8"))
    assert found, f"the built stylesheet selects nothing called .{class_name}"
    return " ".join(found)


# --- the card is a grid item that may shrink ----------------------------------

def test_the_scrim_lays_its_card_out_as_a_grid_item() -> None:
    """The premise: a grid item's `min-width` defaults to `auto`, which is the whole defect."""
    assert A_GRID in declared(THE_SCRIM, LAYOUT)


def test_the_card_is_floored_at_zero_so_it_can_obey_its_own_cap() -> None:
    """The fix. Without it one long json line pushes the card past `max-width` and the window."""
    assert declared(THE_CARD, FLOOR) == [FLOORED_AT]


def test_the_card_is_capped_at_all_so_the_floor_has_something_to_hold_it_to() -> None:
    """Non-vacuity of a sort: a card with no cap could not be pushed past one."""
    assert declared(THE_CARD, CAP) != []


# --- and the text inside it is what scrolls -----------------------------------

def test_the_text_is_its_own_scroll_container() -> None:
    """The other half of the pair: reachable only while the card may shrink."""
    assert SCROLLS in declared(THE_TEXT, OVERFLOW)


def test_the_text_is_unwrapped_which_is_what_made_the_card_grow() -> None:
    """The premise. Wrap it and the defect is gone -- and this fails, which is the honest result."""
    assert declared(THE_TEXT, WRAPPING) == [UNWRAPPED]


def test_the_class_that_scrolls_is_the_one_the_viewer_renders() -> None:
    """A rule can outlive its markup by a whole change with every sweep still green."""
    assert f'className="{THE_TEXT.lstrip(".")} mono"' in source_of(VIEWER)


# --- both rules are in the sheet that owns the panel --------------------------

def test_both_halves_of_the_pair_are_declared_in_the_overlays_own_sheet() -> None:
    """A rule that moved elsewhere is a rule this file stops reading, silently."""
    for selector in (THE_CARD, THE_TEXT):
        assert {rule.where for rule in rules_for(selector)} == {SHEET}, selector


def test_the_sweep_read_the_rules_and_not_an_empty_stylesheet() -> None:
    """Non-vacuity: an unreadable selector satisfies every value check above."""
    assert len(rules_for(THE_CARD)) >= MINIMUM_CARD_RULES
    assert len(rules_for(THE_TEXT)) >= MINIMUM_TEXT_RULES


# --- and the pair is in the bundle that is actually served --------------------

def test_both_halves_of_the_pair_are_in_the_built_stylesheet() -> None:
    """A stale `dist/` serves the defect from a source that has been fixed, silently."""
    assert MINIFIED_FLOOR in built_declarations(THE_CARD.lstrip("."))
    assert MINIFIED_OVERFLOW in built_declarations(THE_TEXT.lstrip("."))


# --- the reader discriminates -------------------------------------------------

def test_a_card_with_no_floor_on_it_is_reported() -> None:
    """Planted, in the shape the card had: the check above compares a list either way."""
    assert values_of([A_CARD_WITH_NO_FLOOR], FLOOR) == []


def test_the_default_spelled_out_is_not_read_as_a_floor() -> None:
    """`min-width: auto` is the refusal to shrink, written down rather than inherited."""
    assert values_of([THE_DEFAULT_SPELLED_OUT], FLOOR) != [FLOORED_AT]


def test_the_floor_is_not_read_off_the_cap() -> None:
    """`min-width` and `max-width` differ by three characters and one is the defect."""
    assert values_of([A_CARD_WITH_NO_FLOOR], CAP) == ["44rem"]
