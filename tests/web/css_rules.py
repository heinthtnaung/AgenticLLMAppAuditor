"""Reads the page's stylesheets as text: every rule, its selectors, its declarations.

Shared by the three files that pin a CSS invariant the suite could not see
before -- `test_css_theme_parity.py`, `test_css_layering.py` and
`test_css_grid_tracks.py`. It lives here for the reason `jsx_sweep.py` does: one
reader, so the three cannot drift into three slightly different ideas of what a
rule is, and the reasoning about what each invariant proves stays in the file
that asserts it.

**What it is.** A text scan, deliberately: the alternative is a CSS parser as a
dependency, for three assertions over 840 lines of stylesheet this project wrote
itself. Comments go first -- `index.css` explains the wave layer's `z-index` in
prose that names `background` and `z-index` several times, so a sweep that read
comments would find declarations nobody wrote.

**What it cannot do, and every caller must allow for it.**

- It finds *innermost* rules only. A rule inside `@media (max-width: 1180px)` is
  reported with its own selector and nothing records the condition, so a
  declaration that applies at one width reads here exactly like one that always
  applies. Callers that care assert the at-rule's text separately.
- It is not a cascade model. It cannot say which rule wins, only which rules
  exist -- so "no background on `body`" here means "no rule whose selector is
  exactly `body` declares one", not "nothing paints the body".
- `rules_selecting` matches a whole selector exactly. `.shell` finds
  `.shell` and `.shell, .card`, and does *not* find `.shell > div` or
  `.report__rail .card`. That is a false negative by choice: a descendant
  selector paints a descendant, which is a different claim.
"""

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

# A CSS comment, and one innermost rule: neither group may cross a brace, so an
# at-rule's prelude never matches as a selector and a nested block is found on
# its own. `re.DOTALL` for comments only -- they span lines and rules do too,
# but a rule body cannot contain a brace, which is what keeps the pair honest.
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
RULE = re.compile(r"([^{}]*)\{([^{}]*)\}")

# A class name in a selector: a dot followed by a name, so `0.86em` in a
# declaration value is not one. Callers pass selector text only anyway.
CLASS_SELECTOR = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")

# What marks a declaration as setting a custom property rather than a
# CSS property the browser already knows.
CUSTOM_PREFIX = "--"


@dataclass(frozen=True)
class Rule:
    """One innermost CSS rule: the file it is in, what it selects, what it sets."""

    where: str
    selector: str
    block: str


def stylesheets() -> list[Path]:
    """Every stylesheet the page's own source ships, in a stable order."""
    found = sorted(FRONTEND_SRC.glob("*.css"))
    assert found, f"no stylesheet under {FRONTEND_SRC}; the page has no styles at all"
    return found


def strip_comments(text: str) -> str:
    """The same CSS with every `/* */` comment replaced by one space."""
    return COMMENT.sub(" ", text)


def rules_in(text: str, where: str) -> list[Rule]:
    """Every innermost rule in one stylesheet, comments stripped first."""
    return [Rule(where, found.group(1).strip(), found.group(2))
            for found in RULE.finditer(strip_comments(text))]


def all_rules() -> list[Rule]:
    """Every innermost rule in every stylesheet the page ships."""
    found: list[Rule] = []
    for sheet in stylesheets():
        found += rules_in(sheet.read_text(encoding="utf-8"), sheet.name)
    return found


def selectors_of(rule: Rule) -> list[str]:
    """The rule's comma-separated selectors, each with its whitespace collapsed."""
    return [" ".join(part.split()) for part in rule.selector.split(",")]


def rules_selecting(selector: str) -> list[Rule]:
    """Every rule that selects exactly this, wherever in the stylesheets it was written."""
    return [rule for rule in all_rules() if selector in selectors_of(rule)]


def declarations(block: str) -> list[tuple[str, str]]:
    """The `property: value` pairs in one rule body, values whitespace-collapsed."""
    found: list[tuple[str, str]] = []
    for part in block.split(";"):
        name, separator, value = part.partition(":")
        if separator:
            found.append((name.strip(), " ".join(value.split())))
    return found


def custom_properties(block: str) -> list[tuple[str, str]]:
    """Just the `--token: value` declarations of one rule, in written order."""
    return [(name, value) for name, value in declarations(block)
            if name.startswith(CUSTOM_PREFIX)]


def values_of(rules: list[Rule], property_name: str) -> list[str]:
    """Every value the given rules set for one property, in the order they set it."""
    return [value for rule in rules
            for name, value in declarations(rule.block) if name == property_name]


def class_selectors_in(text: str, where: str) -> set[str]:
    """Every class name one stylesheet's selectors mention, declarations excluded."""
    return {name for rule in rules_in(text, where)
            for name in CLASS_SELECTOR.findall(rule.selector)}
