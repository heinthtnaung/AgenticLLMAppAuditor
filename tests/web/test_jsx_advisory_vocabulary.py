"""The advisory section's vocabulary: four rated words, one unrated, and two states.

`AdvisoryComponents.jsx` renders the vulnerable dependencies no LLM surface
reaches. To do it, it spells three things no compiler checks for it: the
severity words the advisory database uses, the word for an advisory that
database did *not* rate, and the literal for "no advisory database was read at
all". `test_jsx_record_fields.py` holds that the *keys* it reads exist; this
holds that the *values* it words are the ones the artifact can carry.

**The severity words are a pin, not a derivation, and the difference is the
point.** `deps/trivy_runner.py` quotes Trivy's own `Severity` field verbatim and
`checks/known_advisory.py` carries the quotation into `coverage`, so the
vocabulary belongs to the database and nothing in `src/` narrows it -- a
coverage block would accept any word at all in an item, which is why the four
below are written down here with their source named rather than read out of a
constant that does not exist. Trivy has a fifth word, `UNKNOWN`, and it is
deliberately not one of them: the runner keeps a severity word only when the
same source also carries the CVSS vector that attributes it, and an unrated
record carries none, so it reaches the artifact as `null`. That null is what
the section renders as `unrated` -- 46 of the 311 advisories on the run that
prompted this section are that case, and showing them as `low` would be this
tool inventing a rating out of a database that gave none.

**`not_ingested` is a third state, not an empty list.** "No advisory database
was read" and "the database was read and matched nothing" are different
sentences to a reader, and the section says both -- so the tests below check
each branch for the claim only it can make. The literal is bound to
`src/artifacts/coverage.py`'s own constant, the way `test_run_routes.py` binds
`GET /api/stages` to `progress.STAGES`. The other state needs no literal in the
page: everything that is not `not_ingested` is a snapshot, which is safe only
while the vocabulary is closed at two, and
`tests/artifacts/test_findings_document.py` holds the refusal of a third.

**One boundary here is invisible to the bundle sweep.** A tone becomes a class
name inside a template literal, and `test_built_page_shipped.py` skips braced
class names on purpose because they never appear whole in the built bundle. So a
tone with no rule behind it -- a tag with no colour, a bar with no fill -- is
caught here, over every entry the map declares, with no node needed.
`test_jsx_severity_chips.py` checks the harder half of the same thing, by
evaluating those templates for severities the map does *not* declare, and skips
where node is absent.

No fastapi: this reads two JSX files and the stylesheets as text, and two
constants out of `src/`.
"""

import re
from pathlib import Path

from advisory_fixtures import ADVISORY_PURL, advisory_record, unreached_items
from artifacts.coverage import ADVISORY_NOT_INGESTED, ADVISORY_SNAPSHOT

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
SECTION = FRONTEND_SRC / "components" / "AdvisoryComponents.jsx"
DASHBOARD = FRONTEND_SRC / "components" / "ResultsDashboard.jsx"

# Trivy's rated severity words, worst first, which is also the display order.
# A pin and not a derivation -- see the module docstring for whose vocabulary
# this is and why `UNKNOWN` is absent from it.
RATED_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# What the section calls an advisory the database did not rate, the map key it
# is held under, and the expression that reaches it: from a null severity, never
# from the lowest rating.
UNRATED = "unrated"
UNRATED_TONE_KEY = "[UNRATED]"
LOWEST_RATING = "LOW"
NULL_SEVERITY_FALLBACK = "advisory.severity ?? UNRATED"

# How a tone becomes a class name: `--${TONE[...]}` inside a template literal.
# The stem in front of it is read out of the source rather than written down
# here -- the styling is presentation and will move again, and what has to hold
# is that whatever stem is used has a rule behind it.
TONE_CLASS_PATTERN = re.compile(r"([\w-]+)--\$\{TONE\[")

# The anchors that separate the section's two branches: the state test opens the
# refusal, and binding the item list opens the snapshot path.
STATE_BRANCH = "coverage.advisory_data === NOT_INGESTED"
SNAPSHOT_PATH_BEGINS = "const items ="

# One phrase from each branch -- the claim only that branch can make. Nothing was
# looked at, against a database that was read and matched nothing.
NOTHING_CHECKED = "nothing was checked"
MATCHED_NOTHING = "matched nothing"

# How the dashboard reaches the section at all. A component nobody renders is
# the reported defect ("only LLM surfaces") in a new place.
SECTION_IMPORT = 'from "./AdvisoryComponents.jsx"'
SECTION_ELEMENT = "<AdvisoryComponents"


def section() -> str:
    """The advisory section's own source, as text."""
    return SECTION.read_text(encoding="utf-8")


def stylesheets() -> str:
    """Every stylesheet the page ships, concatenated: the tones are looked up here."""
    return "\n".join(sheet.read_text(encoding="utf-8")
                     for sheet in sorted(FRONTEND_SRC.rglob("*.css")))


def declared_string(name: str) -> str:
    """The value of a `const NAME = "..."` in the section, or name what is missing."""
    found = re.search(rf'const {name} = "([^"]*)";', section())
    assert found, f"{SECTION.name} declares no string constant {name}"
    return found.group(1)


def declared_words(name: str) -> list[str]:
    """The strings a `const NAME = [...]` in the section holds, in order."""
    found = re.search(rf"const {name} = \[([^\]]*)\];", section())
    assert found, f"{SECTION.name} declares no list constant {name}"
    return re.findall(r'"([^"]*)"', found.group(1))


def tone_of(key: str) -> str:
    """The class tone the section's `TONE` map gives one severity."""
    found = re.search(rf'{re.escape(key)}: "([^"]+)"', section())
    assert found, f"{SECTION.name}'s TONE map has no entry for {key}"
    return found.group(1)


def tones() -> list[str]:
    """Every tone that map holds, each of which becomes a class name."""
    block = re.search(r"const TONE = \{(.*?)\};", section(), re.DOTALL)
    assert block, f"{SECTION.name} declares no TONE map"
    return re.findall(r': "([^"]+)"', block.group(1))


def tone_class_stems() -> set[str]:
    """Every class stem the section builds out of a tone, `tag` and `bar` today."""
    return set(TONE_CLASS_PATTERN.findall(section()))


def flattened(text: str) -> str:
    """One line, single-spaced: JSX prose is wrapped, so a sentence spans the wrap."""
    return " ".join(text.split())


def _at(anchor: str, start: int = 0) -> int:
    """Where an anchor sits in the section, or say which anchor moved."""
    found = section().find(anchor, start)
    assert found != -1, f"{SECTION.name} no longer holds the anchor {anchor!r}"
    return found


def refusal_branch() -> str:
    """The `not_ingested` branch's own text, up to where the snapshot path begins."""
    start = _at(STATE_BRANCH)
    return section()[start:_at(SNAPSHOT_PATH_BEGINS, start)]


def snapshot_branch() -> str:
    """The snapshot path's own text, which is the rest of the section."""
    return section()[_at(SNAPSHOT_PATH_BEGINS):]


# --- the section is reached at all ---------------------------------------------

def test_the_dashboard_renders_the_advisory_section() -> None:
    """The reported defect: the data was in the document and nothing put it on the page."""
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    assert SECTION_IMPORT in dashboard
    assert SECTION_ELEMENT in dashboard


# --- the severity words --------------------------------------------------------

def test_the_severity_words_the_section_renders_are_the_databases_own() -> None:
    """Four rated words, worst first, quoted from Trivy and never chosen here."""
    assert declared_words("SEVERITIES") == RATED_SEVERITIES


def test_the_word_for_an_unrated_advisory_is_not_one_of_the_ratings() -> None:
    """A database that rated nothing is not a database that rated something low."""
    assert declared_string("UNRATED") == UNRATED
    assert UNRATED not in declared_words("SEVERITIES")


def test_a_null_severity_falls_back_to_unrated_and_not_to_a_rating() -> None:
    """The one expression that decides it: `?? UNRATED`, on the null the artifact carries."""
    assert NULL_SEVERITY_FALLBACK in section()


def test_an_advisory_with_no_rating_is_a_shape_the_artifact_really_carries() -> None:
    """Non-vacuity for the case above: `src/` writes that null, so the page must meet it."""
    items = unreached_items({ADVISORY_PURL: [advisory_record(severity=None)]})
    assert items[0]["advisories"][0]["severity"] is None


# --- and how they are shown ----------------------------------------------------

def test_unrated_is_not_shown_in_the_tone_the_lowest_rating_gets() -> None:
    """Same argument in the styling: `unrated` and `low` may not read as one thing."""
    assert tone_of(UNRATED_TONE_KEY) != tone_of(LOWEST_RATING)


def test_every_tone_the_section_maps_to_has_a_rule_in_the_stylesheets() -> None:
    """A braced class name no other test can see: a tone with no rule is a blank tag."""
    styles = stylesheets()
    missing = [f".{stem}--{tone}" for tone in tones() for stem in tone_class_stems()
               if f".{stem}--{tone}" not in styles]
    assert missing == [], f"no stylesheet defines {missing}"


def test_the_tones_really_reach_the_page_as_class_names() -> None:
    """Non-vacuity for the rule above: no stem found would leave it checking nothing."""
    assert tone_class_stems()


def test_the_tone_map_really_holds_a_tone_for_every_word_it_shows() -> None:
    """Guard: an unparsed map would leave the stylesheet sweep with nothing to look up."""
    assert len(tones()) == len(RATED_SEVERITIES) + 1


# --- the third state -----------------------------------------------------------

def test_the_state_the_section_branches_on_is_the_constant_python_owns() -> None:
    """One literal, two languages: bound here so a rename in `src/` cannot pass quietly."""
    assert declared_string("NOT_INGESTED") == ADVISORY_NOT_INGESTED
    assert STATE_BRANCH in section()


def test_the_snapshot_state_needs_no_literal_in_the_page() -> None:
    """Everything that is not `not_ingested` is a snapshot, so one literal covers two states.

    A page that grew a second branch would be spelling a second Python constant
    by hand, unbound: this failing is the prompt to bind it here as well.
    """
    assert ADVISORY_SNAPSHOT not in section()


def test_the_not_ingested_branch_says_that_nothing_was_checked() -> None:
    """"No advisory data" has to read as a gap, which is what the scorer calls it too."""
    assert NOTHING_CHECKED in flattened(refusal_branch())
    assert MATCHED_NOTHING not in flattened(refusal_branch())


def test_the_empty_snapshot_branch_says_the_database_matched_nothing() -> None:
    """The other sentence: a database was read, and this time it is a real clean result."""
    assert MATCHED_NOTHING in flattened(snapshot_branch())
    assert NOTHING_CHECKED not in flattened(snapshot_branch())
