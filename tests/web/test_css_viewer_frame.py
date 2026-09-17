"""The frame an HTML artifact is shown in has to pin its own colour scheme.

This was `test_css_report_frame.py`, over `.report-frame` in `results.css`. That
rule is gone with the card that rendered it, and **the claim moved to
`.viewer__frame` in `overlay.css` wider than it was**: `FileViewer.jsx` decides
by suffix, so this is now the frame *any* `.html` file a run leaves on disk goes
into, rather than the two the report card framed by name.

It is one rule of three characters' consequence and it was a report nobody could
read, so it is worth the file. The chain:

1. `reporting/markdown_html.py` gives the exported document **no text colour and
   no background of its own**. That is deliberate -- the report is meant to be
   readable opened straight off disk, following whatever the reader's browser
   does -- and it declares `color-scheme: light dark` to say so.
2. An iframe inherits `color-scheme` from its embedder. This page's root is
   dark by default, so inside the frame the document's *default* text colour
   resolved to white.
3. The frame paints itself white, because a report is a document and a document
   is a page.

White text on a white background: the report rendered, the bytes were right,
and there was nothing to see. `color-scheme: light` on the frame is what makes
the document's own defaults resolve to dark text, and it changes nothing about
the bytes being displayed.

**The ground may not come from a theme token, and that is the sharper half.**
The old rule wrote `background: #fff` and the check under it was only that
*some* background was declared -- which the frame satisfied while the effective
declaration was `var(--page)`, the token that is nearly black in the dark
palette. A frame pinned to one colour scheme must not take its ground from a
palette that follows another, so the last background declared is asserted to be
a literal. A token that happened to be white in all three palettes would fail
here too, and should: `--page` is white in two of them, which is exactly how
this is missed by eye.

**Source order stands in for the cascade, and `css_rules.py` is not a cascade
model.** Two rules select this frame -- the shared scroll-container block and
the frame's own -- so "the last one wins" is read off the file. An `!important`
or a more specific selector in another sheet would beat it and nothing here
could see that.

**Both ends are asserted, because the rule is only load-bearing while the other
end stays as it is.** If the exported report ever grows a colour of its own, the
pin here becomes harmless rather than necessary -- and a reader looking at
either file alone could not tell. So `markdown_html.STYLE` is checked for the
absence this rule compensates for, and the failure message says which.

**And the class is joined back to the component that renders it.** That is this
file's own regression: `.report-frame` outlived its markup by a whole change and
these tests went on passing over a rule nothing rendered, because a stylesheet
sweep cannot tell a live rule from a dead one. Nothing else in the suite catches
removed CSS -- `test_built_styles_shipped.py` and `test_built_page_shipped.py`
both run source to bundle and say so.

Nothing here opens a browser, and the one thing no test in this suite can show
is what the pixels look like. No fastapi and no node.
"""

import re

from reporting.markdown_html import STYLE

from .css_rules import Rule, declarations, rules_selecting
from .jsx_sweep import FRONTEND_SRC, strip_comments

# The frame, the component that renders it, and the two declarations that make a
# document readable inside it.
FRAME = ".viewer__frame"
VIEWER = FRONTEND_SRC / "components" / "FileViewer.jsx"
SHEET = "overlay.css"
COLOUR_SCHEME = "color-scheme"
PINNED_TO = "light"
BACKGROUND = "background"

# How a value that follows the page's palette is written. The frame is pinned to
# one scheme, so its ground may not be one of these.
A_THEME_TOKEN = "var("

# What the exported report must *not* set, on pain of this rule being pointless.
# Matched against the document's own `body` rule, where a colour would go.
BODY_RULE = re.compile(r"body\s*\{([^}]*)\}")
COLOUR_PROPERTIES = ("color:", "background:", "background-color:")

# What the exported report declares instead: follow the embedder. Which is
# exactly why the embedder has to say something.
REPORT_FOLLOWS_THE_EMBEDDER = "color-scheme: light dark"

# Planted below, each for a check that passes over an absence either way. The
# second is the frame as it was written before this file's sharper half: a
# scheme pinned light over a ground that follows the palette.
PLANTED_COLOURED_BODY = "body { color: #fff; margin: 2rem auto; }"
PLANTED_THEME_GROUND = Rule(SHEET, FRAME,
                            "color-scheme: light; background: var(--page);")


def frame_rules() -> list[Rule]:
    """Every rule selecting the viewer's frame, insisting the page still has one."""
    found = rules_selecting(FRAME)
    assert found, f"no stylesheet declares {FRAME}; HTML is shown in something else now"
    return found


def frame_declares(property_name: str) -> list[str]:
    """Every value the frame's rules give one property, in the order the file declares them."""
    return [value for rule in frame_rules()
            for name, value in declarations(rule.block) if name == property_name]


def ground_of(rules: list[Rule]) -> str:
    """The background these rules end up with: the last one declared, by source order."""
    painted = [value for rule in rules
               for name, value in declarations(rule.block) if name == BACKGROUND]
    assert painted, f"{FRAME} declares no background at all"
    return painted[-1]


def exported_body_block() -> str:
    """The `body` rule of the document `markdown_html.py` writes."""
    found = BODY_RULE.search(STYLE)
    assert found, "markdown_html.STYLE no longer has a body rule this test can read"
    return found.group(1)


# --- the frame pins the scheme ------------------------------------------------

def test_the_viewer_frame_pins_its_colour_scheme_to_light() -> None:
    """The fix: without it the embedded document's default text colour is white."""
    assert frame_declares(COLOUR_SCHEME) == [PINNED_TO]


def test_the_viewer_frame_paints_itself_a_ground_of_its_own() -> None:
    """Which is the other half of the pair, and the half that made white text invisible."""
    assert frame_declares(BACKGROUND) != []


def test_the_ground_does_not_follow_the_pages_palette() -> None:
    """A frame pinned to one scheme may not take its ground from a palette on another."""
    painted = ground_of(frame_rules())
    assert A_THEME_TOKEN not in painted, (
        f"{FRAME} ends up painted {painted}, which follows the theme while "
        f"{COLOUR_SCHEME} is pinned {PINNED_TO}")


def test_that_reader_would_notice_a_ground_that_did() -> None:
    """Mutation check: plant the frame as it was and see the reader name the token."""
    assert ground_of([PLANTED_THEME_GROUND]) == "var(--page)"


def test_the_frame_is_styled_in_the_sheet_that_owns_the_card() -> None:
    """One sheet for the panel: a rule that moved is a rule this file stops reading."""
    assert {rule.where for rule in frame_rules()} == {SHEET}


# --- and the class is one the page really renders -----------------------------

def test_the_frame_this_file_reads_is_the_one_the_viewer_renders() -> None:
    """This file's own regression: the rule it read before outlived its markup by a change."""
    rendered = strip_comments(VIEWER.read_text(encoding="utf-8"))
    assert f'className="{FRAME.lstrip(".")}"' in rendered


# --- and the document it holds has no colour of its own -----------------------

def test_the_exported_report_sets_no_colour_on_its_body() -> None:
    """The premise. A report that coloured itself would make the pin above harmless.

    Left as a live assertion rather than a comment because the two files are far
    apart -- one renders a report for reading off disk, the other styles a frame
    in a browser page -- and nobody editing either would think to check the
    other.
    """
    block = exported_body_block()
    named = [name for name in COLOUR_PROPERTIES if name in block]
    assert named == [], (
        f"markdown_html.STYLE now sets {named} on body, so {FRAME}'s "
        f"{COLOUR_SCHEME} pin is no longer what makes the report readable")


def test_the_exported_report_says_it_follows_whatever_embeds_it() -> None:
    """Which is what makes the embedder's pin reach it at all."""
    assert REPORT_FOLLOWS_THE_EMBEDDER in STYLE


def test_the_check_on_the_exported_report_would_notice_a_colour() -> None:
    """Mutation check: the reader above returns an empty list either way."""
    assert [name for name in COLOUR_PROPERTIES
            if name in BODY_RULE.search(PLANTED_COLOURED_BODY).group(1)] == ["color:"]
