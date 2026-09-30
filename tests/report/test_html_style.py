"""Guards on the one stylesheet: both themes complete, and every colour reachable.

The bug these exist for has one shape. A token defined in the light `:root` and
missed in the dark one leaves a card with black text on a black background, and
nothing but a reader's eyes would catch it -- so the two blocks are held to one
set of names here. The mirror of it, a rule reaching for a token nobody defined,
is the same failure from the other end and is held the same way.
"""

import re

from cvss.score import SEVERITY_BAND_NAMES
from report.html_assets import stylesheet
from report.html_style import BAND_CLASSES, BANDS, band_class

# The joined stylesheet the page inlines, read the way the page reads it.
STYLESHEET = stylesheet()

LIGHT = re.compile(r"^:root \{(.*?)^\}", re.DOTALL | re.MULTILINE)
DARK = re.compile(r"prefers-color-scheme: dark\).*?:root \{(.*?)\n  \}", re.DOTALL)
DEFINED = re.compile(r"(--[a-z0-9-]+):")
USED = re.compile(r"var\((--[a-z0-9-]+)\)")
HEX = re.compile(r"#[0-9a-f]{3,8}\b")

# The only selectors allowed to hide anything: the hidden attribute, the tab bar
# and toolbars with no script, the responsive table head, and the print rule.
# A rule that hides a panel by any other selector would break no-JS readability.
HIDING = re.compile(r"([^{}]+)\{[^{}]*(display:\s*none|visibility:\s*hidden)[^{}]*\}")
HIDE_ALLOWED = frozenset((
    "[hidden]", "html:not(.js) .tabbar", "html:not(.js) .toolbar",
    "table.data.rt thead", ".tabbar, .toolbar",
))

# Set per band class rather than in a theme block, so they are defined by the
# rule that colours a band and not by either `:root`.
PER_BAND = frozenset(("--band-bg", "--band-fg"))


def tokens(block: str) -> set[str]:
    """Name every custom property one block defines."""
    return set(DEFINED.findall(block))


def light_block() -> str:
    """Give the light theme's `:root`, which is the first one in the sheet."""
    found = LIGHT.search(STYLESHEET)
    assert found, "the stylesheet has no light :root block"
    return found.group(1)


def dark_block() -> str:
    """Give the `:root` inside the dark media query."""
    found = DARK.search(STYLESHEET)
    assert found, "the stylesheet has no dark :root block"
    return found.group(1)


def test_both_themes_define_the_same_tokens():
    # A token in one block and not the other is how a card ends up with black
    # text on a black background, and no test that reads markup can see that.
    assert tokens(light_block()) == tokens(dark_block())


def test_the_dark_theme_is_not_the_light_one_again():
    assert dark_block().strip() != light_block().strip()


def test_every_token_a_rule_reaches_for_is_defined():
    reached = set(USED.findall(STYLESHEET)) - PER_BAND
    assert reached <= tokens(light_block())
    assert reached <= tokens(dark_block())


def test_the_palette_colours_the_bands_named_once_and_does_not_restate_them():
    # The CVSS band names cover the organisation ones, so the sheet imports them
    # rather than listing a second copy that could drift from the calculator's.
    assert BANDS is SEVERITY_BAND_NAMES


def test_every_band_has_a_colour_in_both_themes():
    named = {f"--band-{one.lower()}-bg" for one in BANDS}
    named |= {f"--band-{one.lower()}-fg" for one in BANDS}
    assert named <= tokens(light_block())
    assert named <= tokens(dark_block())


def test_every_band_class_is_a_rule_in_the_sheet():
    assert all(f".{one}" in STYLESHEET for one in BAND_CLASSES.values())


def test_the_floor_note_has_its_own_rule_in_the_sheet():
    # The floor note carries its own class, not `refusal`, so the sheet must style
    # it; without this the class would render unstyled and no markup test would see.
    assert ".floor-note {" in STYLESHEET


def test_a_band_the_palette_cannot_reach_is_refused_rather_than_rendered_unstyled():
    try:
        band_class("Severe")
    except ValueError as refusal:
        assert "Severe" in str(refusal)
        assert "Critical" in str(refusal)
        return
    raise AssertionError("a band with no colour was rendered instead of refused")


def test_the_page_is_laid_out_for_a_phone_as_well_as_a_desktop():
    # A fixed track that overflows is the commonest layout bug and no test here
    # can see one. What can be checked is that the narrow rules exist at all.
    assert "@media (max-width: 34rem)" in STYLESHEET


def test_every_colour_is_named_in_a_theme_block_and_nowhere_else():
    # A literal colour in a rule is one the other theme cannot override, which
    # is the same bug as a missing token arriving from the other direction.
    named = len(HEX.findall(light_block())) + len(HEX.findall(dark_block()))
    assert len(HEX.findall(STYLESHEET)) == named


def test_nothing_is_hidden_except_by_a_selector_on_the_allowlist():
    # A rule like `.panel { display: none }` or `html:not(.js) main { visibility:
    # hidden }` would hide content a no-JS reader needs, and no rendering test
    # here can see it. Every hiding rule's selector is held to the allowlist.
    hiding = {selector.strip() for selector, _ in HIDING.findall(STYLESHEET)}
    assert hiding, "the sheet hides nothing at all, so this guard checked nothing"
    assert hiding <= HIDE_ALLOWED, f"unexpected hiding selectors: {hiding - HIDE_ALLOWED}"
