"""Every element the page fixes is either portalled to the body or written at the shell.

`position: fixed` means "against the viewport" only while no ancestor
establishes a containing block, so a fixed element is correct only *in the
company it keeps*. This file is the fence on that: it enumerates every class the
stylesheets fix, and holds that each one's markup is somewhere the ancestry is
known -- portalled out to `document.body`, or written at the shell where
nothing wraps it but the page frame. `test_modal_containment.py` reasons about
the one chain that made the portal necessary; this catches the next instance
rather than that one.

**The frame itself is asserted to establish nothing, and that is the half a
portal rests on.** Handing markup to `document.body` helps only while `:root`,
`body` and `.shell` declare no `transform`, `filter`, `backdrop-filter`,
`perspective`, `will-change` or `contain`. A blur added to any of the three --
and this page already blurs four elements -- would put the modal back where it
was, with the portal still in place and every other test green.

**Why the fence is on the fixed side rather than the property side.** The
alternative was a sweep asserting every declaration of those six properties is
registered. It is over-reach, and the count is why: these stylesheets make
nineteen such declarations, of which eight are `@keyframes` steps and seven more
are a hover lift, a sliding knob, a rotating chevron, a pseudo-element arrow and
a blur on a decorative descendant. Only four sit on a class that can wrap
anything at all. A fence over the property would fire on decoration fifteen
times out of nineteen and teach a reader to add a line without thinking. A fence
over the *fixed* elements has three subjects, and grows only when someone fixes
something new -- which is exactly the moment the question arises.

The related over-reach is the blanket "every fixed element is portalled": two of
the three are correctly not portalled, and portalling the wave layer to satisfy a
test would be a design change no defect asks for.

**What this cannot do.** It does not lay the page out, so it cannot see where
anything ends up -- a portalled modal can still be mispositioned by a rule
nothing here reads, and whether the card is centred was checked by eye.
`css_rules.py` is not a cascade model either, so "the frame establishes nothing"
means no rule whose selector is exactly `:root`, `body` or `.shell` declares one,
not "nothing blurs the page frame". `docs/TODO.md` keeps both halves.

Reads the stylesheets and every component as text. No fastapi, no node, no build.
"""

from . import containing_blocks
from .css_rules import rules_selecting

# The elements that wrap the whole page. A containing block on any of these
# reaches the portalled modal *and* both shell-level fixed elements at once.
THE_PAGE_FRAME = (":root", "body", ".shell")

# Every class the stylesheets fix to the viewport, and where each one's markup
# has to be for that to keep meaning the window. The scrim is portalled because
# it opens from inside a card; the other two are written at the shell, where the
# frame above is all that wraps them.
PORTALLED = {"overlay": "Modal.jsx"}
AT_THE_SHELL = {"waves": "App.jsx", "source-link": "RepositoryLink.jsx"}

# The shell itself: the component that writes the outermost element, the class it
# writes, and the one file that renders it.
THE_SHELL = "App.jsx"
THE_SHELL_CLASS = "shell"
THE_ENTRY_POINT = ["main.jsx"]

# Which components the shell renders directly. Each shell-level fixed element
# must be written by one of these, or its ancestry is something else.
RENDERED_BY_THE_SHELL = ["App.jsx"]

# Floors, so a sweep that read nothing cannot pass as a sweep that found no
# fault. Nineteen establishing declarations across eleven classes today.
MINIMUM_ESTABLISHING_DECLARATIONS = 12
MINIMUM_ESTABLISHING_CLASSES = 8

# Planted below. The first three are declarations this page really makes and
# none of them establishes anything -- two spell a property name in another
# property's place, and `none` is the one value that establishes nothing. The
# fourth is the declaration the whole defect came from.
NOT_A_CONTAINING_BLOCK = ("text-transform: uppercase;",
                          "transition: transform 0.12s ease, background 0.18s ease;",
                          "transform: none;")
THE_DECLARATION_THAT_CAUSED_IT = "backdrop-filter: blur(14px);"


def frame_establishes(selector: str) -> list[str]:
    """Every containing-block property any rule gives one of the page's wrapping elements."""
    return [name for rule in rules_selecting(selector)
            for name in containing_blocks.establishing_declarations(rule.block)]


def portalling_components() -> list[str]:
    """Which components hand their markup to `document.body`, by file name."""
    return sorted(component.name for component in containing_blocks.components()
                  if containing_blocks.portals_to_the_body(component))


def components_mentioning_a_portal() -> list[str]:
    """Which components name `createPortal` at all, portalled or not."""
    return sorted(component.name for component in containing_blocks.components()
                  if containing_blocks.PORTAL_FUNCTION
                  in containing_blocks.source_of(component))


# --- the frame the portal lands in -------------------------------------------

def test_the_page_frame_establishes_no_containing_block() -> None:
    """A blur on any of these puts the portalled modal straight back under an ancestor."""
    for selector in THE_PAGE_FRAME:
        assert frame_establishes(selector) == [], selector


def test_the_page_frame_is_really_styled_by_rules_this_file_can_read() -> None:
    """Non-vacuity: a renamed frame would make the sweep above read nothing at all."""
    for selector in THE_PAGE_FRAME:
        assert rules_selecting(selector) != [], selector


# --- every fixed element is in one of the two registers -----------------------

def test_every_class_the_page_fixes_is_one_this_file_accounts_for() -> None:
    """A fourth fixed element is a fourth ancestry, and nothing else in the suite asks about it."""
    assert containing_blocks.classes_fixed_to_the_viewport() == set(PORTALLED) | set(AT_THE_SHELL)


def test_each_fixed_class_is_written_by_the_component_it_is_registered_to() -> None:
    """The join: a class that moved to another component has an ancestry nobody re-read."""
    for class_name, where in {**PORTALLED, **AT_THE_SHELL}.items():
        assert containing_blocks.components_writing(class_name) == [where], class_name


def test_the_portalled_fixed_element_is_rendered_by_a_component_that_portals() -> None:
    """Which is what takes it out from under the card it is opened from."""
    for class_name, where in PORTALLED.items():
        assert where in portalling_components(), class_name


def test_the_shell_level_fixed_elements_are_not_portalled() -> None:
    """Stated rather than assumed: they do not need it, and a portal would be cargo."""
    for class_name, where in AT_THE_SHELL.items():
        assert where not in portalling_components(), class_name


# --- and "at the shell" is a fact about the source, not a label ---------------

def test_the_shell_writes_the_outermost_element_of_the_page() -> None:
    """The frame the two un-portalled elements sit in is the one asserted above."""
    assert containing_blocks.components_writing(THE_SHELL_CLASS) == [THE_SHELL]


def test_the_shell_is_rendered_by_the_entry_point_and_nothing_else() -> None:
    """Anything between the root and the shell would be an ancestor this file never read."""
    assert containing_blocks.components_rendering("App") == THE_ENTRY_POINT


def test_each_shell_level_fixed_element_is_rendered_by_the_shell_itself() -> None:
    """A component moved into a card keeps its class and loses its ancestry silently."""
    for class_name, where in AT_THE_SHELL.items():
        if where == THE_SHELL:
            continue
        rendered_by = containing_blocks.components_rendering(where.removesuffix(".jsx"))
        assert rendered_by == RENDERED_BY_THE_SHELL, class_name


# --- one portal, and it is the modal's --------------------------------------

def test_the_modal_is_the_only_component_that_portals() -> None:
    """Two portals would be two scrims to keep in step, which is why the modal was extracted."""
    assert portalling_components() == sorted(set(PORTALLED.values()))


def test_no_other_component_so_much_as_names_a_portal() -> None:
    """An imported `createPortal` that is never returned renders in place and says nothing."""
    assert components_mentioning_a_portal() == sorted(set(PORTALLED.values()))


# --- the reader discriminates, on this page's own declarations ----------------

def test_the_establishing_sweep_read_the_whole_stylesheet() -> None:
    """Non-vacuity: an empty sweep satisfies the frame check above having read nothing."""
    assert len(containing_blocks.establishing_rules()) >= MINIMUM_ESTABLISHING_DECLARATIONS
    assert len(containing_blocks.classes_establishing_one()) >= MINIMUM_ESTABLISHING_CLASSES


def test_a_property_name_written_in_another_propertys_place_is_not_read_as_one() -> None:
    """Planted, from this page: `text-transform` and a transition naming `transform`."""
    for declaration in NOT_A_CONTAINING_BLOCK:
        assert containing_blocks.establishing_declarations(declaration) == [], declaration


def test_the_declaration_the_defect_came_from_is_read_as_one() -> None:
    """Planted: the three checks above return an empty list either way."""
    assert containing_blocks.establishing_declarations(THE_DECLARATION_THAT_CAUSED_IT) \
        == ["backdrop-filter"]
