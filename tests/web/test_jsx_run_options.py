"""What a past run asked for is read off that run, never off what the server is set to now.

`RunOptions.jsx` renders one history row's flags, and exports the two helpers
that turn a row into the model names beside it. Which *fields* the flags come
from is `test_jsx_stored_option_fields.py`; what the flags look like is
`test_jsx_run_flags.py`. This file is the model half: three decisions, each of
which is wrong in a way that looks right.

**A model name may not be resolved against `GET /api/model`.** That endpoint
answers `configured_model` -- what `AUDITOR_MODEL` resolves to **now** -- and a
history row filling its blank from it would print today's setting as a past
run's fact. It is the same mistake `docs/SCHEMAS.md` forbids for `app`: never
guessed from the URL's last segment, because a guess in a history list is a
fact-shaped guess, and one shaped like a model name is worse, because the model
is what a finding's prose came out of. So the assertion is that this component
reaches no endpoint at all.

**And it may not fall back to `options.model` either, which is the sharper
half.** `options.model` is what the run *asked for*; `findings.json`'s
`model_run` records what actually **answered**, and the server serves that
beside the record as `local_model_identifier`. Printing the requested name on a
run whose model turned out to be unreachable is a fact-shaped guess wearing a
real field's clothes -- worse than the endpoint, because it would look right on
every run where nothing went wrong. The helpers are required to read the served
fields and required *not* to name the asked-for one.

**Three absences, and they are not interchangeable.** A run where no model was
consulted says `no model`; one where the server could not be reached says
`unreachable`; a run with no second arm says `N/A`. This column said "server
default" for all of them until 2026-09-18, which read as "a model answered, we
just did not pick it" -- a gap rendered as a result, the one thing this page may
not do. `docs/TODO.md` records collapsing "turned off" into "unreachable" as a
defect elsewhere in the project, so the three are pinned as three here.

**The cloud arm is no longer gated on `compare_models`.** It was, and the gate
was asserted as an expression rather than a position after a mutation test. It
went when `N/A` arrived: a row with no second arm now *says* so in the cell,
which is a stronger statement than rendering nothing, and a gate would put that
cell back to being blank for the same reason it was blank before. What replaces
the gate as the real guarantee is the absence vocabulary above.

No test in this suite renders React -- a recorded defect -- so what is read is
the source as text: the fallbacks are shown to be *written*, not shown to work.

Reads one component. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

COMPONENT = FRONTEND_SRC / "components" / "RunOptions.jsx"

# The served fields each arm's helper has to read: what answered, and why
# nothing did. Both halves, because an identifier alone cannot tell the three
# absences apart and the status alone never names a model.
THE_SERVED_FIELDS = ("run.local_model_identifier", "run.local_model_status",
                     "run.cloud_model_identifier", "run.cloud_model_status")

# What the helpers may never read: the option the run was *started* with. Named
# as the accessor rather than the bare word, since `options` appears in this
# file legitimately for the flags.
THE_ASKED_FOR_MODEL = ("options.model", "options.cloud_model")

# The three absences, as the source has to spell them for the column to keep
# them apart. `N/A` arrives through `format.js`, so the import is the assertion
# for that one rather than a literal.
THE_ABSENCES = ('"no model"', '"unreachable"')
THE_SHARED_ABSENT = 'import { ABSENT } from "../format.js"'

# The two statuses the absences are keyed on, from `model_run.status` in
# `src/artifacts/findings_document.py`. `used` is deliberately absent: a used
# run always carries an identifier to show instead.
THE_KEYED_STATUSES = ('"disabled"', '"unavailable"')

# The words the column used to say for all three, which is the defect this
# vocabulary replaced.
THE_COLLAPSED_ABSENCE = "server default"

# Every way this component could reach the model endpoint. `fetchModelStatus` is
# the only caller the page has; the rest are what a second one would be written
# with, so the guard is not a ban on one identifier.
NO_LIVE_MODEL_LOOKUP = ("fetchModelStatus", "configured_model", "useEffect",
                        "fetch(", "../api.js")

# The three helpers the history row imports from here. Exported rather than
# rendered, because the names moved to columns of their own on 2026-09-18.
THE_EXPORTS = ("export function localModel", "export function cloudModel",
               "export function isModelName")

# A floor, so a file this test failed to read cannot satisfy the absences above.
MINIMUM_ELEMENTS = 3


def component() -> str:
    """The component's own source, comments stripped: its comments name the endpoint in prose."""
    return strip_comments(COMPONENT.read_text(encoding="utf-8"))


def live_lookups() -> list[str]:
    """Every way of asking the server about models that this component mentions."""
    return [written for written in NO_LIVE_MODEL_LOOKUP if written in component()]


def asked_for_accessors() -> list[str]:
    """Every read of what the run requested, which is not what answered."""
    return [written for written in THE_ASKED_FOR_MODEL if written in component()]


# --- the names come off the run, and from nowhere else -------------------------

def test_each_arm_reads_what_answered_rather_than_what_was_asked_for() -> None:
    """`model_run` is the record of fact; `options.model` is a request that may have failed."""
    for field in THE_SERVED_FIELDS:
        assert field in component(), field


def test_no_helper_falls_back_to_the_model_the_run_requested() -> None:
    """The fact-shaped guess: a requested name printed on a run nothing answered for."""
    assert asked_for_accessors() == []


def test_a_fallback_added_here_would_be_reported_by_name() -> None:
    """Planted: the absence above is an empty list either way."""
    assert [written for written in THE_ASKED_FOR_MODEL
            if written in "return run.local_model_identifier || options.model;"] \
        == ["options.model"]


def test_the_component_asks_the_server_nothing() -> None:
    """The whole point: today's `configured_model` is not a past run's fact."""
    assert live_lookups() == []


def test_a_live_lookup_added_here_would_be_reported_by_name() -> None:
    """Planted: the absence above is an empty list either way."""
    assert [written for written in NO_LIVE_MODEL_LOOKUP
            if written in "const status = await fetchModelStatus();"] == ["fetchModelStatus"]


# --- and the three absences stay three -----------------------------------------

def test_the_two_spoken_absences_are_written_out() -> None:
    """"Turned off" and "could not be reached" are different facts about a run."""
    for said in THE_ABSENCES:
        assert said in component(), said


def test_each_spoken_absence_is_keyed_on_its_own_status() -> None:
    """A single status driving both words is the collapse `docs/TODO.md` records elsewhere."""
    for status in THE_KEYED_STATUSES:
        assert status in component(), status


def test_the_third_absence_is_the_one_the_rest_of_the_page_uses() -> None:
    """`N/A` is shared, so a run with no second arm reads like every other empty cell."""
    assert THE_SHARED_ABSENT in component()


def test_the_collapsed_wording_it_replaced_is_gone() -> None:
    """"Server default" said a model answered on runs where none was consulted."""
    assert THE_COLLAPSED_ABSENCE not in component()


def test_the_absences_are_told_apart_from_a_name_rather_than_guessed() -> None:
    """The cell dresses a name as data and a gap as this page's own words."""
    assert "export function isModelName" in component()


# --- and the helpers the row imports are the ones this file reads ---------------

def test_every_helper_the_history_row_imports_is_exported_here() -> None:
    """The names left this component's markup; the join to the row is the export list."""
    for exported in THE_EXPORTS:
        assert exported in component(), exported


def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component satisfies every absence check above."""
    assert len(re.findall(r"<[A-Za-z]", component())) >= MINIMUM_ELEMENTS
