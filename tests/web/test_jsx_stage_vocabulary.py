"""The four words a stage row can read, and what each of them is shown with.

`StageProgress.jsx` declares four states and renders each one twice over: as the
class `stage--<state>`, which colours the row, and as a lookup in `MARK`, which
is the tick or the dot beside it. Both are silent when they miss. A class no
stylesheet defines is an unstyled row, and `MARK[state]` for a state the map has
no entry for is `undefined`, which React renders as nothing at all -- so the
state that arrived with the fix, `unreached`, could have shipped as a blank row
with no mark and nothing would have said so.

`test_jsx_stage_states.py` holds *which* state a run gets, by evaluating the
page's own `stateOf` under node. This holds the presentation side of the same
four words, and needs no node: the class name is built inside a template literal
that `test_built_page_shipped.py` skips by design, and `MARK`'s keys are the
constant names themselves, so comparing identifiers is exact.

**The words are read, not written down here.** Only the four constant *names*
are spelled below; every value comes out of the component. What is deliberately
not pinned is which mark or which colour a state gets -- that is presentation,
the same reason `test_jsx_risk_vocabulary.py` does not pin a risk class's tone.

No fastapi and no node: this reads one JSX file and the stylesheets as text.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
COMPONENT = FRONTEND_SRC / "components" / "StageProgress.jsx"

# The constant names the component declares its four states under. The names are
# spelled here; the values are read out of the source below.
STATE_NAMES = ("DONE", "WORKING", "PENDING", "UNREACHED")

# How a state becomes a class name -- `stage--${state}` -- with the stem read
# out of the source rather than written down, because the styling is
# presentation and what has to hold is that whatever stem is used has a rule.
STATE_CLASS_PATTERN = re.compile(r"([\w-]+)--\$\{state\}")

# The map from state to the character shown beside the row, keyed by the
# constants themselves: `{ [DONE]: "✓", ... }`.
MARK_KEY_PATTERN = re.compile(r"\[(\w+)\]:")

# A state nothing declares, planted to show each sweep names a gap rather than
# tolerating one.
STATE_THAT_DOES_NOT_EXIST = "nosuchstate"


def component() -> str:
    """The progress list's own source, as text."""
    return COMPONENT.read_text(encoding="utf-8")


def stylesheets() -> str:
    """Every stylesheet the page ships, concatenated: the classes are looked up here."""
    return "\n".join(sheet.read_text(encoding="utf-8")
                     for sheet in sorted(FRONTEND_SRC.rglob("*.css")))


def word(name: str) -> str:
    """The value of a `const NAME = "..."` in the component, or name what is missing."""
    found = re.search(rf'const {name} = "([^"]*)";', component())
    assert found, f"{COMPONENT.name} declares no string constant {name}"
    return found.group(1)


def state_words() -> list[str]:
    """The four states a row can read, read off the component's own declarations."""
    return [word(name) for name in STATE_NAMES]


def class_stems() -> set[str]:
    """Every class stem the component builds out of a state, `stage` today."""
    return set(STATE_CLASS_PATTERN.findall(component()))


def marked_states() -> set[str]:
    """The constant names `MARK` has an entry for."""
    block = re.search(r"const MARK = \{(.*?)\};", component(), re.DOTALL)
    assert block, f"{COMPONENT.name} declares no MARK map"
    return set(MARK_KEY_PATTERN.findall(block.group(1)))


def undefined_classes(states: list[str]) -> list[str]:
    """Every `stem--state` class name no stylesheet defines."""
    styles = stylesheets()
    return sorted(f".{stem}--{state}" for state in states for stem in class_stems()
                  if f".{stem}--{state}" not in styles)


# --- every state is styled -----------------------------------------------------

def test_every_state_a_row_can_read_has_a_rule_in_the_stylesheets() -> None:
    """`stage--unreached` arrived with the fix; a state with no rule is an unstyled row."""
    assert undefined_classes(state_words()) == []


def test_a_state_with_no_rule_behind_it_is_reported_by_name() -> None:
    """Non-vacuity: the sweep above is an empty list either way, so one is planted."""
    assert undefined_classes([STATE_THAT_DOES_NOT_EXIST]) == [
        f".{stem}--{STATE_THAT_DOES_NOT_EXIST}" for stem in sorted(class_stems())]


def test_the_states_really_reach_the_page_as_class_names() -> None:
    """Non-vacuity: no stem found would leave the sweep above checking nothing."""
    assert class_stems()


# --- and every state is marked -------------------------------------------------

def test_every_state_a_row_can_read_has_a_mark_beside_it() -> None:
    """`MARK[state]` is `undefined` for a state it has no entry for, and renders as nothing."""
    assert sorted(set(STATE_NAMES) - marked_states()) == []


def test_the_mark_map_names_no_state_the_component_does_not_declare() -> None:
    """The other direction: a mark for a state nothing can be in is a dead entry."""
    assert sorted(marked_states() - set(STATE_NAMES)) == []


# --- the four words are four distinct words ------------------------------------

def test_the_four_states_are_four_different_words() -> None:
    """Two states spelled the same would collapse two claims the page has to keep apart."""
    assert len(set(state_words())) == len(STATE_NAMES)


def test_the_state_for_a_stage_never_reached_is_not_the_one_for_a_stage_still_to_come() -> None:
    """The regression in the vocabulary: `unreached` and `pending` may not read as one thing."""
    assert word("UNREACHED") != word("PENDING")
