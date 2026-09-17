"""Which declarations establish a containing block, and which elements the page fixes.

`position: fixed` resolves against the viewport only while **no ancestor
establishes a containing block** for it -- and `transform`, `filter`,
`backdrop-filter`, `perspective`, `will-change` and `contain` all establish one.
That is the mechanism behind the file viewer hanging off to the right of the
Download rail rather than sitting on the window: `.card` declares
`backdrop-filter: blur(14px)`, and the viewer is opened from inside a card, so
`.overlay { position: fixed; inset: 0 }` was laid out from that card's top-left
corner.

Shared by the two files that assert something about it --
`test_modal_containment.py` for the one chain that made a portal necessary, and
`test_css_fixed_ancestry.py` for every fixed element the page renders -- for the
reason `css_rules.py` and `jsx_sweep.py` are shared: one reader, so the two
cannot drift into two ideas of what establishes a containing block, and the
reasoning about what each invariant proves stays in the file that asserts it.

**What it cannot do, and every caller must allow for it.**

- It is not a DOM and it does not lay anything out. It reads which component
  writes a class and which component renders which, as text, so "inside a card"
  is always a claim about source order within one file. Whether the modal is
  actually centred on the window is not knowable here, and no test in this suite
  can say it -- `docs/TODO.md` keeps that row.
- A `transform` inside `@keyframes` is reported against the keyframe step
  (`from`, `to`) rather than against the element that runs the animation, so an
  animated containing block is invisible here. `.overlay__card`'s entrance
  animation is one of those, and nothing fixed is rendered inside that card.
- A value of exactly `none` is excluded, which is what keeps `transform: none`
  out. Nothing finer is modelled: `will-change: opacity` establishes nothing and
  is counted here anyway, which is an over-count by choice -- a `will-change` on
  an ancestor of a fixed element is worth a reader's eye whatever its value.
- Only static `className="..."` attributes are read. A class assembled in a
  template literal never appears whole, the same false negative
  `test_built_page_shipped.py` records for its freshness join.
"""

import re
from pathlib import Path

from . import css_rules
from .jsx_sweep import strip_comments

# The properties that make an element the containing block for a fixed
# descendant. Matched as declaration *names* only, which is what keeps
# `text-transform: uppercase` and `transition: transform 0.12s ease` out -- both
# are in these stylesheets, and neither establishes anything.
CONTAINING_BLOCK_PROPERTIES = ("transform", "filter", "backdrop-filter",
                               "perspective", "will-change", "contain")

# The one value that establishes nothing, whichever property carries it.
ESTABLISHES_NOTHING = "none"

# What "against the viewport" is written as.
POSITION = "position"
FIXED = "fixed"

# A static class attribute, and one component rendering another. Both are the
# forms this project's own JSX is written in.
STATIC_CLASS = re.compile(r'className="([^"{}]+)"')

# The whole portal call, target and all: markup handed to `document.body`
# instead of being returned in place.
PORTAL_CALL = re.compile(r"return createPortal\(\(.*\), (document\.body)\);", re.DOTALL)
PORTAL_FUNCTION = "createPortal"


def establishing_rules() -> list[tuple[css_rules.Rule, str]]:
    """Every rule that establishes a containing block, paired with the property that does it."""
    return [(rule, name) for rule in css_rules.all_rules()
            for name in establishing_declarations(rule.block)]


def establishing_declarations(block: str) -> list[str]:
    """The properties in one rule body that make its element a containing block."""
    return [name for name, value in css_rules.declarations(block)
            if name in CONTAINING_BLOCK_PROPERTIES and value != ESTABLISHES_NOTHING]


def classes_establishing_one() -> set[str]:
    """Every class name whose rules establish a containing block for a fixed descendant."""
    return {name for rule, _ in establishing_rules()
            for name in css_rules.CLASS_SELECTOR.findall(rule.selector)}


def rules_fixed_to_the_viewport() -> list[css_rules.Rule]:
    """Every rule that takes its element out of the flow and fixes it."""
    return [rule for rule in css_rules.all_rules()
            if (POSITION, FIXED) in css_rules.declarations(rule.block)]


def classes_fixed_to_the_viewport() -> set[str]:
    """Every class name the stylesheets position fixed."""
    return {name for rule in rules_fixed_to_the_viewport()
            for name in css_rules.CLASS_SELECTOR.findall(rule.selector)}


def components() -> list[Path]:
    """Every component the page's own source ships, in a stable order."""
    found = sorted(css_rules.FRONTEND_SRC.rglob("*.jsx"))
    assert found, f"no component under {css_rules.FRONTEND_SRC}; the page has no source"
    return found


def source_of(component: Path) -> str:
    """One component's source with its comments gone: they name these properties in prose."""
    return strip_comments(component.read_text(encoding="utf-8"))


def static_classes_in(component: Path) -> set[str]:
    """Every class name one component writes as a static attribute."""
    return {one for attribute in STATIC_CLASS.findall(source_of(component))
            for one in attribute.split()}


def components_writing(class_name: str) -> list[str]:
    """Which components render an element carrying this class, by file name."""
    return sorted(component.name for component in components()
                  if class_name in static_classes_in(component))


def components_rendering(component_name: str) -> list[str]:
    """Which components render this one as an element, by file name."""
    element = re.compile(rf"<{component_name}\b")
    return sorted(source.name for source in components()
                  if element.search(source_of(source)))


def portals_to_the_body(component: Path) -> bool:
    """Whether one component hands its markup to `document.body` rather than rendering in place."""
    return PORTAL_CALL.search(source_of(component)) is not None
