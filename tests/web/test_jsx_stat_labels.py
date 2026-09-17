"""A headline number may not claim more than the number under it.

The third stat was labelled **Vulnerable deps** while its value was
`coverage.advisory_unreached_component_count` -- the components no LLM surface
reaches, which is a *part* of the vulnerable dependencies and not all of them.
On the run that prompted the section, 79 components carried 311 advisories and
the stat read 79 under a label that said "all". It says "Vulnerable deps,
unreached" now.

**What is asserted is the tie, not the wording.** Three links, each one checked:
the key is one `src/artifacts/coverage.py` really publishes; exactly one stat on
the page shows that key; and the label over it carries the qualifier the key
itself carries. The qualifier is taken from the key name --
`advisory_unreached_component_count` -- rather than typed in, so renaming the key
in `src/` moves what this file demands of the label instead of leaving it
checking a word the artifact no longer uses.

**No file is named, on purpose.** The stats began in `ResultsDashboard.jsx` and
moved to `StatRail.jsx` when the report became a three-column layout, breaking
three tests here that had the path written down. Every `<Stat />` is swept out of
`frontend/src/**.jsx` now, so the next move needs no edit here -- and the floor
at the end is what still fails if the stats vanish altogether.

**The two numbers for one fact now sit in two files, and that is the point.**
The stat is in `StatRail.jsx`; the prose that explains a zero -- "N dependencies
carry a known advisory... none is reached by an LLM surface" -- is in
`ResultsDashboard.jsx`, which keeps its own binding of the same key. Each side
is resolved in its own file, directly or through a `const` bound there, so a
binding changed on one side and not the other fails the test that ties them.

**What only a string match can do, and it is one.** That "unreached" is *true*
of the number is `checks/known_advisory.py`'s claim; that the key exists at all
is `test_jsx_coverage_fields.py`'s sweep. What is left is whether the page says
the qualifier, and the honest form of that is a word-level check on the label --
with the label that shipped planted below, so it is shown to discriminate.

No fastapi and no node: this reads the JSX as text and one coverage block from
`src/`.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from advisory_fixtures import ADVISORY_PIN, unreached_items
from artifacts.coverage import ADVISORY_SNAPSHOT, coverage

from .jsx_sweep import strip_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

# The coverage key the stat counts, and the word in it that makes the count a
# part rather than a total. Both are checked against `src/` below rather than
# trusted: the key against a block the builder writes, the word against the key.
UNREACHED_COUNT_KEY = "advisory_unreached_component_count"
QUALIFIER = "unreached"

# The label that shipped, which is the one this file exists to refuse: a total
# claimed over a partial count.
LABEL_THAT_CLAIMED_EVERYTHING = "Vulnerable deps"

# One `<Stat ... />` element, and the two attributes every one of them must have.
STAT_ELEMENT = re.compile(r"<Stat\s(.*?)/>", re.DOTALL)
LABEL_ATTRIBUTE = re.compile(r'label="([^"]*)"')
VALUE_ATTRIBUTE = re.compile(r"value=\{(.*?)\}\s*$", re.DOTALL)

# A `const` bound to the key, for a file that reads it once and uses it twice.
COUNT_BINDING = re.compile(rf"const (\w+) = [^;\n]*\b{UNREACHED_COUNT_KEY}\b")

# The prop that carries the same number to the card whose prose explains a zero.
CARD_PROP = re.compile(r"unreached=\{([^}]*)\}")

# A floor under the sweep: four headline stats today, in one file. A parse that
# found none would satisfy every check below.
MINIMUM_STATS = 4


@dataclass(frozen=True)
class StatDeclaration:
    """One `<Stat />` the page declares: where it is, what it says, what it shows."""

    file: str
    label: str
    value: str


def sources() -> dict[str, str]:
    """Every component the page ships, keyed by file name, with comments stripped."""
    return {source.name: strip_comments(source.read_text(encoding="utf-8"))
            for source in sorted(FRONTEND_SRC.rglob("*.jsx"))}


def _attribute(pattern: re.Pattern, attributes: str) -> str:
    """One attribute of one stat, or the empty string when it has none."""
    found = pattern.search(attributes)
    return found.group(1).strip() if found else ""


def stats() -> list[StatDeclaration]:
    """Every headline stat the page declares, found without naming a file."""
    found: list[StatDeclaration] = []
    for name, text in sources().items():
        found += [StatDeclaration(name, _attribute(LABEL_ATTRIBUTE, attributes),
                                  _attribute(VALUE_ATTRIBUTE, attributes))
                  for attributes in STAT_ELEMENT.findall(text)]
    return found


def reaches_the_count(expression: str, source: str) -> bool:
    """Whether an expression reads the key, directly or through a `const` in its own file."""
    if UNREACHED_COUNT_KEY in expression:
        return True
    return any(re.search(rf"\b{name}\b", expression)
               for name in COUNT_BINDING.findall(source))


def stat_showing_the_count() -> StatDeclaration:
    """The one stat whose number is that key, or say how many the page has."""
    showing = [stat for stat in stats()
               if reaches_the_count(stat.value, sources()[stat.file])]
    assert len(showing) == 1, (
        f"{len(showing)} stats on the page show {UNREACHED_COUNT_KEY}; this file is "
        f"written for the one that shows the partial count, found in {showing}")
    return showing[0]


def card_prop() -> tuple[str, str]:
    """The file and expression that hand the same number to the card, or say it is gone."""
    for name, text in sources().items():
        found = CARD_PROP.search(text)
        if found:
            return name, found.group(1).strip()
    raise AssertionError("no component hands the unreached count to the findings card")


def qualifies(label: str) -> bool:
    """Whether a label carries the qualifier that makes its number a part, not a total."""
    return QUALIFIER in label.lower()


def a_coverage_block() -> dict:
    """One coverage block of an advisory run, as `src/` writes it."""
    items = unreached_items()
    return coverage(0, [], ADVISORY_SNAPSHOT, advisory_unreached_component_count=len(items),
                    advisory_unreached_components=items, **ADVISORY_PIN)


# --- the number the label sits over -------------------------------------------

def test_the_partial_count_the_stat_shows_is_a_key_the_artifact_carries() -> None:
    """First link: the key is one the coverage builder really publishes."""
    assert UNREACHED_COUNT_KEY in a_coverage_block()


def test_the_qualifier_demanded_of_the_label_is_a_word_of_that_key() -> None:
    """Second link: the word is taken from the key, so a rename in `src/` moves it."""
    assert QUALIFIER in UNREACHED_COUNT_KEY.split("_")


def test_exactly_one_headline_stat_shows_the_partial_count() -> None:
    """Third link: one stat reads that key, wherever the page keeps its stats."""
    assert stat_showing_the_count().value


# --- and what it says over it --------------------------------------------------

def test_the_label_over_the_partial_count_carries_the_qualifier() -> None:
    """The regression: `Vulnerable deps` over a count of the unreached ones claimed all."""
    stat = stat_showing_the_count()
    assert qualifies(stat.label), (
        f"{stat.file}: {stat.label!r} claims more than {UNREACHED_COUNT_KEY} counts")


def test_the_label_that_claimed_everything_would_not_pass_this() -> None:
    """Non-vacuity: the check is shown to refuse the wording that shipped."""
    assert not qualifies(LABEL_THAT_CLAIMED_EVERYTHING)


def test_the_prose_that_explains_a_zero_shows_the_same_number() -> None:
    """Two numbers for one fact is the same defect twice, and they now live in two files."""
    where, expression = card_prop()
    assert reaches_the_count(expression, sources()[where]), (
        f"{where}: {expression!r} no longer reads {UNREACHED_COUNT_KEY}")
    assert reaches_the_count(stat_showing_the_count().value,
                             sources()[stat_showing_the_count().file])


# --- and every other headline number ------------------------------------------

def test_every_headline_stat_has_a_label_and_a_number() -> None:
    """A number with no words over it is the general form of what went wrong here."""
    for stat in stats():
        assert stat.label, f"{stat.file}: a <Stat> with no label"
        assert stat.value, f"{stat.file}: a <Stat> labelled {stat.label!r} with no value"


def test_the_page_really_declares_the_headline_stats_this_file_read() -> None:
    """Non-vacuity: a sweep that matched nothing would satisfy every check above."""
    assert len(stats()) >= MINIMUM_STATS
