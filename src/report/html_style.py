"""The class that colours a severity band.

**Every colour is a token, and every token is defined in both themes.** A token
defined in the light block and missed in the dark one is how a card ends up with
black text on a black background, so `tests/report/test_html_style.py` holds the
two blocks to the same set of names.

**A published CVSS score and an Organisation Risk Score never share a shape.**
They are different claims on different scales -- `docs/SCORING_MODEL.md` refuses
to merge them -- so one is a square outlined chip and the other a solid pill,
and the band colour they share cannot make them read as one badge.

The sheet itself is `assets/*.css`, read and joined by `report.html_assets` at
render time and inlined, because a scan runs offline and a fetched stylesheet
arrives unreadable.
"""

from cvss.score import SEVERITY_BAND_NAMES

# The CVSS band names, defined once in `cvss.score`: they cover the organisation
# ones, which are the same names without `None`. A band with no colour is refused
# rather than rendered unstyled.
BANDS: tuple[str, ...] = SEVERITY_BAND_NAMES

BAND_CLASSES = {name: f"band-{name.lower()}" for name in BANDS}


def band_class(band: str) -> str:
    """Give the class that colours one band, refusing a band the palette cannot reach."""
    named = BAND_CLASSES.get(band)
    if named is None:
        named_bands = ", ".join(BANDS)
        raise ValueError(f"{band!r} is no band this palette has a colour for: {named_bands}")
    return named
