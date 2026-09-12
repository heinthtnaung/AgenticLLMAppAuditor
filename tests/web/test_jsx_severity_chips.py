"""The severity chips are a total function of the data, run as JavaScript to prove it.

`AdvisoryComponents.jsx` used to hold a fixed severity list and sum its total
over that list, so a word outside it was counted in `counts`, left out of both
the chips and the total, and silently unfilterable. It now derives the chip list
from the data -- known words worst-first, then anything it has never heard of,
then `unrated` last, because the absence of a rating is not the mildest rating
-- and sums the total from every count instead.

**Trivy's fifth word is the known instance of the problem, and this file does
not need it.** `UNKNOWN` is a rating the database chose, distinct from `unrated`
which means it rated nothing; `deps/trivy_runner.py` copies the word verbatim,
so nothing in `src/` narrows what can arrive and no `src/` fixture can be made
to *guarantee* an `UNKNOWN`. That is the point of the fix: the page is a total
function over any severity string, so the property is asserted over strings this
test invents rather than over a vocabulary anything owns.

**It runs the page's own code.** Everything above the section's first React
component is plain JavaScript, and the three bindings the chips are built from
-- `counts`, `present`, `total` -- are lifted out of the component verbatim and
evaluated under node over an artifact this test builds in Python. A second
Python implementation of the same arithmetic would only be tested against
itself; the sibling files sweep the JSX as text, which cannot evaluate anything.

Skipped when node is absent, the way the vexctl and PDF-font tests skip: node
builds `frontend/dist/`, which is committed, so it is a prerequisite and not a
dependency of this suite. `test_jsx_advisory_vocabulary.py` covers the words and
the tones without it.

Nothing here needs fastapi, the network, or a rebuilt bundle: it reads the
component's source, not `dist/`.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from advisory_fixtures import advisory_record, unreached_items

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
SECTION = FRONTEND_SRC / "components" / "AdvisoryComponents.jsx"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Where the plain-JavaScript half of the section ends: at its first component,
# which is the first capitalised `function` in the file.
FIRST_COMPONENT = re.compile(r"^function [A-Z]", re.MULTILINE)
REACT_IMPORT = 'import { useState } from "react";'
EXPORTED_COMPONENT = "export default function AdvisoryComponents"

# The three bindings the chips and the total are built from, lifted from the
# component in the order it binds them. `items` is bound to this test's input
# instead: it is the artifact list, and the artifact is what a test provides.
LIFTED_BINDINGS = ("counts", "present", "total")

# A `className={`...`}` template. Backticks do not nest in this file, so the
# whole template can be lifted and evaluated as written.
CLASS_TEMPLATE = re.compile(r"className=\{(`[^`]*`)\}")

# The word the section uses for an advisory the database did not rate. Read back
# out of the section by `test_jsx_advisory_vocabulary.py`, which binds it; here
# it is the value expected in a chip list.
UNRATED = "unrated"

# Severity words to put through the page. Four the database rates, Trivy's fifth,
# two nobody has ever emitted, and the null that means it rated nothing at all.
INVENTED_WORDS = ("ZEBRA-RATING", "ALPHA-RATING")
EVERY_WORD = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN", *INVENTED_WORDS, None)

# What one severity's advisories are worth in the fixtures below, so a wrong
# total cannot coincide with a right one.
PER_SEVERITY = {"CRITICAL": 1, "HIGH": 2, "UNKNOWN": 3, None: 4}


def section() -> str:
    """The advisory section's own source, as text."""
    return SECTION.read_text(encoding="utf-8")


def pure_helpers() -> str:
    """The section's plain-JavaScript half: everything above its first component."""
    text = section()
    found = FIRST_COMPONENT.search(text)
    assert found, f"{SECTION.name} has no component after its helpers"
    helpers = text[:found.start()].replace(REACT_IMPORT, "")
    assert "import " not in helpers, "the helpers now import something node cannot resolve"
    return helpers


def component_body() -> str:
    """The exported component's own text, where the page binds what it renders."""
    text = section()
    found = text.find(EXPORTED_COMPONENT)
    assert found != -1, f"{SECTION.name} no longer exports {EXPORTED_COMPONENT}"
    return text[found:]


def binding(name: str) -> str:
    """The expression the component binds one name to, lifted verbatim."""
    found = re.search(rf"^\s*const {name} = (.+);$", component_body(), re.MULTILINE)
    assert found, f"{SECTION.name} no longer binds `{name}`"
    return found.group(1)


def tone_templates() -> list[str]:
    """Every class-name template the section builds out of a tone."""
    return [found for found in CLASS_TEMPLATE.findall(section()) if "TONE" in found]


def stylesheets() -> str:
    """Every stylesheet the page ships, concatenated: the classes are looked up here."""
    return "\n".join(sheet.read_text(encoding="utf-8")
                     for sheet in sorted(FRONTEND_SRC.rglob("*.css")))


def run_in_node(program: str, argument: object, tmp_path: Path) -> object:
    """Evaluate one program over a JSON argument and return the JSON it printed."""
    script = tmp_path / "severity_probe.mjs"
    script.write_text(program, encoding="utf-8")
    done = subprocess.run([NODE, str(script), json.dumps(argument)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused the section's helpers:\n{done.stderr}"
    return json.loads(done.stdout)


def rendered(items: list[dict], tmp_path: Path) -> dict:
    """What the page makes of one artifact list: its counts, its chips and its total."""
    lifted = "\n".join(f"const {name} = {binding(name)};" for name in LIFTED_BINDINGS)
    program = (f"{pure_helpers()}\n"
               "const items = JSON.parse(process.argv[2]);\n"
               f"{lifted}\n"
               f"console.log(JSON.stringify({{ {', '.join(LIFTED_BINDINGS)} }}));\n")
    return run_in_node(program, items, tmp_path)


def classes_for(severity: str | None, tmp_path: Path) -> list[str]:
    """Every class name the section builds for one severity, evaluated as written."""
    program = (f"{pure_helpers()}\n"
               "const severity = JSON.parse(process.argv[2]);\n"
               'const advisory = { id: "CVE-0000-0000", severity };\n'
               f"console.log(JSON.stringify([{', '.join(tone_templates())}]));\n")
    built = run_in_node(program, severity, tmp_path)
    return [name for built_class in built for name in built_class.split()]


def artifact_carrying(*severities: str | None) -> list[dict]:
    """One unreached component per severity, with `PER_SEVERITY` advisories each."""
    advisories = {}
    for index, severity in enumerate(severities):
        records = [advisory_record(f"CVE-2026-{index}{number}", severity=severity)
                   for number in range(PER_SEVERITY.get(severity, 1))]
        advisories[f"pkg:pypi/component-{index}@1.0.0"] = records
    return unreached_items(advisories)


# --- a word the page has never heard of ----------------------------------------

def test_an_unforeseen_severity_word_gets_a_chip_of_its_own(tmp_path) -> None:
    """Trivy's `UNKNOWN` is a rating the database chose, so it is filterable like any."""
    shown = rendered(artifact_carrying("CRITICAL", "UNKNOWN", None), tmp_path)
    assert shown["present"] == ["CRITICAL", "UNKNOWN", UNRATED]


def test_two_unforeseen_words_sort_between_the_known_ones_and_unrated(tmp_path) -> None:
    """Alphabetical among themselves: there is no severity order to put them in."""
    shown = rendered(artifact_carrying("HIGH", *INVENTED_WORDS, None), tmp_path)
    assert shown["present"] == ["HIGH", *sorted(INVENTED_WORDS), UNRATED]


def test_the_unrated_case_sorts_last_even_behind_the_lowest_rating(tmp_path) -> None:
    """The absence of a rating is not the mildest rating, so it does not sort as one."""
    shown = rendered(artifact_carrying("LOW", None), tmp_path)
    assert shown["present"] == ["LOW", UNRATED]


# --- the arithmetic ------------------------------------------------------------

def test_the_total_counts_every_advisory_the_artifact_carries(tmp_path) -> None:
    """Summed from the counts, so a word with no chip cannot fall out of the total."""
    carried = artifact_carrying("CRITICAL", "HIGH", "UNKNOWN", None)
    expected = sum(len(item["advisories"]) for item in carried)
    assert rendered(carried, tmp_path)["total"] == expected


def test_the_total_equals_the_sum_of_the_chips_beside_it(tmp_path) -> None:
    """The regression: a total and its chips disagreeing is the page's own arithmetic."""
    shown = rendered(artifact_carrying(*EVERY_WORD), tmp_path)
    assert sum(shown["counts"][severity] for severity in shown["present"]) == shown["total"]


def test_an_artifact_carrying_no_advisories_tallies_to_nothing(tmp_path) -> None:
    """Non-vacuity: a probe returning constants would pass every assertion above."""
    shown = rendered([], tmp_path)
    assert shown == {"counts": {}, "present": [], "total": 0}


# --- and what it is shown with -------------------------------------------------

def test_every_class_the_section_builds_for_a_severity_has_a_rule(tmp_path) -> None:
    """No severity may render with a class no stylesheet defines, invented or not."""
    styles = stylesheets()
    for severity in EVERY_WORD:
        undefined = [name for name in classes_for(severity, tmp_path)
                     if f".{name}" not in styles]
        assert undefined == [], f"{severity}: no stylesheet defines {undefined}"


def test_the_section_really_builds_its_classes_out_of_the_tone_map(tmp_path) -> None:
    """Non-vacuity: no template found would leave the rule above checking nothing."""
    assert tone_templates()
    assert classes_for("UNKNOWN", tmp_path)
