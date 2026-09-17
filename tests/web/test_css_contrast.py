"""Every colour pair the page renders meets the contrast WCAG asks of it.

This guard was written because a hand-check found what no test could see:
**`--ink-faint` failed AA for normal text in both themes** -- 4.18 on the dark
page and 3.83 on the light, against the 4.5 its twenty-two uses demand, because
every one of them is small text (field labels, placeholders, card hints, file
sizes, pending stages). It is `#7b8a9b` / `#5f6d7d` now, and the pairs below are
what keeps it there.

**The pairs come from the stylesheets, not from a list written here.** Two
sweeps, because text gets its ground two ways:

- **Declared.** Every rule that sets `color` *and* a background is a pair the
  page really paints, and each is checked in all three palettes.
- **Inherited.** A rule that sets `color` alone sits on whatever its ancestor
  paints, which a text sweep cannot resolve -- so every such foreground is
  checked against *both* grounds the page has, the page itself and a raised
  card. That is stricter than the page needs in one direction (a token might
  only ever be used on the lighter of the two) and it is the only honest reading
  without a rendered tree: if it passes on both, it passes wherever it is used.

**A translucent ground is refused rather than guessed**, by `wcag.parse_colour`.
`--panel` is the card's own `rgba()` fill over the page, and the colour a reader
sees under it is a composite that depends on the element tree. So `--card-raised`
stands in as the raised ground, which is what the controls carrying most of the
faint text actually declare.

**Two failures are recorded here rather than asserted, deliberately, and both
are in `docs/TODO.md`.**

- `--line` on `--card-raised` is 1.21 dark and 1.43 light, where 1.4.11 wants
  3.0 for a control boundary -- and that border is the only thing identifying a
  field or a pick. It is a **strict xfail**: the suite stays green on work
  nobody has asked for, the defect keeps a name in the suite rather than only in
  a document, and raising the token turns the xfail into an unexpected pass, so
  the record cannot be left behind by the fix.
- `--on-source-mark` on `--source-mark` is 3.49, which fails 4.5 for text and
  passes the 3.0 a graphical object needs. It is asserted at the non-text
  threshold **and the premise is asserted with it**: `RepositoryLink.jsx` is
  read to confirm that control still carries an icon and no text. Put a word in
  it and the exemption stops being true, which is the half a threshold alone
  would not notice.

What no test in this suite can do: say how large or heavy any of this text is,
which is what decides whether 4.5 or 3.0 applies; say what a display does to
these values; or see a colour that is not a token. The thresholds below are
assigned by hand for that reason, and the assignment is the part to read
sceptically.

Reads the stylesheets as text through `css_rules.py` and computes with `wcag.py`.
No fastapi, no node, no build, no dependency.
"""

import pytest

from . import css_rules, wcag
from .jsx_sweep import strip_comments

# The three palettes, in cascade order. `test_css_theme_parity.py` owns the
# claim that the two light ones are identical; this file checks all three so
# that a drift between them would fail here too.
PALETTES = (":root",
            ':root:not([data-theme="dark"])',
            ':root[data-theme="light"]')

# What WCAG 2.2 asks. 4.5 is 1.4.3 for normal text; 3.0 is 1.4.11 for a
# graphical object or a control boundary, and 1.4.3 for large text.
TEXT_MINIMUM = 4.5
NON_TEXT_MINIMUM = 3.0

# The two grounds the page paints text on. `--panel` is the card's translucent
# fill and cannot be composited by a text sweep, so the raised ground stands in
# for it -- and is what the controls carrying the faint text declare anyway.
GROUNDS = ("--page", "--card-raised")

# The one `color` value that is not a bare token reference.
# `var(--stat-tone, var(--accent))` names a token a *rule* declares rather than
# a palette -- `test_css_theme_parity.py` records that -- so it is skipped, and
# the skipped set is asserted below rather than left to grow quietly.
SKIPPED_FOREGROUNDS = ("var(--stat-tone, var(--accent))",)

# The one pair that is not text, and the component whose markup is why.
THE_ICON_ONLY_CONTROL = ("--on-source-mark", "--source-mark")
THE_CORNER_LINK = "RepositoryLink.jsx"
THE_CORNER_LINK_CLASS = "source-link"

# Recorded and not asserted: a control boundary at 1.21. In `docs/TODO.md`.
THE_CONTROL_BOUNDARY = ("--line", "--card-raised")

# The token the guard was written for, and what it has to clear everywhere.
THE_FAINT_INK = "--ink-faint"

# Published values, to pin the maths rather than trust it: the two extremes, the
# canonical pair of greys either side of 4.5 on white, and the AAA boundary.
PUBLISHED = (("#000000", "#ffffff", 21.0), ("#3ddc84", "#3ddc84", 1.0),
             ("#767676", "#ffffff", 4.54), ("#777", "#fff", 4.48),
             ("#595959", "#ffffff", 7.0))

# A ground no palette declares as a plain colour, to drive the refusal.
A_TRANSLUCENT_GROUND = "rgba(10, 15, 22, 0.66)"

# Floors, so a sweep that read nothing cannot pass as a sweep that found no
# fault. Thirteen declared pairs and six inherited foregrounds today.
MINIMUM_DECLARED_PAIRS = 8
MINIMUM_INHERITED = 4


def palette(selector: str) -> dict[str, str]:
    """One palette block's tokens, insisting it is there exactly once."""
    found = css_rules.rules_selecting(selector)
    assert len(found) == 1, f"expected one `{selector}` block, found {len(found)}"
    return dict(css_rules.custom_properties(found[0].block))


def token_of(value: str) -> str | None:
    """The token one declaration refers to, or nothing when it is not a bare reference."""
    if not (value.startswith("var(") and value.endswith(")")):
        return None
    inside = value[len("var("):-1].strip()
    return inside if inside.startswith("--") and "," not in inside else None


def declared_pairs() -> set[tuple[str, str]]:
    """Every (foreground, background) token pair a single rule declares both halves of."""
    found: set[tuple[str, str]] = set()
    for rule in css_rules.all_rules():
        written = dict(css_rules.declarations(rule.block))
        ink = token_of(written.get("color", ""))
        ground = token_of(written.get("background") or written.get("background-color", ""))
        if ink and ground:
            found.add((ink, ground))
    return found


def inherited_foregrounds() -> set[str]:
    """Every token used as a `color` by a rule that paints no ground of its own."""
    found: set[str] = set()
    for rule in css_rules.all_rules():
        written = dict(css_rules.declarations(rule.block))
        if "background" in written or "background-color" in written:
            continue
        ink = token_of(written.get("color", ""))
        if ink:
            found.add(ink)
    return found


def unreadable_foregrounds() -> set[str]:
    """Every `color` value this file cannot resolve to one palette token."""
    return {value for rule in css_rules.all_rules()
            for name, value in css_rules.declarations(rule.block)
            if name == "color" and value.startswith("var(") and token_of(value) is None}


def ratio_in(selector: str, foreground: str, background: str) -> float:
    """What one pair measures in one palette."""
    tokens = palette(selector)
    for name in (foreground, background):
        assert name in tokens, f"`{selector}` declares no {name}"
    return wcag.ratio_of(tokens[foreground], tokens[background])


def failures(pairs: set[tuple[str, str]], minimum: float) -> list[str]:
    """Every pair that falls short in any palette, named with its palette and its ratio."""
    return sorted(f"{selector}: {foreground} on {background} is "
                  f"{ratio_in(selector, foreground, background):.2f}"
                  for selector in PALETTES
                  for foreground, background in pairs
                  if ratio_in(selector, foreground, background) < minimum)


def _without_tags(markup: str) -> str:
    """The text a reader would see in one element's body, tags removed."""
    depth, kept = 0, []
    for character in markup:
        depth += {"<": 1, ">": -1}.get(character, 0)
        if depth == 0 and character != ">":
            kept.append(character)
    return "".join(kept)


def corner_link_body() -> str:
    """What the corner link element contains, markup and all."""
    text = strip_comments(
        (css_rules.FRONTEND_SRC / "components" / THE_CORNER_LINK).read_text(encoding="utf-8"))
    opened = text.index(f'className="{THE_CORNER_LINK_CLASS}"')
    return text[text.index(">", opened) + 1:text.index("</a>", opened)]


# --- the maths, against published values ---------------------------------------

def test_the_ratio_matches_every_published_value_this_file_names() -> None:
    """The extremes, the two greys either side of AA, and the AAA boundary."""
    measured = [(wcag.ratio_of(ink, ground), expected)
                for ink, ground, expected in PUBLISHED]
    assert [round(got, 2) for got, _ in measured] == [expected for _, expected in measured]


def test_a_translucent_ground_is_refused_rather_than_guessed() -> None:
    """`--panel` over the page is a composite that depends on the element tree."""
    with pytest.raises(ValueError, match="translucent"):
        wcag.parse_colour(A_TRANSLUCENT_GROUND)


# --- every pair a rule declares both halves of ---------------------------------

def test_every_declared_colour_pair_meets_the_text_minimum() -> None:
    """A rule setting both is a pair the page really paints, in every palette."""
    pairs = declared_pairs() - {THE_ICON_ONLY_CONTROL}
    assert failures(pairs, TEXT_MINIMUM) == []


def test_the_pair_sweep_read_the_rules_the_page_declares() -> None:
    """Non-vacuity: an empty set satisfies the check above having read nothing."""
    assert len(declared_pairs()) >= MINIMUM_DECLARED_PAIRS


def test_the_only_foreground_this_file_cannot_read_is_the_named_one() -> None:
    """A token a rule declares is not in a palette; a second one would be skipped in silence."""
    assert sorted(unreadable_foregrounds()) == sorted(SKIPPED_FOREGROUNDS)


# --- and the text whose ground it inherits -------------------------------------

def test_every_inherited_foreground_meets_the_text_minimum_on_both_grounds() -> None:
    """It sits on whatever an ancestor paints, so it has to clear both of them."""
    pairs = {(ink, ground) for ink in inherited_foregrounds() for ground in GROUNDS}
    assert failures(pairs, TEXT_MINIMUM) == []


def test_the_faint_ink_clears_it_on_both_grounds_in_every_palette() -> None:
    """Named, because this is the token the guard was written for: 4.18 and 3.83 before."""
    assert failures({(THE_FAINT_INK, ground) for ground in GROUNDS}, TEXT_MINIMUM) == []


def test_the_inherited_sweep_read_the_foregrounds_the_page_uses() -> None:
    """Non-vacuity: the two checks above pass over an empty set of pairs."""
    assert len(inherited_foregrounds()) >= MINIMUM_INHERITED
    assert THE_FAINT_INK in inherited_foregrounds()


def test_the_sweep_would_report_a_foreground_that_fell_short() -> None:
    """Mutation check: both sweeps return an empty list either way."""
    reported = failures({("--ink-faint", "--ink-soft")}, TEXT_MINIMUM)
    assert len(reported) == len(PALETTES), reported


# --- the one non-text exemption, and the premise it rests on -------------------

def test_the_icon_only_control_meets_the_non_text_minimum() -> None:
    """3.49: too little for text, enough for a graphical object under 1.4.11."""
    assert failures({THE_ICON_ONLY_CONTROL}, NON_TEXT_MINIMUM) == []


def test_the_icon_only_control_would_not_pass_as_text() -> None:
    """Which is why the exemption is named rather than the threshold lowered for everything."""
    assert failures({THE_ICON_ONLY_CONTROL}, TEXT_MINIMUM) != []


def test_the_control_the_exemption_is_for_carries_an_icon_and_no_text() -> None:
    """The premise. Put a word in that link and 3.49 stops being enough for it."""
    body = corner_link_body()
    assert "<Icon" in body
    assert _without_tags(body).strip() == "", f"{THE_CORNER_LINK} now renders text"


def test_that_reader_would_notice_a_word_in_the_control() -> None:
    """Mutation check: the check above compares against an empty string either way."""
    assert _without_tags('<a className="source-link"><Icon /> Source</a>').strip() == "Source"


# --- and one failure this file records rather than asserts ---------------------

@pytest.mark.xfail(strict=True, reason="1.21 dark / 1.43 light against the 3.0 that 1.4.11 "
                                       "asks of a control boundary; recorded in docs/TODO.md")
def test_the_control_boundary_meets_the_non_text_minimum() -> None:
    """Strict, so raising `--line` turns this into an unexpected pass and the record follows."""
    assert failures({THE_CONTROL_BOUNDARY}, NON_TEXT_MINIMUM) == []
