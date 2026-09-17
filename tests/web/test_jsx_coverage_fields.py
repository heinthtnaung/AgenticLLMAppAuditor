"""Every coverage key the advisory section reads is a key that block really carries.

`AdvisoryComponents.jsx` renders the vulnerable dependencies no LLM surface
reaches -- 79 components carrying 311 advisories on the run that prompted it,
and the page showed none of them, which is the reported defect this file stands
under. It reads them off `findings.json`'s `coverage`: the block itself, each
`{purl, advisories}` item under `item.`, and each `{id, severity}` advisory
under `advisory.`.

Three shapes, one silent boundary, the same as `test_jsx_record_fields.py`
covers for the findings and the run record: JavaScript answers `undefined` for a
key that does not exist and React renders `undefined` as nothing at all, so a
misspelling is invisible from both sides. `FindingList.jsx` read
`finding.evidence` for weeks.

**The allowed keys are read off the builders, not transcribed.** One coverage
block is built through `src/artifacts/coverage.py` carrying a list from
`src/checks/known_advisory.py`, and the keys of what comes out are what the JSX
may read -- the same derivation `tests/artifacts/test_coverage_fields.py` makes
for the Python readers of the block. A test below holds that the findings
document hands the page that block unchanged, so there is no third shape in
between for either end to drift from.

What this cannot see: a key read through a variable, or one reached after
destructuring; `jsx_sweep.py` says what its regex does match. A `.js` module is
outside it too.

No fastapi here. It reads the JSX as text and the block from `src/`, so this
runs on a clean checkout with no web extra installed.
"""

from advisory_fixtures import ADVISORY_PIN, unreached_items
from artifacts.findings_document import (
    ADVISORY_SNAPSHOT, MODEL_DISABLED, build_findings_document, coverage, model_run)
from checks.known_advisory import CHECK_NAME as ADVISORY_CHECK

from .jsx_sweep import accessors, field_names, unknown

# The three names the section binds, spelled as the JSX spells them: the block it
# is handed, one unreached component of it, one advisory against that component.
COVERAGE = "coverage"
UNREACHED_ITEM = "item"
ADVISORY = "advisory"

# The two coverage keys the section is built on. `coverage.py` holds them null or
# sized together, and the page reads them apart -- the count as a headline stat,
# the list as the section -- so a sweep that reached only one half would leave
# the reported failure (a count with nothing behind it) unguarded.
UNREACHED_COUNT_KEY = "advisory_unreached_component_count"
UNREACHED_LIST_KEY = "advisory_unreached_components"

# Floors under each sweep: one that matched nothing would otherwise pass having
# checked nothing. Ten `coverage.` reads across four components today -- seven
# distinct keys, one of the reads rendered prose rather than code, and two of
# them in `StatRail.jsx`, which the `*.jsx` glob picked up the day that file was
# split out of the dashboard -- then five off the items and five off the
# advisories. Each floor sits under that, so an ordinary edit need not move it,
# and a file added to the page is swept without one being touched.
MINIMUM_COVERAGE_ACCESSORS = 6
MINIMUM_UNREACHED_ITEM_ACCESSORS = 4
MINIMUM_ADVISORY_ACCESSORS = 4

# A key no coverage block has ever published: the plausible short spelling of the
# count key above. Planted, to show the check reports rather than tolerates one.
COVERAGE_KEY_THAT_DOES_NOT_EXIST = "advisory_count"


def advisory_coverage() -> dict:
    """One coverage block of an advisory run, carrying the components nothing reaches."""
    items = unreached_items()
    return coverage(len(items), [ADVISORY_CHECK], ADVISORY_SNAPSHOT,
                    advisory_unreached_component_count=len(items),
                    advisory_unreached_components=items, **ADVISORY_PIN)


def served_coverage_fields() -> set[str]:
    """Every key the coverage block carries, read off the builder that writes it."""
    return set(advisory_coverage())


def an_unreached_component() -> dict:
    """One `{purl, advisories}` item, as `known_advisory.unreached_components` builds it."""
    return advisory_coverage()[UNREACHED_LIST_KEY][0]


def served_unreached_item_fields() -> set[str]:
    """Every key one unreached component carries."""
    return set(an_unreached_component())


def served_advisory_fields() -> set[str]:
    """Every key one advisory against such a component carries."""
    return set(an_unreached_component()["advisories"][0])


# --- what the page reads exists -----------------------------------------------

def test_every_coverage_field_the_page_reads_exists() -> None:
    """The reported defect's own data: 79 vulnerable components, rendered as nothing."""
    assert unknown(COVERAGE, served_coverage_fields(), accessors(COVERAGE)) == []


def test_every_unreached_component_field_the_page_reads_exists() -> None:
    """Each item is a purl and its advisories, and the section renders both."""
    assert unknown(UNREACHED_ITEM, served_unreached_item_fields(),
                   accessors(UNREACHED_ITEM)) == []


def test_every_advisory_field_the_page_reads_exists() -> None:
    """`advisory.severity` is the one the section must read to say `unrated` at all."""
    assert unknown(ADVISORY, served_advisory_fields(), accessors(ADVISORY)) == []


# --- the sweep really swept ---------------------------------------------------

def test_the_sweep_read_the_advisory_sections_accessors() -> None:
    """Guard: three empty lists would satisfy every check above having read nothing."""
    assert len(accessors(COVERAGE)) >= MINIMUM_COVERAGE_ACCESSORS
    assert len(accessors(UNREACHED_ITEM)) >= MINIMUM_UNREACHED_ITEM_ACCESSORS
    assert len(accessors(ADVISORY)) >= MINIMUM_ADVISORY_ACCESSORS


def test_the_page_reads_both_halves_of_the_unreached_fact() -> None:
    """The count is a stat and the list is the section: a page with one of them lies."""
    assert {UNREACHED_COUNT_KEY, UNREACHED_LIST_KEY} <= field_names(COVERAGE)
    assert {UNREACHED_COUNT_KEY, UNREACHED_LIST_KEY} <= served_coverage_fields()


def test_a_coverage_key_the_block_does_not_publish_is_reported_and_named() -> None:
    """Guard on the check itself: a plausible misspelling is named with its file."""
    planted = [("AdvisoryComponents.jsx", COVERAGE_KEY_THAT_DOES_NOT_EXIST)]
    assert unknown(COVERAGE, served_coverage_fields(), planted) == [
        f"AdvisoryComponents.jsx: {COVERAGE}.{COVERAGE_KEY_THAT_DOES_NOT_EXIST}"]


# --- the block the page is served is the block the keys came from -------------

def test_the_findings_document_hands_the_page_the_coverage_block_unchanged() -> None:
    """Pins the derivation: what `coverage()` builds is what the browser is served.

    `web/artifacts_read.py` returns the document unmodified, so the block the
    allowed keys were derived from is the block the JSX reads -- there is no
    third shape in between to drift from either end.
    """
    block = advisory_coverage()
    document = build_findings_document([], [], block, model_run(MODEL_DISABLED))
    assert document["coverage"] == block
