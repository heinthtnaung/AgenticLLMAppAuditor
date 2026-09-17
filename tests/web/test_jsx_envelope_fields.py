"""Every field the page reads off the audit's result envelope is a field it carries.

`test_jsx_record_fields.py` sweeps five prefixes -- `finding.`, `surface.`,
`probe.`, `run.` and `record.` -- and the envelope was not among them. That is
the gap this file closes, and it had already cost something: `ComparisonCard.jsx`
labelled the local arm with a hardcoded `"agentic_auditor"`, inventing in
JavaScript the exact word `run_jobs._comparison` refuses to invent in Python, and
nothing joined the card to the envelope well enough to notice. The arm carries
`compared_with` now and the page spells neither name; the last section holds
that.

**Three prefixes, and they are not one shape.** `result` is the whole envelope.
`comparison` is the hosted arm. `envelope` is the name `ComparisonCard`'s `Arm`
binds, and it is rendered **once per arm** -- with the whole envelope on the
left and the comparison on the right -- so what it may read is what *both*
answer. That is asserted as the intersection rather than as either side, because
a field only the enclosing envelope has would render as nothing on the hosted
arm: silent, and wrong on exactly half the card.

**The allowed names come from the producer, not from a transcript.** A run is
driven through `run_jobs.Registry` with the audit replaced, and the keys of the
envelope it really stored are what the JSX may read. `docs/SCHEMAS.md` lists
them too; a second list here would be a third copy to keep in step.

What this cannot see is what `jsx_sweep.py` records: a field read through a
variable or after destructuring, one read in a `.js` module, and one written
inside a comment, which is ignored on purpose.

No fastapi: `run_jobs.py`, `run_record.py` and `history_store.py` are all free of
it, so this runs on a clean checkout with no web extra installed. The audit is
replaced throughout -- nothing here clones, calls a model or opens a socket.
"""

from pathlib import Path

from audit_request import AuditRequest
from evaluation.document import AGENTIC_AUDITOR, CLOUD_AUDITOR
from run_jobs import Registry

from .audit_stub import AUDITOR, URL, open_a_store, stub_the_audit, wait_for_the_worker
from .jsx_sweep import FRONTEND_SRC, accessors, strip_comments, unknown

# The three names the components bind. `result` is the envelope as the run
# record carries it, `comparison` the hosted arm inside it, and `envelope` the
# parameter one component renders each arm through.
RESULT = "result"
COMPARISON = "comparison"
ARM = "envelope"

# Floors under each sweep: one that matched nothing would pass having read
# nothing. Measured today at eleven, three and three; these sit under that, so
# an ordinary edit need not move them.
MINIMUM_RESULT_ACCESSORS = 6
MINIMUM_COMPARISON_ACCESSORS = 2
MINIMUM_ARM_ACCESSORS = 2

# The two system names `evaluation.document` owns. Neither may appear in the
# page: the envelope carries both, and a page that spelled one would be a second
# copy of a vocabulary across a language boundary with nothing binding them.
SYSTEM_NAMES = (AGENTIC_AUDITOR, CLOUD_AUDITOR)

# A field no envelope has ever carried, to show the check reports rather than
# tolerates one.
FIELD_THAT_DOES_NOT_EXIST = "findings_count"


def stored_envelope(monkeypatch, tmp_path: Path) -> dict:
    """The envelope a two-arm run really stored, read back from its own run record."""
    stub_the_audit(monkeypatch, tmp_path, compares=True)
    registry = Registry(open_a_store(tmp_path))
    accepted = registry.start(AuditRequest(url=URL, compare_models=True), AUDITOR)
    wait_for_the_worker(registry)
    _, envelope = registry.store.get(accepted.run_id)
    assert envelope is not None, "the run finished without storing an envelope"
    return envelope


def arm_fields(envelope: dict) -> set[str]:
    """What both arms answer, which is what the component rendering either may read."""
    return set(envelope) & set(envelope[COMPARISON])


def page_text() -> str:
    """The whole committed page as one string, with its comments stripped."""
    return "\n".join(strip_comments(source.read_text(encoding="utf-8"))
                     for source in sorted(FRONTEND_SRC.rglob("*.jsx")))


# --- what the page reads exists ---------------------------------------------------

def test_every_envelope_field_the_page_reads_exists(monkeypatch, tmp_path) -> None:
    """`result.x` across four components, against the keys a run really stored."""
    allowed = set(stored_envelope(monkeypatch, tmp_path))
    assert unknown(RESULT, allowed, accessors(RESULT)) == []


def test_every_comparison_field_the_page_reads_exists(monkeypatch, tmp_path) -> None:
    """`comparison.x`, which is where both system names are read rather than spelled."""
    allowed = set(stored_envelope(monkeypatch, tmp_path)[COMPARISON])
    assert unknown(COMPARISON, allowed, accessors(COMPARISON)) == []


def test_every_field_one_arm_is_rendered_through_exists_on_both_arms(monkeypatch,
                                                                     tmp_path) -> None:
    """The intersection, because the component is rendered once per arm.

    A key only the enclosing envelope carries would render as nothing on the
    hosted side -- wrong on half the card, and silent about it.
    """
    allowed = arm_fields(stored_envelope(monkeypatch, tmp_path))
    assert unknown(ARM, allowed, accessors(ARM)) == []


# --- the sweep really swept ---------------------------------------------------------

def test_the_sweep_read_the_accessors_the_components_are_written_with() -> None:
    """Guard: three empty lists would satisfy every check above having read nothing."""
    assert len(accessors(RESULT)) >= MINIMUM_RESULT_ACCESSORS
    assert len(accessors(COMPARISON)) >= MINIMUM_COMPARISON_ACCESSORS
    assert len(accessors(ARM)) >= MINIMUM_ARM_ACCESSORS


def test_an_accessor_no_envelope_answers_is_reported_and_named(monkeypatch,
                                                               tmp_path) -> None:
    """Guard on the check itself: a bad field is named with its file, not passed over."""
    allowed = set(stored_envelope(monkeypatch, tmp_path))
    planted = [("StatRail.jsx", FIELD_THAT_DOES_NOT_EXIST)]
    assert unknown(RESULT, allowed, planted) == [
        f"StatRail.jsx: {RESULT}.{FIELD_THAT_DOES_NOT_EXIST}"]


def test_the_two_arms_really_differ_in_what_they_carry(monkeypatch, tmp_path) -> None:
    """Non-vacuity for the intersection above: two identical sets would make it the union."""
    envelope = stored_envelope(monkeypatch, tmp_path)
    assert arm_fields(envelope) < set(envelope)


# --- and the page spells neither system name -----------------------------------------

def test_the_page_names_neither_system_itself() -> None:
    """The defect this file was written after: a card that spelled `agentic_auditor`."""
    written = page_text()
    assert [name for name in SYSTEM_NAMES if name in written] == []


def test_both_names_are_things_the_envelope_hands_the_page(monkeypatch, tmp_path) -> None:
    """Non-vacuity: a page that showed no system at all would pass the test above."""
    comparison = stored_envelope(monkeypatch, tmp_path)[COMPARISON]
    assert {comparison["system"], comparison["compared_with"]} == set(SYSTEM_NAMES)
