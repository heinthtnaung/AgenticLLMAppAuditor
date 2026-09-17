"""The wave layer is in front of the ground and behind the page, in the one form text can hold.

The waves were invisible. `.waves` sat at `z-index: -1` and `body` carried a
`background`, and a descendant at a negative index paints *behind its own
ancestor's background* -- so the whole layer was under the fill, on every
screen, and nothing in the suite could tell. The fix is a pair, not a single
value: the layer moved to `0` with the bar and the content at `1`, and the fill
moved off `body` up to `:root`. Either half alone brings the defect back, which
is why they are asserted together here.

**This pins the mechanism, not the appearance.** It says no rule whose selector
is exactly `body` or `.shell` declares a background, that the layer's index is
not negative, and that the bar and the content are above it. It cannot say the
waves are *visible*: it does not lay the page out, so a wave tinted to
transparency, a layer sized to nothing, or an opaque card over it all pass here
and need an eye on a rendered page. `docs/TODO.md` keeps that half of the row.

**Only exact selectors.** `css_rules.rules_selecting` matches a whole selector,
so `body` and `.shell` are checked and `.shell > div` is not: a descendant's
background paints a descendant, which is a different claim and would be a
different test. The consequence is a false negative -- a background reaching
`body` through a group selector this test does not name -- and the ground
assertion below is what bounds it, since it holds that the page's one fill is
where the design says it is rather than merely absent from two rules.

Reads the stylesheets as text through `css_rules.py`. No fastapi, no node, no
build.
"""

from . import css_rules

# The layer, and the two ancestors whose fill would paint over it.
WAVE_LAYER = ".waves"
NO_BACKGROUND_ON = ("body", ".shell")

# What must sit in front of the waves for the page to be readable at all.
ABOVE_THE_WAVES = (".topbar", ".content")

# Where the one opaque fill belongs. `:root` is above `body` in the tree, so a
# fill there is behind the wave layer instead of over it -- the whole point of
# moving it, and the reason this is asserted rather than "nothing has a
# background".
THE_GROUND = ":root"
GROUND_PROPERTY = "background"

# The lowest index the layer may sit at. `-1` is the defect; `0` is what
# `index.css` uses and explains.
LOWEST_ALLOWED_INDEX = 0

# A fixed layer over the whole viewport swallows every click unless it opts out,
# and raising it from `-1` to `0` is what made that possible -- so the two
# belong to one change and are asserted in one file.
NO_CLICKS = ("pointer-events", "none")


def paints(rule: css_rules.Rule) -> list[str]:
    """Every background property one rule sets, longhand or shorthand."""
    return [name for name, _ in css_rules.declarations(rule.block)
            if name == GROUND_PROPERTY or name.startswith(f"{GROUND_PROPERTY}-")]


def backgrounds_on(selector: str) -> list[str]:
    """Name every background any rule sets on exactly this selector, sheet and all."""
    return sorted(f"{rule.where}: {selector} {{ {name} }}"
                  for rule in css_rules.rules_selecting(selector)
                  for name in paints(rule))


def index_of(selector: str) -> int:
    """The one `z-index` a selector is given, or say plainly that it has none or two."""
    found = css_rules.values_of(css_rules.rules_selecting(selector), "z-index")
    assert len(found) == 1, f"expected one z-index on `{selector}`, found {found}"
    return int(found[0])


# --- nothing between the waves and the ground ---------------------------------

def test_the_wave_layers_ancestors_paint_no_background() -> None:
    """The defect's other half: a fill on `body` is what the layer was hidden under."""
    for selector in NO_BACKGROUND_ON:
        assert backgrounds_on(selector) == [], selector


def test_the_pages_one_fill_is_on_the_root_element() -> None:
    """Non-vacuity: a stylesheet with no fill anywhere would pass the test above."""
    assert css_rules.values_of(css_rules.rules_selecting(THE_GROUND),
                               GROUND_PROPERTY) != []


def test_a_background_on_an_ancestor_is_reported() -> None:
    """Planted: the property matcher is what the sweep above rests on."""
    planted = css_rules.Rule("planted.css", "body", "background-color: #fff;")
    assert paints(planted) == ["background-color"]


# --- and the waves behind everything that has to be read ----------------------

def test_the_wave_layer_sits_at_a_non_negative_index() -> None:
    """`-1` paints behind the ancestor's background, whatever that background is."""
    assert index_of(WAVE_LAYER) >= LOWEST_ALLOWED_INDEX


def test_the_bar_and_the_content_sit_above_the_wave_layer() -> None:
    """The layer is opaque enough to tint text, so the page has to be in front of it."""
    for selector in ABOVE_THE_WAVES:
        assert index_of(selector) > index_of(WAVE_LAYER), selector


def test_the_wave_layer_takes_no_clicks() -> None:
    """At `0` over the whole viewport it is in front of the ground and under the cursor."""
    name, value = NO_CLICKS
    assert value in css_rules.values_of(css_rules.rules_selecting(WAVE_LAYER), name)


def test_every_selector_this_file_names_has_a_rule() -> None:
    """Non-vacuity: a renamed class would make three sweeps above read nothing at all."""
    for selector in (WAVE_LAYER, THE_GROUND, *NO_BACKGROUND_ON, *ABOVE_THE_WAVES):
        assert css_rules.rules_selecting(selector) != [], selector
