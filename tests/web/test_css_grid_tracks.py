"""Every flexible track in the top bar is floored at zero, so the header cannot be widened.

`1fr` does not mean "a share of the space". It means `minmax(auto, 1fr)`, and
`auto` on a grid item is its *minimum content* size -- so a track holding a long
repository URL or an untruncated app name grows past the viewport and takes the
whole page into a horizontal scroll with it. That is the third defect a
screenshot caught: the bar was wider than the window and everything under it
moved sideways. `minmax(0, 1fr)` is the fix, and it is one word nobody notices
going missing.

**Narrow on purpose.** Only `.topbar__inner` is asserted, because only the
header holds text of a length nobody controls in a track that has to share the
row. `.stats--rail { grid-template-columns: 1fr; }` and `.report`'s
`210px minmax(0, 1fr) 300px` are elsewhere and are not this test's business:
a single-column rail cannot overflow its own row, and widening that judgement
into "every `fr` in the page must be floored" would be a rule the design does
not follow. If a second grid ever needs the same guard, it is one entry in
`FLOORED_GRIDS`.

**This pins the mechanism, not the appearance.** Nothing here lays the page out,
so it cannot see an overflow -- an element with a hard `width`, a `white-space:
nowrap` on something long, or a padding that overshoots all pass. It holds one
spelling that had to be right and was not. `docs/TODO.md` keeps the rest.

Every rule selecting the grid is read, wherever it is written, so an override
inside a media query is covered by the same sweep -- but the at-rule's condition
is invisible to `css_rules.py`, so a track floored at one width and not another
reads here as two declarations and both must hold.

Reads the stylesheets as text through `css_rules.py`. No fastapi, no node, no
build.
"""

from . import css_rules

# The grids whose flexible tracks must be floored. One today: the header.
FLOORED_GRIDS = (".topbar__inner",)

TRACK_PROPERTY = "grid-template-columns"

# What makes a track flexible, and the only spelling of a flexible track that
# cannot be pushed wider than its share by its own contents.
FLEXIBLE_UNIT = "fr"
FLOORED_AT_ZERO = "minmax(0,"

# Floors under the sweep. The header has two flexible tracks of three, and a
# grid with none would satisfy every check below having read nothing.
MINIMUM_FLEXIBLE_TRACKS = 2
MINIMUM_DECLARATIONS = 1

# Planted below: the shape the regression had, and a function that must survive
# the split whole rather than being read as three tracks.
UNFLOORED_TRACKS = "210px 1fr auto"
ONE_FUNCTION_TRACK = "repeat(auto-fit, minmax(140px, 1fr))"


def tracks(value: str) -> list[str]:
    """Split a track list on the spaces between tracks, keeping each function whole."""
    found: list[str] = []
    depth = 0
    current = ""
    for character in value:
        depth += (character == "(") - (character == ")")
        if character == " " and depth == 0:
            found.append(current)
            current = ""
            continue
        current += character
    found.append(current)
    return [track for track in found if track]


def flexible(value: str) -> list[str]:
    """Just the tracks of one list that take a share of the leftover space."""
    return [track for track in tracks(value) if FLEXIBLE_UNIT in track]


def unfloored(value: str) -> list[str]:
    """Every flexible track that is not floored at zero, which is every one that can grow."""
    return [track for track in flexible(value) if not track.startswith(FLOORED_AT_ZERO)]


def declared_tracks(selector: str) -> list[str]:
    """Every track list any rule gives one grid, media queries included."""
    return css_rules.values_of(css_rules.rules_selecting(selector), TRACK_PROPERTY)


# --- the invariant ------------------------------------------------------------

def test_every_flexible_track_in_the_top_bar_is_floored_at_zero() -> None:
    """The regression: a bare `1fr` is `minmax(auto, 1fr)` and grows with its contents."""
    for selector in FLOORED_GRIDS:
        for value in declared_tracks(selector):
            assert unfloored(value) == [], f"{selector}: {value}"


def test_the_top_bar_really_declares_flexible_tracks() -> None:
    """Non-vacuity: a grid of fixed columns would pass the test above having nothing to check."""
    for selector in FLOORED_GRIDS:
        for value in declared_tracks(selector):
            assert len(flexible(value)) >= MINIMUM_FLEXIBLE_TRACKS, f"{selector}: {value}"


def test_the_top_bar_is_a_grid_with_a_track_list_to_read() -> None:
    """A renamed class or a switch to flexbox must fail here, not sweep an empty list."""
    for selector in FLOORED_GRIDS:
        assert len(declared_tracks(selector)) >= MINIMUM_DECLARATIONS, selector
        assert "grid" in css_rules.values_of(css_rules.rules_selecting(selector),
                                             "display"), selector


# --- the split the invariant is read through ----------------------------------

def test_a_bare_flexible_track_is_reported() -> None:
    """Planted, in the shape the header had: the check returns a list either way."""
    assert unfloored(UNFLOORED_TRACKS) == ["1fr"]


def test_a_track_written_as_a_function_survives_the_split_whole() -> None:
    """`repeat(auto-fit, minmax(...))` holds a space; split naively it reads as three tracks."""
    assert tracks(ONE_FUNCTION_TRACK) == [ONE_FUNCTION_TRACK]


def test_a_fixed_track_is_not_read_as_flexible() -> None:
    """The other direction: `auto` and `210px` are not tracks this invariant is about."""
    assert flexible(UNFLOORED_TRACKS) == ["1fr"]
