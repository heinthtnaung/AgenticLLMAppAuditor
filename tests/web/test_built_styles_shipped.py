"""The shipped stylesheet is built from the six the source has, and all six are imported.

`test_built_page_shipped.py` joins the JSX to `dist/assets/index.js` and says so
in its own docstring: **the CSS half of the bundle is swept by nothing.** The
stylesheets were split twice while this page was being built -- three files
became six -- and either half of that can fail silently. A seventh sheet that
`main.jsx` never imports is simply not in the build, and a rule edited without
`npm run build` ships as the previous rule. Neither shows up in a Python test
suite, and a `className`-to-bundle join cannot see either: those names are in
the JSX whether a stylesheet mentions them or not.

Two joins, one per failure:

- **Source to bundle.** Every class name any `frontend/src/*.css` selects must
  appear in the shipped `dist/assets/*.css`. Vite concatenates and minifies
  without renaming selectors, so this is a rebuild check that survives a clone
  -- the same argument `test_built_page_shipped.py` makes for not using mtimes,
  and the reason that file, not this one, owns the `index.html` link and the
  `/assets` mount.
- **Source to entry point.** The set of stylesheets under `frontend/src/` and
  the set `main.jsx` imports must be equal, so an unimported sheet and an
  import of a file that no longer exists both fail.

What it cannot see, which is the same gap the JSX sweep has: a rule *removed*
from the source, since the sweep runs source to bundle and a stale bundle keeps
what the source has dropped; a changed *value* -- a colour, a width, a
`z-index` -- because only selectors are joined; and a class the JSX renders that
no stylesheet defines, which is unstyled markup rather than a stale build.

Reads this project's own build output, as `test_built_page_shipped.py` does and
for the reason recorded there: `dist/` is committed on purpose, so "clone, pip
install, run" needs no Node. No fastapi and no node -- paths only, since the
route that serves this file is tested next door.
"""

import re

from . import css_rules

DIST_ASSETS = css_rules.REPO_ROOT / "frontend" / "dist" / "assets"
ENTRY_POINT = css_rules.FRONTEND_SRC / "main.jsx"

# `import './tokens.css'` -- the entry point's own spelling, single-quoted, and
# the double-quoted form too so a reformat is not a failure.
STYLESHEET_IMPORT = re.compile(r"""import\s+['"]\./([^'"]+\.css)['"]""")

# Floors, so a sweep that read nothing cannot pass as a sweep that found no
# fault. 121 class selectors across six sheets when this was written; the floor
# is well under it so an ordinary edit does not have to move it, and the sheet
# floor is the count from before the two splits.
MINIMUM_CLASS_SELECTORS = 80
MINIMUM_STYLESHEETS = 3

# Planted below: a class no stylesheet has ever selected, to show the join
# reports a name rather than tolerating it.
CLASS_THAT_DOES_NOT_EXIST = "card--pacakge"


def shipped() -> str:
    """Every stylesheet the build wrote, concatenated, or say the build is missing."""
    built = sorted(DIST_ASSETS.glob("*.css"))
    assert built, f"no stylesheet under {DIST_ASSETS}; run `npm run build` in frontend/"
    return "\n".join(sheet.read_text(encoding="utf-8") for sheet in built)


def class_selectors() -> list[tuple[str, str]]:
    """Every class name the source stylesheets select, paired with the sheet selecting it."""
    found: list[tuple[str, str]] = []
    for sheet in css_rules.stylesheets():
        text = sheet.read_text(encoding="utf-8")
        found += [(sheet.name, name)
                  for name in sorted(css_rules.class_selectors_in(text, sheet.name))]
    return found


def not_shipped(selected: list[tuple[str, str]]) -> list[str]:
    """Name every class the built stylesheet does not have, sheet and all."""
    bundle = shipped()
    return sorted({f"{where}: .{name}" for where, name in selected
                   if f".{name}" not in bundle})


def imported() -> list[str]:
    """The stylesheets the entry point pulls in, in the order it pulls them."""
    return STYLESHEET_IMPORT.findall(ENTRY_POINT.read_text(encoding="utf-8"))


# --- the built stylesheet matches the source it was built from ----------------

def test_every_class_the_source_selects_is_in_the_built_stylesheet() -> None:
    """A rule edited without `npm run build` serves the page's previous appearance."""
    assert not_shipped(class_selectors()) == [], "rebuild frontend/"


def test_the_sweep_read_a_real_set_of_class_selectors() -> None:
    """Non-vacuity: a regex that matched nothing would make the join above pass empty."""
    assert len(class_selectors()) >= MINIMUM_CLASS_SELECTORS


def test_a_class_the_built_stylesheet_does_not_have_is_reported_with_its_sheet() -> None:
    """Planted, because the join is a check that returns an empty list either way."""
    planted = [("surfaces.css", CLASS_THAT_DOES_NOT_EXIST)]
    assert not_shipped(planted) == [f"surfaces.css: .{CLASS_THAT_DOES_NOT_EXIST}"]


# --- and every sheet the source has really reaches the build ------------------

def test_every_stylesheet_in_the_source_is_imported_by_the_entry_point() -> None:
    """A sheet nothing imports is not in the bundle, however correct its rules are."""
    missing = sorted({sheet.name for sheet in css_rules.stylesheets()} - set(imported()))
    assert missing == [], f"not imported by {ENTRY_POINT.name}: {missing}"


def test_every_stylesheet_the_entry_point_imports_exists() -> None:
    """The other direction: a renamed sheet leaves an import Vite fails to resolve."""
    absent = sorted(name for name in imported()
                    if not (css_rules.FRONTEND_SRC / name).is_file())
    assert absent == []


def test_no_stylesheet_is_imported_twice() -> None:
    """Two imports of one sheet is a duplicated rule set and a merge nobody finished."""
    assert sorted(imported()) == sorted(set(imported()))


def test_the_import_sweep_read_the_real_list() -> None:
    """Non-vacuity: two empty sets satisfy the equality the two tests above split."""
    assert len(imported()) >= MINIMUM_STYLESHEETS
    assert len(css_rules.stylesheets()) >= MINIMUM_STYLESHEETS
