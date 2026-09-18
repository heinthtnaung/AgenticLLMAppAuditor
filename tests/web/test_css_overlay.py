"""The run overlay really covers the page, in the one form a text sweep can hold.

What was asked for is a panel that "should popup and cover with position
fixed", and a stylesheet can fail that four ways without anything in this suite
noticing: not fixed, not stretched over the viewport, painted with a colour
literal that only suits one theme, or sitting under a layer that was already
there. So all four are asserted.

**Above everything, measured rather than assumed.** The overlay's `z-index` is
compared against *every other* `z-index` the page's stylesheets declare -- the
sticky form chrome, the source link, the bar, the content, the wave layer --
rather than against a number written here. A new layer added above it fails this
file, which is the only way a covering panel stays covering.

**The scrim is a token, and that is not tidiness.** A literal dark fill over a
light page is either invisible or far too heavy; `tokens.css` carries `--scrim`
in all three palettes and `test_css_theme_parity.py` holds that parity, so what
is left here is that the rule *uses* the token.

**The entrance animation is guarded.** `prefers-reduced-motion` is an
accessibility setting, not a preference to ignore, and an animation declared
outside the query would run for a reader who asked for none. The one
`animation` declaration is asserted to sit inside the query, and the keyframes
it names to exist -- an animation naming keyframes nothing defines is silent and
simply does not happen.

**The one styling hook that is not a class is joined here too, because nothing
else could.** The card's width is `data-wide={wide || undefined}` in
`Modal.jsx` against `.overlay__card[data-wide]` in this sheet. It was written as
a modifier class and moved to an attribute so that `overlay__card` itself would
stay in the static form the freshness join can read -- which is right, and took
the *modifier* out of every join in the suite: `test_built_page_shipped.py`
reads `className="..."` and nothing else, and the class sweep below joins
classes. Rename or drop either side and the file viewer silently opens at
44rem, with the whole suite green. So both ends are named: the attribute in the
component, and a rule that selects on it. Same join `test_css_viewer_frame.py`
makes for `.viewer__frame`, and for the same reason -- `.report-frame` outlived
its markup by a change under two tests that went on passing.

**The card has two consumers and the sweep reads both.** `RunOverlay.jsx`
stopped rendering a control of any kind on 2026-09-18, so `.overlay__actions` --
the row at the card's foot -- is now written only by `FileViewer.jsx`. The
selector stays named here and the file viewer joined the component list, because
the alternative was to stop naming it: that would leave a live rule with no test
joining it to any markup, which is precisely what `.report-frame` was when it
outlived its own component under two passing tests.

**And the classes the card renders are styled and static.** Unstyled markup is
the failure a `className`-to-bundle join cannot see: the name is in the JSX
whether a stylesheet mentions it or not. The static form is what
`test_built_page_shipped.py`'s freshness join can read at all -- a name
assembled in a template literal never appears whole in the build -- so that the
overlay's own names are written that way is asserted here, and the comparison
against `dist/` stays that file's job.

What this cannot do is lay the page out. A scrim tinted to transparency, a card
sized to nothing, a fixed layer with no height: all pass here and need an eye on
a rendered page. No test in this suite renders React or a browser, which is a
recorded defect and not one this file closes.

Reads the stylesheets and the four components that make the card as text. No
fastapi, no node, no build.
"""

import re

from . import css_rules
from .jsx_sweep import strip_comments

SHEET = "overlay.css"
OVERLAY = css_rules.FRONTEND_SRC / SHEET
# The card, and what the run overlay puts in it. `Modal.jsx` is first because
# the scrim and the card element moved there when the file viewer became a
# second consumer -- a list without it reads the run overlay for classes the
# run overlay no longer writes.
CARD_COMPONENTS = ("components/Modal.jsx", "components/RunOverlay.jsx",
                   "components/RunStamps.jsx", "components/FileViewer.jsx")

# The panel, the card in it, and the row of controls at its foot. The run
# overlay stopped rendering that row on 2026-09-18 -- it now offers no control
# at all -- so `FileViewer.jsx` is the only consumer left that writes it, and
# it is in the list above for that reason. A rule nothing renders is what the
# `.report-frame` regression was, and dropping the selector from this file
# instead would have left `.overlay__actions` exactly that on the day the file
# viewer stops using it too.
THE_SCRIM = ".overlay"
THE_CARD = ".overlay__card"
THE_ACTIONS = ".overlay__actions"

# What "covers the page" is, as declarations: taken out of the flow entirely,
# and stretched to every edge of the viewport.
COVERING = (("position", "fixed"), ("inset", "0"))

# The ground it paints, and the token it has to come from.
GROUND = "background"
SCRIM_TOKEN = "--scrim"

# The query an entrance animation belongs inside, and the property it sets.
MOTION_QUERY = "@media (prefers-reduced-motion: no-preference)"
ANIMATION = "animation"
KEYFRAMES = "@keyframes"

# A static class attribute -- the form `test_built_page_shipped.py` joins to the
# built bundle. The braced form is assembled at runtime and never appears whole.
STATIC_CLASS = re.compile(r'className="([^"{}]+)"')

# The card's width, which is an attribute rather than a class: the component
# that sets it, and the rule that selects on it. Neither end is reachable by any
# other sweep in this folder.
THE_CARD_COMPONENT = "components/Modal.jsx"
WIDE_ATTRIBUTE = "data-wide"
THE_WIDE_CARD = ".overlay__card[data-wide]"

# Floors, so a sweep that read nothing cannot pass as a sweep that found no
# fault. Six other z-indexes and twenty-one classes across the four components
# that make up the card today.
MINIMUM_OTHER_LAYERS = 4
MINIMUM_CLASSES = 6


def sheet() -> str:
    """The overlay's own stylesheet, comments stripped: they name properties in prose."""
    return css_rules.strip_comments(OVERLAY.read_text(encoding="utf-8"))


def one_rule(selector: str) -> css_rules.Rule:
    """The single rule for a selector, or say how many there really are."""
    found = css_rules.rules_selecting(selector)
    assert len(found) == 1, f"expected one `{selector}` rule, found {len(found)}"
    return found[0]


def declared_on(selector: str) -> list[tuple[str, str]]:
    """Every declaration every rule for one selector makes, in written order."""
    return [pair for rule in css_rules.rules_selecting(selector)
            for pair in css_rules.declarations(rule.block)]


def layers() -> dict[str, int]:
    """Every z-index the page's stylesheets declare, by the selector that declares it."""
    return {rule.selector: int(value) for rule in css_rules.all_rules()
            for name, value in css_rules.declarations(rule.block) if name == "z-index"}


def animations() -> list[str]:
    """Every `animation` value the overlay's stylesheet sets."""
    return css_rules.values_of(css_rules.rules_in(sheet(), SHEET), ANIMATION)


def classes_the_card_renders() -> set[str]:
    """Every class name the card's components write as a static attribute."""
    found: set[str] = set()
    for name in CARD_COMPONENTS:
        text = strip_comments((css_rules.FRONTEND_SRC / name).read_text(encoding="utf-8"))
        found |= {one for attribute in STATIC_CLASS.findall(text)
                  for one in attribute.split()}
    return found


def styled_classes() -> set[str]:
    """Every class name any of the page's stylesheets selects."""
    found: set[str] = set()
    for stylesheet in css_rules.stylesheets():
        text = stylesheet.read_text(encoding="utf-8")
        found |= css_rules.class_selectors_in(text, stylesheet.name)
    return found


# --- it covers the page --------------------------------------------------------

def test_the_scrim_is_taken_out_of_the_flow_and_stretched_to_every_edge() -> None:
    """What was asked for: fixed, and covering, rather than a panel the page grows."""
    declared = declared_on(THE_SCRIM)
    assert [pair for pair in COVERING if pair not in declared] == []


def test_the_scrim_is_painted_with_the_token_and_not_a_literal() -> None:
    """A dark fill written into the rule is wrong on a light page in one direction or the other."""
    painted = [value for name, value in declared_on(THE_SCRIM) if name == GROUND]
    assert painted == [f"var({SCRIM_TOKEN})"]


def test_the_scrim_sits_above_every_other_layer_the_page_declares() -> None:
    """Measured against the real layers: a panel under the sticky chrome does not cover."""
    found = layers()
    mine = found.pop(THE_SCRIM)
    assert [selector for selector, index in found.items() if index >= mine] == []


def test_the_layer_sweep_read_the_rest_of_the_page() -> None:
    """Non-vacuity: one z-index found would make the comparison above pass over nothing."""
    assert len(layers()) > MINIMUM_OTHER_LAYERS


# --- and it arrives without overriding a reader's settings ---------------------

def test_the_only_animation_is_inside_the_reduced_motion_query() -> None:
    """Outside it, a reader who asked for no motion gets motion anyway."""
    text = sheet()
    assert len(animations()) == 1
    assert MOTION_QUERY in text
    assert text.index(MOTION_QUERY) < text.index(f"{ANIMATION}:")


def test_the_animation_names_keyframes_the_stylesheet_defines() -> None:
    """An animation naming nothing simply does not happen, and says nothing about it."""
    named = animations()[0].split()[0]
    assert f"{KEYFRAMES} {named}" in sheet()


# --- the classes it renders are styled, and readable by the bundle sweep -------

def test_every_class_the_card_renders_has_a_rule_behind_it() -> None:
    """Unstyled markup is what a class-name-to-bundle join cannot see."""
    assert sorted(classes_the_card_renders() - styled_classes()) == []


def test_the_overlays_own_classes_are_written_in_the_static_form() -> None:
    """The form the freshness join reads: a name built in a template literal is invisible to it."""
    rendered = classes_the_card_renders()
    for selector in (THE_SCRIM, THE_CARD, THE_ACTIONS):
        assert selector.lstrip(".") in rendered, selector


def test_the_class_sweep_read_every_component_of_the_card() -> None:
    """Non-vacuity: an empty set satisfies the rule check above having read nothing."""
    assert len(classes_the_card_renders()) >= MINIMUM_CLASSES
    assert len(styled_classes()) > len(classes_the_card_renders())


# --- and the one hook that is not a class ------------------------------------

def test_the_card_sets_the_width_as_an_attribute_the_stylesheet_selects_on() -> None:
    """Both ends of a join nothing else in this folder makes: a rename leaves 44rem and green."""
    component = strip_comments(
        (css_rules.FRONTEND_SRC / THE_CARD_COMPONENT).read_text(encoding="utf-8"))
    assert WIDE_ATTRIBUTE in component, f"{THE_CARD_COMPONENT} sets no {WIDE_ATTRIBUTE}"
    assert one_rule(THE_WIDE_CARD).where == SHEET


def test_the_rule_for_the_wide_card_is_what_widens_it() -> None:
    """Non-vacuity: a rule that selected on the attribute and set nothing would pass above."""
    assert [name for name, _ in css_rules.declarations(one_rule(THE_WIDE_CARD).block)] \
        == ["max-width"]


def test_the_attribute_is_absent_rather_than_false_when_the_card_is_not_wide() -> None:
    """`data-wide="false"` is present, and `[data-wide]` would match it: the selector needs undefined."""
    component = strip_comments(
        (css_rules.FRONTEND_SRC / THE_CARD_COMPONENT).read_text(encoding="utf-8"))
    assert f"{WIDE_ATTRIBUTE}={{wide || undefined}}" in component


def test_every_selector_this_file_names_is_declared_in_the_overlays_own_sheet() -> None:
    """One sheet for one panel: a rule that moved elsewhere is a rule this file stops reading."""
    for selector in (THE_SCRIM, THE_ACTIONS):
        assert one_rule(selector).where == SHEET, selector
    assert {rule.where for rule in css_rules.rules_selecting(THE_CARD)} == {SHEET}
