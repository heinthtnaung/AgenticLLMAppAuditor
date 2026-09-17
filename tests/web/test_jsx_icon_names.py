"""Every icon the page asks for by name exists, and a name that does not is shown.

`Icon.jsx` looks a name up in a table of hand-drawn paths. The lookup is the
same silent boundary the accessor sweep exists for: a misspelt name is not an
error, it is simply no path -- so before the fallback below, `<Icon
name="pacakge" />` rendered an empty `<svg>`, which is a typo nobody finds.
Two halves are asserted here, and the second is what makes the first safe to
rely on.

**There are two tables, and a name may be in either.** `PATHS` holds the line
icons and `MARKS` holds the filled brand marks, kept apart because the
difference is real -- a 20-unit stroke against a 24-unit filled path nobody here
drew. This file reads both through `icon_tables.icon_names`, since the question
it asks is "can the component draw this name", which is true of either table.
What keeps them apart is `test_jsx_icon_marks.py`'s subject, not this one's.
Reading only `PATHS` is what this file used to do, and it reported the GitHub
mark as a name no icon set has -- a genuine second source of names, found by the
check rather than by a person.

**The names asked for.** Swept out of the JSX as text, from three spellings the
components really use: `<Icon name="download" />`, the literals inside a
`name={...}` expression (`name={dark ? "dark" : "light"}`), and the `icon`
props and object fields that feed `<Icon name={icon} />` -- `<Stat icon="finding" />`
and the `icon:` field of a nav entry. A name reaching the component through any
*other* variable is outside this and would be caught only by the fallback, which
is the argument for having one; the floor below is what keeps a sweep that
matched nothing from passing.

**The fallback.** A name with no path draws a bordered square with the missing
name in its `title`, rather than nothing at all. That element needs a class of
its own, a rule behind it, and something in that rule that gives an empty
element a visible box -- otherwise the fallback is itself invisible and the
whole point of it is gone.

Both directions hold: every name a component asks for has a path, and every
path is one some component asks for.

No fastapi and no node: this reads the JSX and the stylesheets as text, through
`jsx_sweep.strip_comments`, so an icon named in a comment is not counted as one
the page asks for.
"""

import re

from .icon_tables import FRONTEND_SRC, ICON, icon_names, icon_source
from .jsx_sweep import strip_comments

# One `<Icon ... />` element with its attributes. The tables themselves are read
# by `icon_tables.py`, which both icon files share.
ICON_ELEMENT = re.compile(r"<Icon\s([^>]*?)/>", re.DOTALL)

# The name an element asks for: a literal, or an expression that may hold some.
NAME_ATTRIBUTE = re.compile(r'name=(?:"([^"]*)"|\{([^}]*)\})')
STRING_LITERAL = re.compile(r'"([^"]*)"')

# The two spellings that feed `<Icon name={icon} />`: a prop and an object field.
ICON_VALUE = re.compile(r'\bicon(?:=|:\s*)"([^"]*)"')

# The fallback the component draws for a name it has no path for, and what a
# stylesheet has to say about it for an empty element to show at all.
UNKNOWN_CLASS = "icon--unknown"
SIZING_CLASS = "icon"
VISIBLE_BY = ("border", "outline", "background")

# The name is interpolated into the title, so the page says which one is missing.
TITLE_NAMES_IT = "`no icon: ${name}`"

# A floor under the sweep: twelve reads of eleven names across five components
# today, and it has only ever gone up as the page grew.
MINIMUM_NAMES_ASKED = 8

# A name no icon set has ever had, planted to show the sweep reports rather than
# tolerates one. This is the misspelling the fallback was written for.
NAME_THAT_DOES_NOT_EXIST = "pacakge"


def stylesheets() -> str:
    """Every stylesheet the page ships, concatenated: the classes are looked up here."""
    return "\n".join(sheet.read_text(encoding="utf-8")
                     for sheet in sorted(FRONTEND_SRC.rglob("*.css")))


def names_asked_in(text: str, where: str) -> list[tuple[str, str]]:
    """Every icon name one component asks for by literal, paired with its file."""
    asked = [(where, name) for name in ICON_VALUE.findall(text)]
    for attributes in ICON_ELEMENT.findall(text):
        asked += [(where, name) for name in _names_in_attribute(attributes)]
    return asked


def _names_in_attribute(attributes: str) -> list[str]:
    """The literals a `name=` attribute holds, whether bare or inside an expression."""
    found = NAME_ATTRIBUTE.search(attributes)
    if not found:
        return []
    literal, expression = found.groups()
    if literal is not None:
        return [literal]
    return STRING_LITERAL.findall(expression)


def names_asked() -> list[tuple[str, str]]:
    """Every icon name the page asks for, across every component, with its file."""
    asked: list[tuple[str, str]] = []
    for source in sorted(FRONTEND_SRC.rglob("*.jsx")):
        asked += names_asked_in(strip_comments(source.read_text(encoding="utf-8")),
                                source.name)
    return asked


def unknown(asked: list[tuple[str, str]]) -> list[str]:
    """Name every icon the set cannot draw, file and all, or return nothing."""
    defined = icon_names()
    return sorted({f"{where}: {name}" for where, name in asked if name not in defined})


def unknown_class_rule() -> str:
    """The stylesheet rule for the fallback element, or say that there is none."""
    found = re.search(rf"\.{UNKNOWN_CLASS}\s*\{{([^}}]*)\}}", stylesheets())
    assert found, f"no stylesheet defines .{UNKNOWN_CLASS}"
    return found.group(1)


# --- every name asked for is a name the set has -------------------------------

def test_every_icon_the_page_asks_for_by_name_exists() -> None:
    """A name with no path used to render an empty `<svg>`: silent in both directions."""
    assert unknown(names_asked()) == []


def test_the_sweep_read_the_names_the_components_ask_for() -> None:
    """Non-vacuity: an empty sweep would satisfy the check above having read nothing."""
    assert len(names_asked()) >= MINIMUM_NAMES_ASKED


def test_every_icon_element_the_page_writes_was_read_by_the_sweep() -> None:
    """An element shape this regex cannot parse is a request nothing above checked."""
    for source in sorted(FRONTEND_SRC.rglob("*.jsx")):
        text = strip_comments(source.read_text(encoding="utf-8"))
        assert text.count("<Icon ") == len(ICON_ELEMENT.findall(text)), source.name


def test_a_name_the_icon_set_has_no_path_for_is_reported_with_its_file() -> None:
    """Planted, because the sweep is a check that returns an empty list either way."""
    planted = [("TopBar.jsx", NAME_THAT_DOES_NOT_EXIST)]
    assert unknown(planted) == [f"TopBar.jsx: {NAME_THAT_DOES_NOT_EXIST}"]


# --- and a name it does not have is shown, not swallowed ----------------------

def test_an_unknown_name_renders_an_element_of_its_own() -> None:
    """The fallback's whole point: an invisible icon is a typo nobody finds."""
    assert UNKNOWN_CLASS in icon_source()


def test_the_fallback_element_has_a_rule_giving_it_something_to_show() -> None:
    """An empty span with no box is as invisible as the empty `<svg>` it replaced."""
    rule = unknown_class_rule()
    assert any(property_name in rule for property_name in VISIBLE_BY), rule


def test_the_fallback_keeps_the_class_that_gives_every_icon_its_size() -> None:
    """`.icon` carries the width and height, so the fallback needs it to have a size."""
    found = re.search(r'className=\{`([^`]*)`\}', icon_source())
    assert found, f"{ICON.name} builds no class name for its fallback"
    assert SIZING_CLASS in found.group(1).split()


def test_the_fallback_says_which_name_was_missing() -> None:
    """A dotted square with no name in it says something is wrong and not what."""
    assert TITLE_NAMES_IT in icon_source()


# --- and the reverse direction, which holds now -------------------------------

def test_every_icon_the_set_defines_is_one_the_page_renders() -> None:
    """No dead entry in either table: every path is one some component asks for.

    Held as a live assertion since `auto` and `clock` were deleted -- `auto` was
    the third position of the old three-state theme control and `clock` never
    had a caller. It was a strict xfail while they stood, so removing them is
    what turned the record into a guard.
    """
    assert sorted(icon_names() - {name for _, name in names_asked()}) == []
