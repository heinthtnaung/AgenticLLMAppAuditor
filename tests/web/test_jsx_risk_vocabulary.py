"""The risk classes the findings table words are the ones `src/` can emit.

`FindingList.jsx` declares `RISK_TONE` with one key per risk class -- a second
copy of `OWASP_IDS`, which `src/artifacts/finding.py` owns and validates every
finding against. Two copies of a closed vocabulary in two languages, with
nothing holding them together, is the defect `GET /api/stages` was built to
avoid for the stage names: there the page asks the server for the list, here the
page spells it. So it is bound here instead, out of `src/` rather than
transcribed, and a rename or a sixth class fails this file rather than showing a
chip nobody can filter or a class the tool cannot report.

**Both directions are asserted, because they fail differently.** A class in
`OWASP_IDS` with no tone renders in the fallback tone and sorts with the
unforeseen ones -- readable, and wrong about what the tool knows. A tone for a
class `OWASP_IDS` does not carry is a page describing a risk this build cannot
report at all. Each has its own test so the failure names which side moved.

**Order is deliberately not pinned, and neither is which tone a class gets.**
The map's key order is the order the known chips appear in and its values are
colours; both are presentation, and a test that fixed them would fail on a
restyle that broke nothing. What has to hold is the membership -- and, because a
class name reaches the page inside a template literal that no bundle sweep can
see whole, that every tone named has a rule behind it. `test_jsx_risk_chips.py`
takes the harder half of the same subject by evaluating the page's own
`classesIn` under node.

No fastapi and no node here: this reads one JSX file and the stylesheets as
text, and one constant out of `src/`.
"""

import re
from pathlib import Path

from artifacts.finding import OWASP_IDS

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
COMPONENT = FRONTEND_SRC / "components" / "FindingList.jsx"

# The map's own name in the page, and one `KEY: "tone"` entry of it.
TONE_MAP = "RISK_TONE"
TONE_ENTRY = re.compile(r'([A-Za-z_]\w*): "([^"]+)"')

# How a tone becomes a class name: `--${RISK_TONE[...]}` inside a template
# literal. The stem in front of it is read out of the source rather than written
# down here -- the styling is presentation and will move again; what has to hold
# is that whatever stem is used has a rule behind it.
TONE_CLASS_PATTERN = re.compile(rf"([\w-]+)--\$\{{{TONE_MAP}\[")

# The tone a class the map has never heard of falls back to, read off the same
# expression. A finding carrying an unforeseen class still has to render.
FALLBACK_PATTERN = re.compile(rf'{TONE_MAP}\[[^\]]*\]\s*\?\?\s*"([^"]+)"')

# A risk class no build of this tool can report, and one it always can: planted
# below to show each sweep reports a drift rather than tolerating it.
CLASS_THAT_CANNOT_ARRIVE = "LLM99"
CLASS_THAT_ALWAYS_ARRIVES = OWASP_IDS[0]


def component() -> str:
    """The findings table's own source, as text."""
    return COMPONENT.read_text(encoding="utf-8")


def stylesheets() -> str:
    """Every stylesheet the page ships, concatenated: the tones are looked up here."""
    return "\n".join(sheet.read_text(encoding="utf-8")
                     for sheet in sorted(FRONTEND_SRC.rglob("*.css")))


def tone_map() -> dict[str, str]:
    """The `RISK_TONE` map as the page declares it: one tone per risk class."""
    block = re.search(rf"const {TONE_MAP} = \{{(.*?)\}};", component(), re.DOTALL)
    assert block, f"{COMPONENT.name} declares no {TONE_MAP} map"
    entries = TONE_ENTRY.findall(block.group(1))
    assert len(entries) == block.group(1).count(":"), (
        f"{COMPONENT.name}'s {TONE_MAP} has an entry this test cannot read, so the "
        "comparison below would be made against a partial map")
    return dict(entries)


def declared_classes() -> list[str]:
    """The risk classes the page names, which is `Object.keys(RISK_TONE)`."""
    return list(tone_map())


def without_a_tone(classes: list[str]) -> list[str]:
    """Every risk class the tool can report that the page has no entry for."""
    return sorted(set(OWASP_IDS) - set(classes))


def unreportable(classes: list[str]) -> list[str]:
    """Every class the page names that no finding could ever carry."""
    return sorted(set(classes) - set(OWASP_IDS))


def tone_class_stems() -> set[str]:
    """Every class stem the page builds out of a tone, `tag` today."""
    return set(TONE_CLASS_PATTERN.findall(component()))


def fallback_tone() -> str:
    """The tone a risk class outside the map is rendered in."""
    found = FALLBACK_PATTERN.search(component())
    assert found, f"{COMPONENT.name} reads {TONE_MAP} with no fallback tone"
    return found.group(1)


def undefined_classes(tones: list[str]) -> list[str]:
    """Every `stem--tone` class name no stylesheet defines."""
    styles = stylesheets()
    return sorted(f".{stem}--{tone}" for tone in tones for stem in tone_class_stems()
                  if f".{stem}--{tone}" not in styles)


# --- the two copies of the vocabulary agree -----------------------------------

def test_every_risk_class_the_tool_can_report_has_an_entry_in_the_page() -> None:
    """`OWASP_IDS` is the closed set a `Finding` is validated against; the page owns none of it."""
    assert without_a_tone(declared_classes()) == []


def test_the_page_names_no_risk_class_the_tool_cannot_report() -> None:
    """The other direction: a chip for a class no finding can carry describes nothing."""
    assert unreportable(declared_classes()) == []


def test_a_class_the_page_never_heard_of_is_reported_by_name() -> None:
    """Non-vacuity: planted, because both checks above are an empty list either way."""
    planted = [owasp for owasp in declared_classes() if owasp != CLASS_THAT_ALWAYS_ARRIVES]
    assert without_a_tone(planted) == [CLASS_THAT_ALWAYS_ARRIVES]


def test_a_class_the_tool_cannot_emit_is_reported_by_name() -> None:
    """The same guard on the other sweep: an extra key is named, not passed over."""
    assert unreportable([*declared_classes(), CLASS_THAT_CANNOT_ARRIVE]) == [
        CLASS_THAT_CANNOT_ARRIVE]


def test_the_map_really_parsed_before_either_sweep_read_it() -> None:
    """Guard: an unparsed map is an empty one, and an empty one fails for the wrong reason."""
    assert len(declared_classes()) == len(OWASP_IDS)


# --- and the tones they are shown in reach a stylesheet ------------------------

def test_every_tone_the_page_names_has_a_rule_in_the_stylesheets() -> None:
    """A braced class name the bundle sweep skips by design: no rule means a blank tag."""
    assert undefined_classes(list(tone_map().values())) == []


def test_the_tone_an_unforeseen_risk_class_falls_back_to_has_a_rule() -> None:
    """A class outside the map still renders, so its tone needs a rule as much as any."""
    assert undefined_classes([fallback_tone()]) == []


def test_the_tones_really_reach_the_page_as_class_names() -> None:
    """Non-vacuity: no stem found would leave both rules above checking nothing."""
    assert tone_class_stems()


def test_a_tone_with_no_rule_behind_it_is_reported_by_name() -> None:
    """Planted, because the stylesheet sweep is another check that returns an empty list."""
    assert undefined_classes(["nosuchtone"]) == [
        f".{stem}--nosuchtone" for stem in sorted(tone_class_stems())]
