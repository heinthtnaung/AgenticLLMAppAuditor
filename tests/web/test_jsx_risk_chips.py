"""The risk-class filter row is a total function of the findings, run as JavaScript.

`FindingList.jsx` used to build its filter row out of `RISK_TONE`, so a risk
class that map has never heard of was counted in `All N`, given no chip, and
therefore unfilterable -- the same asymmetry `AdvisoryComponents.severitiesIn`
was fixed for, and `test_jsx_severity_chips.py` holds there. `classesIn` derives
the row from the findings now: the classes the map knows in its own order, then
anything else alphabetically.

**Nothing in `src/` can produce the input this file cares about, which is why it
is invented here.** `Finding.__post_init__` refuses an `owasp_id` outside
`OWASP_IDS`, so an unforeseen class can only reach the page from a findings.json
written by another build -- exactly the case a page should survive rather than
mis-count. The known classes below are real serialised findings; the unforeseen
ones are plain dicts, because the dataclass would not let one exist.

**It runs the page's own code.** The `RISK_TONE` declaration and `classesIn` are
lifted verbatim and evaluated under node over findings this test builds in
Python. A second Python implementation of the same ordering would only be tested
against itself. `test_jsx_severity_chips.py` lifts everything above the
component instead; that does not transfer here, because this file defines a
component (`Prose`) above the helper, so each binding is lifted by name.

The counting beside each chip is not lifted -- it sits inside the JSX -- so what
is asserted instead is the property that makes `All N` the sum of the chips:
every class present reaches the row exactly once.

Skipped when node is absent, as the vexctl and PDF-font tests skip: node builds
the committed `frontend/dist/`, so it is a prerequisite rather than a dependency
of this suite. Nothing here needs fastapi, the network, or a rebuilt bundle.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from artifacts.finding import OWASP_IDS
from findings_fixtures import produced_finding

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENT = REPO_ROOT / "frontend" / "src" / "components" / "FindingList.jsx"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The two bindings the row is built from, each lifted by name: the map, and the
# function over it. Both are plain JavaScript -- no JSX, no import, no React.
TONE_MAP = re.compile(r"^const RISK_TONE = \{.*?^\};", re.MULTILINE | re.DOTALL)
CLASSES_IN = re.compile(r"^function classesIn\(.*?^\}", re.MULTILINE | re.DOTALL)

# A `className={`...`}` template. Backticks do not nest in this file, so a whole
# template can be lifted and evaluated as written.
CLASS_TEMPLATE = re.compile(r"className=\{(`[^`]*`)\}")

# Risk classes to put through the page: two the tool can report, and two nobody
# has ever emitted. Uppercase, so JavaScript's `.sort()` and Python's `sorted()`
# order them the same way.
KNOWN_CLASSES = (OWASP_IDS[0], OWASP_IDS[-1])
INVENTED_CLASSES = ("ZEBRA-RISK", "ALPHA-RISK")

# How many findings one class gets in the mixed input below, so a row built by
# accident cannot coincide with the right one.
FINDINGS_PER_CLASS = 3


def component() -> str:
    """The findings table's own source, as text."""
    return COMPONENT.read_text(encoding="utf-8")


def stylesheets() -> str:
    """Every stylesheet the page ships, concatenated: the classes are looked up here."""
    return "\n".join(sheet.read_text(encoding="utf-8")
                     for sheet in sorted(FRONTEND_SRC.rglob("*.css")))


def lifted(pattern: re.Pattern, what: str) -> str:
    """One binding of the component, lifted verbatim, or say which one moved."""
    found = pattern.search(component())
    assert found, f"{COMPONENT.name} no longer declares {what}"
    assert "import " not in found.group(0), f"{what} now imports something node cannot resolve"
    return found.group(0)


def helpers() -> str:
    """The map and the function that reads it, which is all the row needs."""
    return f"{lifted(TONE_MAP, 'RISK_TONE')}\n{lifted(CLASSES_IN, 'classesIn')}\n"


def tone_templates() -> list[str]:
    """Every class-name template the component builds out of a risk tone."""
    return [found for found in CLASS_TEMPLATE.findall(component()) if "RISK_TONE" in found]


def run_in_node(program: str, argument: object, tmp_path: Path) -> object:
    """Evaluate one program over a JSON argument and return the JSON it printed."""
    script = tmp_path / "risk_probe.mjs"
    script.write_text(program, encoding="utf-8")
    done = subprocess.run([NODE, str(script), json.dumps(argument)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused the component's helpers:\n{done.stderr}"
    return json.loads(done.stdout)


def chips(findings: list[dict], tmp_path: Path) -> list[str]:
    """The filter row the page builds for one findings list, in its own order."""
    program = (f"{helpers()}"
               "const findings = JSON.parse(process.argv[2]);\n"
               "console.log(JSON.stringify(classesIn(findings)));\n")
    return run_in_node(program, findings, tmp_path)


def classes_for(owasp_id: str, tmp_path: Path) -> list[str]:
    """Every class name the page builds for one risk class, evaluated as written."""
    program = (f"{lifted(TONE_MAP, 'RISK_TONE')}\n"
               "const finding = JSON.parse(process.argv[2]);\n"
               f"console.log(JSON.stringify([{', '.join(tone_templates())}]));\n")
    built = run_in_node(program, {"owasp_id": owasp_id}, tmp_path)
    return [name for built_class in built for name in built_class.split()]


def findings_carrying(*owasp_ids: str) -> list[dict]:
    """One finding per class named, real where the dataclass can build one."""
    return [_one_finding(owasp_id, number)
            for number, owasp_id in enumerate(owasp_ids, start=1)]


def _one_finding(owasp_id: str, number: int) -> dict:
    """A serialised finding, or the least a page needs where `Finding` refuses the class."""
    if owasp_id in OWASP_IDS:
        return produced_finding(owasp_id=owasp_id, line=number)
    return {"owasp_id": owasp_id, "finding_id": f"invented-{number}"}


# --- a class the page has never heard of ---------------------------------------

def test_a_risk_class_the_tone_map_never_heard_of_gets_a_chip_of_its_own(tmp_path) -> None:
    """The regression: it was counted in `All N` with no way to filter to it."""
    shown = chips(findings_carrying(KNOWN_CLASSES[0], INVENTED_CLASSES[0]), tmp_path)
    assert shown == [KNOWN_CLASSES[0], INVENTED_CLASSES[0]]


def test_two_unforeseen_classes_sort_after_the_known_ones_and_among_themselves(
        tmp_path) -> None:
    """Alphabetical among themselves: there is no risk order to put them in."""
    carried = findings_carrying(*INVENTED_CLASSES, *KNOWN_CLASSES)
    assert chips(carried, tmp_path) == [*KNOWN_CLASSES, *sorted(INVENTED_CLASSES)]


# --- and the classes that are not there ----------------------------------------

def test_a_class_the_map_knows_but_no_finding_carries_gets_no_chip(tmp_path) -> None:
    """Derived from the findings, not the map: a chip that filters to nothing is noise."""
    assert chips(findings_carrying(KNOWN_CLASSES[0]), tmp_path) == [KNOWN_CLASSES[0]]


def test_a_class_many_findings_carry_gets_exactly_one_chip(tmp_path) -> None:
    """Two chips for one class would double the row and filter identically twice.

    Both halves in one input on purpose: a known class is deduplicated by being
    looked up in the map, and only an unforeseen one needs the `Set`.
    """
    carried = findings_carrying(*[KNOWN_CLASSES[0], INVENTED_CLASSES[0]] * FINDINGS_PER_CLASS)
    assert chips(carried, tmp_path) == [KNOWN_CLASSES[0], INVENTED_CLASSES[0]]


def test_every_class_the_findings_carry_reaches_the_row_once(tmp_path) -> None:
    """What makes `All N` the sum of the chips: each class present, counted once."""
    carried = findings_carrying(*(KNOWN_CLASSES + INVENTED_CLASSES) * FINDINGS_PER_CLASS)
    shown = chips(carried, tmp_path)
    assert sorted(shown) == sorted({finding["owasp_id"] for finding in carried})
    assert len(shown) == len(set(shown))


def test_findings_that_carry_nothing_build_no_row_at_all(tmp_path) -> None:
    """Non-vacuity: a probe returning a constant would pass every assertion above."""
    assert chips([], tmp_path) == []


# --- and what an unforeseen class is shown with --------------------------------

def test_the_class_name_an_unforeseen_risk_class_renders_with_has_a_rule(
        tmp_path) -> None:
    """Its chip is filterable and its tag must still be visible: no class without a rule."""
    styles = stylesheets()
    undefined = [name for name in classes_for(INVENTED_CLASSES[0], tmp_path)
                 if f".{name}" not in styles]
    assert undefined == [], f"no stylesheet defines {undefined}"


def test_the_component_really_builds_its_classes_out_of_the_tone_map(tmp_path) -> None:
    """Non-vacuity: no template found would leave the rule above checking nothing."""
    assert tone_templates()
    assert classes_for(KNOWN_CLASSES[0], tmp_path)
