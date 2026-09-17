"""Three outcomes, three places on the audit page, and each one shown where it can be read.

The audit page renders one of three things about a run, and which surface owns
which outcome is the decision this file holds:

- **While it is going**, the overlay covers the page. The form behind it is
  disabled anyway, and a panel that grew inline put the stages below the fold on
  the very click that started them.
- **When it finished**, nothing is rendered here at all: the page navigates to
  the run's own report, which `test_jsx_audit_redirect.py` owns.
- **When it failed**, the overlay is gone and the reason is a notice in the page
  body, beside the URL still sitting in the form -- which is what the commonest
  failure, a repository that cannot be fetched, actually needs on screen -- with
  a link to the run's page for the stages it reached.

**The record on screen is the 202's own until the first poll replaces it, and
every status flag is gated on there being a run at all.** Two lines, one window:
between the click being accepted and the first `GET` answering there was no
record, so no overlay, no notice and a live Audit button -- a first poll that
failed left a bare form polling for ever, and a second click detached the page
from a run that then completed unseen. `run_record.body` answers the same shape
for the accept as for a poll, so the accept is kept and shown until it is
replaced. The gate is the other half: `setRunId(null)` commits one render before
`useRun` resets, and a flag reading a stale record would build `/runs/null`.

Both are asserted as the expressions they are, because **the conditional sweep
below cannot see either.** `statuses_tested(flag("running"))` reads the status
comparison inside the flag and is satisfied whether or not the flag is gated,
and it says nothing at all about which record was compared -- so the fix for
that window could be deleted with this file green. That is the gap these two
asserts close.

**And the poll error is inside the card, which is not where it started.** "Lost
contact with the server; still asking" is the one message that can arrive
*during* a run, and it was rendered in the page body -- under the scrim, while
`useRun` went on polling behind the cover: invisible exactly when it mattered.
It is handed to `RunOverlay` now, and this file holds both halves, the page not
rendering it and the card receiving it.

`test_jsx_overlay_props.py` holds the boundary beside this one: that what the
page passes the card is what the card takes apart.

**No test in this suite renders React**, a recorded defect this does not close.
Everything here is the page read as text: it can say which conditional a block
is written under and what that block contains, and it cannot say what a browser
paints. Comments are stripped first, so the prose explaining each decision is
not read as code.

No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

PAGE = FRONTEND_SRC / "pages" / "AuditPage.jsx"
OVERLAY = FRONTEND_SRC / "components" / "RunOverlay.jsx"

# The component the page shows while a run is going, and the one it must not
# grow again: a finished run is read on its own page, and two copies would be
# two places to read one run.
THE_OVERLAY = "RunOverlay"
THE_INLINE_REPORT = "RunSummary"

# A conditional render -- `{running && (<RunOverlay ...` -- as its condition and
# the first element it renders.
GATE = re.compile(r"\{(\w+) && \(?\s*<(\w+)")

# A `const flag = ...;` the render is gated on, and how a status comparison
# reads inside one.
FLAG = re.compile(r"const (\w+) = ([^;]+);")
STATUS_TEST = re.compile(r"status\s*(===|!==)\s*([A-Z][A-Z_]*)")

# What the two notices are, as the classes they carry. The wait notice is the
# poll error and belongs in the card; the error notice is the run's own failure
# and belongs in the page.
WAIT_NOTICE = "notice notice--wait"
ERROR_NOTICE = "notice notice--error"

# The record field that carries the reason a run failed, and the two things the
# failure notice has to offer: the reason, and the way to the rest of it.
THE_REASON = "record.error"
THE_WAY_TO_THE_RUN = "runPath("

# The record the page renders, as the expression it is defined by. The accept
# is kept rather than discarded because it answers the same shape a poll does.
THE_RECORD_SHOWN = "polled ?? accepted"

# What every status flag has to open with, and the flags that have to open with
# it. A flag that read the record alone would be true for a run the page has
# stopped polling.
ONLY_WITH_A_RUN = "Boolean(runId) &&"
THE_STATUS_FLAGS = ("running", "failed")

# A floor, so a sweep that read nothing cannot pass as a sweep that found no
# fault. Three conditional renders today.
MINIMUM_GATES = 3


def page() -> str:
    """The audit page's own source, comments stripped: they name every outcome in prose."""
    return strip_comments(PAGE.read_text(encoding="utf-8"))


def gates() -> list[tuple[str, str]]:
    """Every conditional render on the page, as its condition and what it renders."""
    found = GATE.findall(page())
    assert found, f"{PAGE.name} renders nothing conditionally this test can read"
    return found


def conditions_rendering(element: str) -> list[str]:
    """Every condition one element is rendered under, in the order the page writes them."""
    return [condition for condition, rendered in gates() if rendered == element]


def flag(name: str) -> str:
    """The expression one `const` flag is defined as, or say it is not defined at all."""
    defined = dict(FLAG.findall(page()))
    assert name in defined, f"{PAGE.name} defines no `{name}`"
    return defined[name]


def statuses_tested(expression: str) -> list[tuple[str, str]]:
    """Every status comparison in one expression, as its operator and the constant."""
    return STATUS_TEST.findall(expression)


def region_of(condition: str) -> str:
    """The block one condition renders, from its brace to the one that closes it.

    A depth scan rather than a pattern, so re-indenting or wrapping the block
    does not change what this reads.
    """
    text = page()
    start = text.index(f"{{{condition} &&")
    depth = 0
    for offset in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[offset], 0)
        if depth == 0:
            return text[start:offset + 1]
    raise AssertionError(f"the `{condition}` block in {PAGE.name} is never closed")


# --- the window between the accept and the first poll -------------------------

def test_the_record_on_screen_is_the_poll_or_the_accept_it_replaces() -> None:
    """Without the accept there is a window with no record in it, and three things go wrong."""
    assert flag("record") == THE_RECORD_SHOWN


def test_every_status_flag_is_gated_on_there_being_a_run_at_all() -> None:
    """A stale record outliving its `runId` by one render is how `/runs/null` gets built."""
    for name in THE_STATUS_FLAGS:
        assert flag(name).startswith(ONLY_WITH_A_RUN), f"{name} = {flag(name)}"


def test_both_flags_this_file_gates_are_flags_the_page_defines() -> None:
    """Non-vacuity: `flag` raises on a name the page does not define, so the pair is named."""
    assert [name for name in THE_STATUS_FLAGS if not flag(name)] == []


# --- the overlay is for a run that is going, and only that --------------------

def test_the_overlay_is_rendered_under_one_condition_and_it_is_the_running_one() -> None:
    """A run that is over has somewhere better to be: its own page, or a notice."""
    shown_when = conditions_rendering(THE_OVERLAY)
    assert len(shown_when) == 1, shown_when
    assert statuses_tested(flag(shown_when[0])) == [("===", "RUNNING")]


def test_the_page_never_grows_the_inline_report_again() -> None:
    """Decision, asserted: one run is read in one place, which is the run's own page."""
    assert THE_INLINE_REPORT not in page()


# --- a failure is a notice on the page ----------------------------------------

def test_a_failed_run_is_reported_where_the_form_still_shows_what_was_typed() -> None:
    """The other terminal status, and the one nothing navigates away from."""
    assert statuses_tested(flag("failed")) == [("===", "FAILED")]
    assert ERROR_NOTICE in region_of("failed")


def test_the_failure_notice_carries_the_reason_and_the_way_to_the_rest() -> None:
    """A failure stated with neither its reason nor a route onward is a dead end."""
    failed = region_of("failed")
    assert THE_REASON in failed
    assert THE_WAY_TO_THE_RUN in failed


def test_the_overlay_is_not_what_reports_a_failure() -> None:
    """The redesign: a panel a reader may not dismiss, over a run that is over."""
    assert THE_OVERLAY not in region_of("failed")


# --- and the poll error is in the card, not under the scrim -------------------

def test_the_page_hands_the_poll_error_to_the_overlay() -> None:
    """It arrives *during* a run, which is the one moment the page body is covered."""
    assert "error={error}" in region_of("running")


def test_the_page_body_renders_no_notice_for_the_poll_error() -> None:
    """Where it used to be, and where it was invisible while it went on polling."""
    assert [condition for condition, _ in gates() if condition == "error"] == []
    assert WAIT_NOTICE not in page()


def test_the_wait_notice_is_rendered_in_one_component_and_it_is_the_card() -> None:
    """Non-vacuity for the test above: a message no component renders is not moved, it is gone."""
    renders = sorted(source.name for source in FRONTEND_SRC.rglob("*.jsx")
                     if WAIT_NOTICE in strip_comments(source.read_text(encoding="utf-8")))
    assert renders == [OVERLAY.name]


def test_the_gate_sweep_read_the_conditions_the_page_is_written_with() -> None:
    """Non-vacuity: no gate found would leave four checks above reading nothing."""
    assert len(gates()) >= MINIMUM_GATES
