"""The WCAG contrast ratio, from the published formula, in the standard library.

One job: turn two CSS colours into the number WCAG 2.2 compares against a
threshold. `test_css_contrast.py` decides which pairs the page really renders
and what each one has to reach; this module knows nothing about the page.

**The formula, as published** (WCAG 2.2, *relative luminance* and *contrast
ratio*). For each sRGB channel, taken as 0..1:

    c / 12.92                      when c <= 0.03928
    ((c + 0.055) / 1.055) ** 2.4   otherwise

    L     = 0.2126 R + 0.7152 G + 0.0722 B
    ratio = (L_lighter + 0.05) / (L_darker + 0.05)

The threshold is written `0.03928` because that is the number in the
specification. The mathematically exact crossing point is 0.04045, and the
difference changes no ratio this project computes to two decimal places; the
published value is used so a reader can check this against the document rather
than against an argument. `test_css_contrast.py` pins the output against four
published values -- including the well-known pair of greys either side of 4.5 --
so an error here fails there rather than silently shifting every number.

**A translucent ground is refused rather than guessed.** `--panel`, `--veil`
and `--scrim` are `rgba()`, and the colour a reader actually sees under one is
the composite of it with whatever is behind it -- which depends on the element
tree, and no text sweep can know it. `parse_colour` raises on any alpha below 1
with a message saying so, so a pair involving one cannot be asserted by
accident.

The reader is `parse_colour` and not `parse` because `tests/ast_scan.py`
defines a `parse` and `tests/test_ast_scan.py` holds every scanner name to one
definition across the whole suite. Two functions with one name and two answers
is a hazard that file was written for after it really happened, and it caught
this module on the first run.

No dependency, by design: a colour-science package for one formula in forty
lines would be the fifth third-party import in a project that argues for four.
It also cannot tell you what a display does -- no colour profile, no gamma
beyond the transfer function above, and nothing about the size or weight of the
text, which is what decides whether 4.5 or 3.0 applies.
"""

import re

# What a colour may be written as in this project's stylesheets: a three- or
# six-digit hex literal, or an `rgb()`/`rgba()` function.
HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")
RGB_FUNCTION = re.compile(r"rgba?\(([^)]*)\)\Z")

# The transfer function's own constants, and the channel weights, from the
# specification rather than rounded here.
LINEAR_BELOW = 0.03928
LINEAR_DIVISOR = 12.92
GAMMA_OFFSET = 0.055
GAMMA_DIVISOR = 1.055
GAMMA_EXPONENT = 2.4
WEIGHTS = (0.2126, 0.7152, 0.0722)

# What the ratio is offset by, so that black on black is 1 rather than undefined.
FLARE = 0.05

# Fully opaque. Anything less is a composite this module will not guess at.
OPAQUE = 1.0

Rgb = tuple[int, int, int]


def parse_colour(value: str) -> Rgb:
    """One CSS colour as its three channels, or an explicit refusal saying why."""
    value = value.strip()
    found = HEX.match(value)
    if found:
        digits = found.group(1)
        if len(digits) == 3:
            digits = "".join(digit * 2 for digit in digits)
        return tuple(int(digits[at:at + 2], 16) for at in (0, 2, 4))
    return _colour_function(value)


def _colour_function(value: str) -> Rgb:
    """An `rgb()` or `rgba()` colour, insisting it is opaque and well formed."""
    found = RGB_FUNCTION.match(value)
    if not found:
        raise ValueError(f"{value!r} is not a colour this reader knows how to parse")
    parts = [part.strip() for part in found.group(1).split(",")]
    if len(parts) == 4 and float(parts[3]) < OPAQUE:
        raise ValueError(
            f"{value!r} is translucent, so what a reader sees is it composited with "
            "whatever is behind it -- which no text sweep can know. Assert a pair "
            "of opaque colours instead.")
    if len(parts) not in (3, 4):
        raise ValueError(f"{value!r} does not give three channels")
    return tuple(int(float(part)) for part in parts[:3])


def _channel(eight_bit: int) -> float:
    """One sRGB channel made linear, by the published transfer function."""
    unit = eight_bit / 255
    if unit <= LINEAR_BELOW:
        return unit / LINEAR_DIVISOR
    return ((unit + GAMMA_OFFSET) / GAMMA_DIVISOR) ** GAMMA_EXPONENT


def luminance(colour: Rgb) -> float:
    """The relative luminance of one colour: 0 for black, 1 for white."""
    return sum(weight * _channel(channel)
               for weight, channel in zip(WEIGHTS, colour))


def ratio(foreground: Rgb, background: Rgb) -> float:
    """The contrast ratio between two colours, from 1 to 21, whichever is lighter."""
    lit = (luminance(foreground), luminance(background))
    return (max(lit) + FLARE) / (min(lit) + FLARE)


def ratio_of(foreground: str, background: str) -> float:
    """The same, taking the two colours as they are written in CSS."""
    return ratio(parse_colour(foreground), parse_colour(background))
