"""The three palettes in `tokens.css` define the same tokens, so no theme half-exists.

`--panel` -- the translucent card ground -- was defined in the dark palette and
in the system-light palette and **not** in the explicit `[data-theme="light"]`
block. Flipping the switch to light therefore left every card with no
background at all, over a drifting wave layer: a defect a hand-check found and
nothing pinned. It is the exact failure the file's own opening comment warns
about ("a token defined in one block and not the other is how a theme ends up
with black text on a black card"), which is the argument for asserting it rather
than commenting it.

**The exempt set is named and asserted both ways.** Five tokens are legitimately
dark-block-only -- `--gap`, `--mono`, `--radius`, `--radius-sm` and
`--page-measure` -- because they are not colours and a light palette has nothing
to say about them. So the test is not "the light blocks may be missing anything
harmless": it is that the dark-only tokens are *exactly* those five. A new colour
token added to the dark block alone fails here, and so does deleting one of the
five without updating the constant.

**Declared once per block, too, which is the other way an edit lands wrong.**
`--scrim` -- the ground behind the run overlay -- was added to all three blocks
by line number, after a plain string replace matched the wrong one: `"  --panel:"`
is a substring of `"    --panel:"`, so the indented copy inside the media query
answered a search meant for the dark block. The failure that leaves is a token
defined *twice* in one block and missing from another, and the name-set
comparisons below cannot see the first half of it -- a set keeps one of two
identical names. So the declarations are counted as well as compared.

**"Identical" means declaration for declaration, not byte for byte.** The
system-light copy sits inside a media query and is indented one level deeper, so
the two are compared as ordered `(token, value)` pairs. That is the property
that matters and the one a reader can check.

What this does not cover: whether the values are *right*. Contrast, and the
"tints twice as strong as intended" defect in `docs/TODO.md`, need an eye on a
rendered page -- this file only holds that the same names exist with matching
values in the two light blocks. Nor does it sweep `var(--x)` references for a
token nothing defines; `--stat-tone` is deliberately declared by a rule rather
than a palette, so that is a different sweep and is not written.

Reads the stylesheet as text through `css_rules.py`. No fastapi, no node, no
build.
"""

from . import css_rules

TOKENS = css_rules.FRONTEND_SRC / "tokens.css"

# The three blocks, in the order the cascade needs them: the complete dark
# palette, the light one a machine asks for, and the light one the toggle
# chooses -- last, so a choice beats the machine in both directions.
DARK_BLOCK = ":root"
SYSTEM_LIGHT_BLOCK = ':root:not([data-theme="dark"])'
CHOSEN_LIGHT_BLOCK = ':root[data-theme="light"]'

# The query the system-light block has to live inside to mean anything.
LIGHT_QUERY = "@media (prefers-color-scheme: light)"

# Tokens the light palettes are allowed not to redefine, because they are not
# colours: a gap, a font stack, two corner radii and the page's own measure are
# the same in every theme. `--page-measure` is a length and is deliberately not
# `--page`, which *is* a colour and is declared in all three blocks -- the
# comment on the token itself records that near-collision.
NON_COLOUR_TOKENS = frozenset({"--gap", "--mono", "--radius", "--radius-sm",
                               "--page-measure"})

# The token whose absence from one block is the defect this file exists for.
REGRESSED_TOKEN = "--panel"

# The ground behind the run overlay, named for the reason above: it was written
# into the three blocks by line number rather than by matching, so the parity
# the general sweeps check over a diff is checked here over the token itself.
OVERLAY_TOKEN = "--scrim"

# A floor under each block, so a parse that read nothing cannot pass every set
# comparison below. 36 dark and 32 light today.
MINIMUM_TOKENS = 25


def stylesheet() -> str:
    """The palette file, with its comments gone: they name tokens in prose."""
    return css_rules.strip_comments(TOKENS.read_text(encoding="utf-8"))


def palette(selector: str) -> list[tuple[str, str]]:
    """One block's custom properties, in written order, or say it is not there once."""
    found = css_rules.rules_selecting(selector)
    assert len(found) == 1, f"expected exactly one `{selector}` block, found {len(found)}"
    declared = css_rules.custom_properties(found[0].block)
    assert declared, f"`{selector}` declares no custom property this test can read"
    return declared


def tokens(selector: str) -> set[str]:
    """Just the token names one block defines."""
    return {name for name, _ in palette(selector)}


def opens_at(text: str, selector: str) -> int:
    """Where a block's opening brace is in the file, for the cascade order below."""
    where = text.find(f"{selector} {{")
    assert where >= 0, f"{TOKENS.name} has no `{selector} {{` this test can find"
    return where


# --- every colour token exists in all three palettes --------------------------

def test_the_machine_light_palette_defines_every_colour_the_dark_one_does() -> None:
    """A token missing here shows as an unstyled element to a viewer who chose nothing."""
    missing = sorted(tokens(DARK_BLOCK) - tokens(SYSTEM_LIGHT_BLOCK) - NON_COLOUR_TOKENS)
    assert missing == []


def test_the_chosen_light_palette_defines_every_colour_the_dark_one_does() -> None:
    """The block the bug was in: this is what the toggle switches the page to."""
    missing = sorted(tokens(DARK_BLOCK) - tokens(CHOSEN_LIGHT_BLOCK) - NON_COLOUR_TOKENS)
    assert missing == []


def test_the_token_the_transparent_cards_came_from_is_in_every_block() -> None:
    """Named, because the general sweep above is a check that passes over an empty set."""
    for selector in (DARK_BLOCK, SYSTEM_LIGHT_BLOCK, CHOSEN_LIGHT_BLOCK):
        assert REGRESSED_TOKEN in tokens(selector), selector


def test_the_token_behind_the_run_overlay_is_in_every_block() -> None:
    """The light palettes carry a weaker scrim, so all three have to define one."""
    for selector in (DARK_BLOCK, SYSTEM_LIGHT_BLOCK, CHOSEN_LIGHT_BLOCK):
        assert OVERLAY_TOKEN in tokens(selector), selector


def test_no_block_declares_the_same_token_twice() -> None:
    """The edit-by-anchor hazard: a set comparison keeps one of two identical names."""
    for selector in (DARK_BLOCK, SYSTEM_LIGHT_BLOCK, CHOSEN_LIGHT_BLOCK):
        declared = [name for name, _ in palette(selector)]
        twice = sorted({name for name in declared if declared.count(name) > 1})
        assert twice == [], f"{selector}: {twice}"


def test_the_only_tokens_the_dark_block_keeps_to_itself_are_the_named_ones() -> None:
    """The exemption is a list of four, not a licence: a fifth fails here."""
    assert tokens(DARK_BLOCK) - tokens(CHOSEN_LIGHT_BLOCK) == NON_COLOUR_TOKENS
    assert tokens(DARK_BLOCK) - tokens(SYSTEM_LIGHT_BLOCK) == NON_COLOUR_TOKENS


def test_neither_light_palette_defines_a_token_the_dark_one_does_not() -> None:
    """The other direction: a light-only token is undefined for everyone else."""
    assert sorted(tokens(SYSTEM_LIGHT_BLOCK) - tokens(DARK_BLOCK)) == []
    assert sorted(tokens(CHOSEN_LIGHT_BLOCK) - tokens(DARK_BLOCK)) == []


def test_the_two_light_palettes_declare_the_same_tokens_with_the_same_values() -> None:
    """They are one palette reached two ways; a drift between them is a third theme."""
    assert palette(SYSTEM_LIGHT_BLOCK) == palette(CHOSEN_LIGHT_BLOCK)


# --- and each one is where the cascade needs it -------------------------------

def test_the_machine_light_palette_is_inside_the_colour_scheme_query() -> None:
    """Outside it that block would hand light to everyone, chosen or not."""
    text = stylesheet()
    assert LIGHT_QUERY in text
    assert text.index(LIGHT_QUERY) < opens_at(text, SYSTEM_LIGHT_BLOCK)


def test_the_chosen_palette_comes_after_the_query_it_has_to_beat() -> None:
    """Same specificity would make source order decide, so the toggle goes last."""
    text = stylesheet()
    assert opens_at(text, DARK_BLOCK) < text.index(LIGHT_QUERY)
    assert text.index(LIGHT_QUERY) < opens_at(text, CHOSEN_LIGHT_BLOCK)


# --- the parse read three real palettes ---------------------------------------

def test_every_block_was_read_as_a_palette_and_not_an_empty_rule() -> None:
    """Non-vacuity: three empty sets satisfy every comparison in this file."""
    for selector in (DARK_BLOCK, SYSTEM_LIGHT_BLOCK, CHOSEN_LIGHT_BLOCK):
        assert len(tokens(selector)) >= MINIMUM_TOKENS, selector


def test_all_three_palettes_are_declared_in_the_palette_file() -> None:
    """One place for the colours: a block in another sheet is a palette nothing here reads."""
    for selector in (DARK_BLOCK, SYSTEM_LIGHT_BLOCK, CHOSEN_LIGHT_BLOCK):
        where = [rule.where for rule in css_rules.rules_selecting(selector)]
        assert where == [TOKENS.name], selector
