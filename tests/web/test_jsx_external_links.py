"""Every link the page opens in a new tab hands that tab nothing.

Two anchors leave this page: the auditor's own repository in the corner, and the
one the advice panel renders per grounded OWASP cheat-sheet passage -- so the
second is as many links as a run has cited passages. Both use
`target="_blank"`, which without `rel="noopener"` gives the opened page a live
`window.opener` handle back to this one -- it can navigate this tab somewhere
else, and the reader sees the change in a tab they trust because they opened it
themselves.

**On this page that matters more than usual, and less than usual, at the same
time.** Less, because there is nothing to steal: no session, no token, no
authentication of any kind. More, because a security tool whose own UI hands
out an opener handle is making, in its own page, the class of mistake it reports
about other people's code. `noreferrer` goes with it: the same-origin server is
on loopback and its URL says so, which is not a thing to send to a third party
in a `Referer` header.

The check is over **every** anchor the page has rather than over the ones this
file knows about, so a link added later is covered the moment it is written. A
planted anchor shows the reader reports rather than tolerates one, and a floor
under the count keeps a sweep that matched nothing from passing.

What this cannot see: a link built as an `<a>` through a variable, or a
`window.open` call. Neither exists today and a floor would not catch either;
`jsx_sweep.py` records the same class of limit for the accessor sweep.

Read as text with comments stripped, so a comment mentioning `target="_blank"`
to explain this rule is not itself a violation.
"""

import re
from pathlib import Path

from .jsx_sweep import FRONTEND_SRC, strip_comments

# One anchor with its attributes, and the two attributes that decide this.
ANCHOR = re.compile(r"<a\s([^>]*?)>", re.DOTALL)
TARGET = re.compile(r'target="([^"]*)"')
REL = re.compile(r'rel="([^"]*)"')

# The target that opens a new tab, and what a link using it must grant.
NEW_TAB = "_blank"
REQUIRED_REL = ("noreferrer", "noopener")

# A floor: two anchors open a new tab today, in two components. Zero would
# satisfy "every one of them is safe" perfectly.
LEAST_NEW_TAB_LINKS = 2

# Planted anchors, to show each reader fires on a real violation.
PLANTED_FILE = "Planted.jsx"
PLANTED_BARE = '<a href={url} target="_blank">a link that hands over its opener</a>'
PLANTED_HALF = '<a href={url} target="_blank" rel="noreferrer">half of it</a>'
PLANTED_IN_A_COMMENT = f'// never write target="{NEW_TAB}" without a rel\n<a href="/runs">x</a>'


def anchors(root: Path = FRONTEND_SRC) -> list[tuple[str, str]]:
    """Every `<a ...>` the page declares, paired with the file that declares it."""
    found: list[tuple[str, str]] = []
    for source in sorted(root.rglob("*.jsx")):
        text = strip_comments(source.read_text(encoding="utf-8"))
        found += [(source.name, tag) for tag in ANCHOR.findall(text)]
    return found


def new_tab_links(root: Path = FRONTEND_SRC) -> list[tuple[str, str]]:
    """Just the anchors that open a new tab, which are the ones this rule is about."""
    return [(where, tag) for where, tag in anchors(root)
            if _target_of(tag) == NEW_TAB]


def _target_of(tag: str) -> str | None:
    """What one anchor's `target` attribute says, or None when it has none."""
    found = TARGET.search(tag)
    return found.group(1) if found else None


def ungranted(root: Path = FRONTEND_SRC) -> list[str]:
    """Name every new-tab link missing part of the rel it needs, file and all."""
    said: list[str] = []
    for where, tag in new_tab_links(root):
        granted = (REL.search(tag).group(1).split() if REL.search(tag) else [])
        missing = [name for name in REQUIRED_REL if name not in granted]
        said += [f"{where}: {name}" for name in missing]
    return sorted(said)


def plant(tmp_path: Path, source: str) -> Path:
    """Write a throwaway page holding one anchor, and return its root."""
    root = tmp_path / "planted_src"
    root.mkdir()
    (root / PLANTED_FILE).write_text(source, encoding="utf-8")
    return root


# --- the sweep read something -------------------------------------------------

def test_the_page_really_opens_links_in_a_new_tab() -> None:
    """Guard: zero such links would satisfy the rule below having checked nothing."""
    assert len(new_tab_links()) >= LEAST_NEW_TAB_LINKS


def test_the_links_come_from_more_than_one_component() -> None:
    """The corner link and the grounded passages are different code, and both count."""
    assert len({where for where, _ in new_tab_links()}) >= LEAST_NEW_TAB_LINKS


# --- and every one of them hands over nothing ---------------------------------

def test_every_new_tab_link_refuses_the_opener_and_the_referrer() -> None:
    """A security tool whose own page leaks an opener handle is making the point badly."""
    assert ungranted() == []


def test_a_link_with_no_rel_at_all_is_reported(tmp_path) -> None:
    """Mutation check: the reader must name both halves it is missing."""
    assert ungranted(plant(tmp_path, PLANTED_BARE)) == sorted(
        f"{PLANTED_FILE}: {name}" for name in REQUIRED_REL)


def test_a_link_with_half_the_rel_is_reported_too(tmp_path) -> None:
    """`noreferrer` implies `noopener` in current browsers and not in old ones; both are asked."""
    assert ungranted(plant(tmp_path, PLANTED_HALF)) == [f"{PLANTED_FILE}: noopener"]


def test_naming_the_attribute_in_a_comment_is_not_using_it(tmp_path) -> None:
    """Comments are stripped first, so this rule can be explained where it applies."""
    assert new_tab_links(plant(tmp_path, PLANTED_IN_A_COMMENT)) == []
