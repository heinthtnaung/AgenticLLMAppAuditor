"""The flags a run asked for, both arms of one ternary.

Split from `test_jsx_run_options.py`, which holds the two model names. Same
component, and the reason for the split is in the second paragraph: asserting
one arm of a conditional properly costs a constant, a regex and a plant, and
doing that to both arms took the file past the ~200-line rule.

**A run with no flags says "defaults" rather than nothing.** An empty cell reads
as "this row has no data", which is the gap-shown-as-a-result failure this whole
project is about, one row deep.

**Both arms are asserted, and for a while only one was.** The
`chosen.length === 0` arm was planted twice over while the other -- the tags for
the flags a run actually ticked -- had no assertion at all, so replacing it with
`null` left a run that asked for all three showing exactly the empty cell the
paragraph above objects to. **A plant on one arm of a conditional says nothing
about the other**, and that asymmetry is worth keeping in mind wherever a
ternary renders two different things.

**And neither arm says anything about the list they branch on.** With both arms
pinned, inverting the predicate to `!options[key]` was still missed: the column
then reports the flags a run did **not** ask for, so a defaults-only run shows
all three tags and a run that ticked all three shows "defaults". Every word on
screen is a lie and the shape of the render is untouched. The premise is a third
claim, and it is asserted here: `chosen` is the flags whose option is **true**.

Which *keys* the table may be written with is `test_jsx_stored_option_fields.py`;
this is about what reaches a reader once they are right.

No test in this suite renders React -- a recorded defect -- so this is the
source read as text: it can show a branch is *written*, not what it paints.

Reads one component as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

COMPONENT = FRONTEND_SRC / "components" / "RunOptions.jsx"

# What a run that ticked nothing shows, joined to the branch that chooses it:
# the class alone could be rendered from anywhere, including unconditionally,
# beside the flags a run *did* ask for.
THE_DEFAULTS_BRANCH = re.compile(
    r'chosen\.length === 0\s*\?\s*<span className="tag tag--rule">defaults</span>')

# The same tag with nothing choosing it, as the plant.
A_DEFAULTS_TAG_NOBODY_CHOSE = '<span className="tag tag--rule">defaults</span>'

# What the two arms branch on. Pinning both arms says nothing about the list
# they read, and inverting this predicate turns every tag on the row into its
# opposite while leaving the markup identical.
THE_SELECTION = "const chosen = FLAGS.filter(([key]) => options[key]);"

# The inversion, as its plant.
THE_SELECTION_INVERTED = "const chosen = FLAGS.filter(([key]) => !options[key]);"

# The other arm: one tag per flag the run really carried.
THE_CHOSEN_FLAGS = re.compile(
    r": chosen\.map\(\(\[key, label\]\) => \(\s*"
    r'<span key=\{key\} className="tag tag--mid">\{label\}</span>')

# The arm emptied out, as its plant.
AN_ARM_THAT_RENDERS_NOTHING = "        : null}\n"

# A floor, so a file this test failed to read cannot satisfy the checks above.
MINIMUM_ELEMENTS = 5


def component() -> str:
    """The component's own source, comments stripped."""
    return strip_comments(COMPONENT.read_text(encoding="utf-8"))


# --- and a run that ticked nothing says so -------------------------------------

def test_a_run_with_no_flags_is_shown_as_asking_for_the_defaults() -> None:
    """An empty cell reads as missing data; "defaults" is what actually happened."""
    assert THE_DEFAULTS_BRANCH.search(component())


def test_a_defaults_tag_nothing_chooses_is_not_accepted() -> None:
    """Planted: the class alone would render "defaults" beside the flags a run did ask for."""
    assert THE_DEFAULTS_BRANCH.search(A_DEFAULTS_TAG_NOBODY_CHOSE) is None


def test_the_flags_a_run_did_ask_for_are_rendered_one_tag_each() -> None:
    """The other arm: emptied, a run that ticked all three shows the blank this file objects to."""
    assert THE_CHOSEN_FLAGS.search(component())


def test_an_arm_that_renders_nothing_is_not_accepted() -> None:
    """Planted: the first arm was planted twice over while this one was unasserted."""
    assert THE_CHOSEN_FLAGS.search(AN_ARM_THAT_RENDERS_NOTHING) is None


def test_the_tags_are_the_flags_whose_option_was_true() -> None:
    """Measured MISSED with both arms pinned: inverted, every word on the row is its opposite."""
    assert THE_SELECTION in component()


def test_an_inverted_selection_is_not_accepted() -> None:
    """Planted: the render is character-identical, so only the predicate carries the claim."""
    assert THE_SELECTION not in THE_SELECTION_INVERTED


def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component satisfies both plants above."""
    assert len(re.findall(r"<[A-Za-z]", component())) >= MINIMUM_ELEMENTS
