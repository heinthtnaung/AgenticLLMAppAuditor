"""What a past run asked for is read off that run, never off what the server is set to now.

`RunOptions.jsx` renders one history row's options: the flags it was started
with and the two model names. Which *fields* it may read is
`test_jsx_stored_option_fields.py`; this file is the three rendering decisions,
each of which is wrong in a way that looks right.

**The local model may not be resolved against `GET /api/model`.** That endpoint
answers `configured_model` -- what `AUDITOR_MODEL` resolves to **now** -- and a
history row filling its blank from it would print today's setting as a past
run's fact. It is the same mistake `docs/SCHEMAS.md` forbids for `app`: never
guessed from the URL's last segment, because a guess in a history list is a
fact-shaped guess, and one shaped like a model name is worse, because the model
is what a finding's prose came out of. The row says **"server default"** when
the run named none, which is true and is all that is knowable: `findings.json`'s
`model_run` records which model actually answered, and the history summary drops
the result envelope. So the assertion is that this component reaches no
endpoint at all.

**The cloud model appears only under `compare_models`.** A `cloud_model` named
without it is refused before the audit starts -- `audit_request.REQUIRES` pairs
them -- so a row that printed one unconditionally would show a value that never
reached a model, on the one option that decides whether the audited source left
the machine.

That was asserted as the gate's *position* until it was mutation-tested. A gate
guarding some other element, with the cloud line rendered unconditionally below
it, satisfies "the gate is present" and "the gate comes first" and both labels
-- so the file passed on a page showing a hosted model for a run that sent
nothing to a third party, which is the exact claim the paragraph above makes. It
is the gated *expression* that is read now: the source from `&& (` to the `)}`
that closes it, with the name required to be inside it.

**What a run's flags look like is `test_jsx_run_flags.py`** -- both arms of one
ternary, split out because asserting each properly costs a constant, a regex and
a plant, and the two together took this file past the ~200-line rule.

No test in this suite renders React -- a recorded defect -- so what is read is
the source as text: the conditional is shown to be *written*, not shown to
work. A `&&` with the operands swapped would pass here.

Reads one component and `web/audit_request.py`. No fastapi, no node, no build.
"""

import re

from audit_request import REQUIRES

from .jsx_sweep import FRONTEND_SRC, strip_comments

COMPONENT = FRONTEND_SRC / "components" / "RunOptions.jsx"

# What the row says when the run named no model of its own. One spelling, used
# for both arms.
NO_MODEL_NAMED = '"server default"'

# The two model lines, as the source has to write them for the fallback to
# happen at all: a bare `{options.model}` renders an empty string as nothing.
THE_LOCAL_MODEL = f'{{options.model || {NO_MODEL_NAMED}}}'
THE_CLOUD_MODEL = f'{{options.cloud_model || {NO_MODEL_NAMED}}}'

# The gate the cloud arm sits behind, and the option pair the server enforces.
THE_CLOUD_GATE = "options.compare_models &&"
THE_CLOUD_OPTION = "cloud_model"

# The whole gated expression: `{options.compare_models && (` up to the `)}` that
# closes it. Read as one span so the cloud name can be required to be *inside*
# it -- a gate and a name that merely appear in that order say nothing about
# whether the second is behind the first.
#
# **Its premise, stated rather than assumed**: the first `)}` after the gate is
# the gate's own, which holds because nothing inside the block writes one. A
# `{f(x)}` added in there would end the span early and put a later
# `options.cloud_model` outside it -- a false pass. Nothing in JSX forbids that,
# so it is a premise about this block and not a property of the language.
THE_GATE_EXPRESSION = re.compile(r"\{options\.compare_models && \(.*?\)\}", re.DOTALL)

# The defect it exists to refuse: the gate guarding something else, and the
# cloud name rendered below it whatever the run asked for.
A_GATE_GUARDING_SOMETHING_ELSE = (
    '{options.compare_models && (<span className="tag">compared</span>)}\n'
    '      <span className="run-options__model">\n'
    '        cloud <span className="mono">{options.cloud_model || "server default"}</span>\n'
    "      </span>")

# Every way this component could reach the model endpoint. `fetchModelStatus` is
# the only caller the page has; the rest are what a second one would be written
# with, so the guard is not a ban on one identifier.
NO_LIVE_MODEL_LOOKUP = ("fetchModelStatus", "configured_model", "useEffect",
                        "fetch(", "../api.js")

# Both labels, so "shows both model names" is not satisfied by showing one twice.
THE_LABELS = ("local", "cloud")

# A floor, so a file this test failed to read cannot satisfy the absences above.
MINIMUM_ELEMENTS = 5


def component() -> str:
    """The component's own source, comments stripped: its comments name the endpoint in prose."""
    return strip_comments(COMPONENT.read_text(encoding="utf-8"))


def live_lookups() -> list[str]:
    """Every way of asking the server about models that this component mentions."""
    return [written for written in NO_LIVE_MODEL_LOOKUP if written in component()]


def gated_by_the_compare_flag(text: str) -> str:
    """Everything the compare flag guards, or say the gate is not there at all."""
    found = THE_GATE_EXPRESSION.search(text)
    assert found, f"nothing is rendered behind `{THE_CLOUD_GATE}`"
    return found.group(0)


# --- the local model is the run's own, or is said to be unknown ----------------

def test_the_local_model_falls_back_to_a_named_default() -> None:
    """A bare accessor renders "" as nothing, which reads as a row with a field missing."""
    assert THE_LOCAL_MODEL in component()


def test_the_component_asks_the_server_nothing() -> None:
    """The whole point: today's `configured_model` is not a past run's fact."""
    assert live_lookups() == []


def test_a_live_lookup_added_here_would_be_reported_by_name() -> None:
    """Planted: the absence above is an empty list either way."""
    assert [written for written in NO_LIVE_MODEL_LOOKUP
            if written in "const status = await fetchModelStatus();"] == ["fetchModelStatus"]


# --- and the cloud model appears only when one was consulted -------------------

def test_the_cloud_model_is_rendered_behind_the_compare_flag() -> None:
    """A cloud name without the flag is refused before the audit starts, so it ran nothing."""
    assert THE_CLOUD_GATE in component()


def test_the_cloud_name_is_rendered_inside_that_gate() -> None:
    """Not merely after it: a gate over some other element leaves the name unconditional."""
    assert THE_CLOUD_MODEL in gated_by_the_compare_flag(component())


def test_a_gate_over_some_other_element_is_not_accepted() -> None:
    """Planted: the position check this replaced passed on exactly this page."""
    assert THE_CLOUD_MODEL not in gated_by_the_compare_flag(A_GATE_GUARDING_SOMETHING_ELSE)


def test_the_flag_it_is_gated_on_is_the_one_the_server_pairs_it_with() -> None:
    """`audit_request.REQUIRES` is the rule; the page may not gate on a different option."""
    assert THE_CLOUD_GATE == f"options.{REQUIRES[THE_CLOUD_OPTION]} &&"


def test_the_cloud_model_falls_back_the_same_way_the_local_one_does() -> None:
    """One spelling for both arms: a comparison that showed "" for one is a row half read."""
    assert THE_CLOUD_MODEL in component()


def test_both_model_lines_are_labelled() -> None:
    """Two names in one cell are two facts, and an unlabelled pair is neither."""
    for label in THE_LABELS:
        assert f"{label} <span" in component(), label


def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component satisfies every absence check above."""
    assert len(re.findall(r"<[A-Za-z]", component())) >= MINIMUM_ELEMENTS
