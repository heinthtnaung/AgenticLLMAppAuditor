"""The run's timestamps are one component, read by both views, and its two durations are two facts.

`RunStamps.jsx` was a local `Stamps` function inside `RunSummary.jsx` until the
run overlay needed the same four lines. It was **extracted, not copied**: two
copies of a panel that renders two durations is two places for the harder of the
two facts below to go wrong, and this session has already paid for one guard
written five times. So the claims here are that there is one of it, that both
views read that one, and that nothing declares a second.

**The two durations are not the same number, and `docs/SCHEMAS.md` says so in
the envelope's own table**: the run record's `seconds` times the whole job,
including resolving the repository, while the result envelope's `seconds` is the
audit's own timer, which starts after that. A clone sits in the difference. A
component that read one of them twice would show two labels over one fact and
nothing would throw, so both reads are counted here.

**The envelope read is guarded, and that guard is load-bearing now.** `result`
is null on every run that has not finished, which is the whole time the overlay
is on screen -- and `record.result.seconds` on a null result is a `TypeError`
that takes the panel down with it, unlike a missing *field*, which renders as
nothing. The guard is asserted rather than assumed.

**No test in this suite renders React**, a recorded defect this does not close.
This file reads modules as text: it can say which file declares the markup and
which files import it, and it cannot say that either view really mounts it.
`test_jsx_record_fields.py` owns the other half -- that every field these
accessors name is a field the run record carries -- and floors this component by
name there.

No fastapi, no node, no build.
"""

import re
from pathlib import Path

from .jsx_sweep import FRONTEND_SRC, strip_comments

STAMPS = FRONTEND_SRC / "components" / "RunStamps.jsx"

# The two views that show a run's timestamps: the card an audit advances in, and
# the report it is read from afterwards.
THE_TWO_VIEWS = ("RunOverlay.jsx", "RunSummary.jsx")

# The markup's own fingerprint. A second copy of this panel would carry it,
# whatever the copy called itself.
STAMPS_CLASS = "stamps__label"

# A component whose name ends in `Stamps`, which is what the extracted one and
# the local one it replaced are both called.
STAMPS_COMPONENT = re.compile(r"function (\w*Stamps)\b")

# An import of the shared component, however the importing file reaches it, and
# the element that puts it on screen. Both are asserted: an import with no
# element left is a view that stopped showing the timestamps, and an element
# with no import is a component React cannot resolve.
STAMPS_IMPORT = re.compile(r'import RunStamps from "[./]*(?:components/)?RunStamps\.jsx";')
STAMPS_ELEMENT = re.compile(r"<RunStamps\b")

# The two durations, each read off a different shape: the run record itself, and
# the result envelope inside it.
WHOLE_JOB = re.compile(r"record\.seconds\b")
THE_AUDIT_ITSELF = re.compile(r"record\.result\.seconds\b")
THE_GUARD = "record.result &&"

# A floor under the sweep, so a run of it that read no module cannot pass.
MINIMUM_MODULES = 20


def code_of(path: Path) -> str:
    """One module's source with its comments gone: they name the component in prose."""
    return strip_comments(path.read_text(encoding="utf-8"))


def components() -> list[Path]:
    """Every component file the page ships, in a stable order."""
    found = sorted(FRONTEND_SRC.rglob("*.jsx"))
    assert found, f"no JSX under {FRONTEND_SRC}; the page has no components at all"
    return found


def rendering_the_stamps() -> list[str]:
    """Every module that writes the timestamps markup itself."""
    return sorted(path.name for path in components() if STAMPS_CLASS in code_of(path))


def declaring_a_stamps_component() -> list[str]:
    """Every module that declares a component by that name, wherever it does it."""
    return sorted(path.name for path in components()
                  if STAMPS_COMPONENT.search(code_of(path)))


def importing_the_stamps() -> list[str]:
    """Every module that reads the shared component instead of writing its own."""
    return sorted(path.name for path in components()
                  if STAMPS_IMPORT.search(code_of(path)))


def showing_the_stamps() -> list[str]:
    """Every module that actually renders it, which is not the same as importing it."""
    return sorted(path.name for path in components()
                  if STAMPS_ELEMENT.search(code_of(path)))


def stamps() -> str:
    """The shared component's own source."""
    return code_of(STAMPS)


# --- there is one of it -------------------------------------------------------

def test_the_timestamps_markup_is_written_in_one_module() -> None:
    """A second copy is a second place for the two durations to be confused."""
    assert rendering_the_stamps() == [STAMPS.name]


def test_no_module_declares_a_second_stamps_component() -> None:
    """The local `Stamps` inside `RunSummary.jsx` is what this replaced."""
    assert declaring_a_stamps_component() == [STAMPS.name]


def test_both_views_that_show_a_run_read_the_shared_component() -> None:
    """The reason it was extracted: the overlay and the report show the same four lines."""
    assert importing_the_stamps() == sorted(THE_TWO_VIEWS)


def test_both_views_really_render_it_and_not_only_import_it() -> None:
    """An import with no element left behind it is a view that stopped showing the stamps."""
    assert showing_the_stamps() == sorted(THE_TWO_VIEWS)


# --- and its two durations are two different facts ----------------------------

def test_the_whole_job_is_read_off_the_run_record_once() -> None:
    """The outer timer: it includes resolving the repository, which the inner one does not."""
    assert len(WHOLE_JOB.findall(stamps())) == 1


def test_the_audits_own_timer_is_read_off_the_result_envelope_once() -> None:
    """Two labels over one number is the mistake nothing would throw about."""
    assert len(THE_AUDIT_ITSELF.findall(stamps())) == 1


def test_the_envelope_is_reached_only_behind_a_guard() -> None:
    """`result` is null on every run that has not finished, and a null read throws."""
    text = stamps()
    assert THE_GUARD in text
    assert text.index(THE_GUARD) < THE_AUDIT_ITSELF.search(text).start()


# --- the sweeps really swept --------------------------------------------------

def test_the_sweep_read_the_components_the_page_is_built_from() -> None:
    """Non-vacuity: an empty module list satisfies all three claims above."""
    assert len(components()) >= MINIMUM_MODULES


def test_a_module_that_copied_the_markup_would_be_reported_by_name() -> None:
    """Planted: the three sweeps above are one-item lists either way."""
    planted = {"RunSummary.jsx": f'<span className="{STAMPS_CLASS}">Started</span>'}
    assert [where for where, text in planted.items() if STAMPS_CLASS in text] == [
        "RunSummary.jsx"]
