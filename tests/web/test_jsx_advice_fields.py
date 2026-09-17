"""Every field the advice panel reads exists, and a refusal renders as a refusal.

`FindingAdvice.jsx` reads three shapes off `remediation.json` -- an entry, one
of its attributions, one of its snippets -- across the same boundary
`test_jsx_record_fields.py` exists for: no compiler, no type, and `undefined`
rendered as nothing at all. The allowed names come from the real producers in
`src/artifacts/remediation.py`, so they are what a run would really write.

**A refusal is not an absence, and this is the common path.** On a measured run
the statuses were `{rejected: 6, unavailable: 0, written: 3}` -- two thirds of
the advice on that run was refused for a named reason. `remediation.py` makes a
refusal whole rather than partial: `guidance`, `snippets` and `sources` are all
emptied, so a component that only checked for guidance would show a refused
entry as no entry at all, which reads as "the run did not write one". The three
branches the component has -- no entry, a refusal with its reason, and written
advice -- are asserted to be three, and the statuses it spells are checked
against the closed vocabulary the producer owns.

How the panel *finds* the entry in the first place is `test_jsx_advice_join.py`,
which this was split from.

What this cannot see is what `jsx_sweep.py` records: a field read through a
variable or after destructuring, and one read in a `.js` module. It also does
not run the component -- whether the refusal branch is *reached* is a claim
about React, not about these names.

No fastapi and no node: it reads the JSX as text and the records from `src/`.
"""

from artifacts.remediation import ADVICE_STATUSES, REJECTED, UNAVAILABLE, WRITTEN
from findings_fixtures import build_document, static_finding
from remediation_fixtures import (
    CLEAN_GUIDANCE, rejected_entry, remediation_document, snippet, source,
    unavailable_entry, written_entry)

from .jsx_sweep import FRONTEND_SRC, accessors, unknown

# The three names the components bind, spelled as the JSX spells them.
ADVICE = "advice"
SOURCE = "source"
SNIPPET = "snippet"

# Why a refusal happened, as `advice_rules` names one. Any value of
# `ADVICE_REASONS` would do; this is the one a reader of the page sees most.
A_REFUSAL_REASON = "names_app_identifier"
REFUSED_ON = "guidance"

# Floors under each sweep: a sweep that matched nothing would satisfy every
# "every field exists" check having read nothing at all. Measured today at ten
# reads of six names, five of three, and four of three.
MINIMUM_ADVICE_ACCESSORS = 8
MINIMUM_SOURCE_ACCESSORS = 4
MINIMUM_SNIPPET_ACCESSORS = 3

# A field no advice entry has ever carried, to show the check reports rather
# than tolerates one.
FIELD_THAT_DOES_NOT_EXIST = "fix"
THE_FILE_THAT_WOULD_READ_IT = "FindingAdvice.jsx"


def a_joined_pair() -> tuple[dict, dict]:
    """One findings document and the remediation document written about it.

    The advice entry is keyed on the findings document's own id, so what the
    fields are read off is the shape a real pair has rather than two documents
    about nothing in particular.
    """
    findings = build_document([static_finding()])
    joined_on = findings["findings"][0]["finding_id"]
    advice = remediation_document([written_entry(joined_on, CLEAN_GUIDANCE,
                                                 [snippet()], [source()])])
    return findings, advice


def advice_fields() -> set[str]:
    """Every key one advice entry carries, taken from the real producer."""
    _findings, advice = a_joined_pair()
    assert len(advice[ADVICE]) == 1, "the fixture stopped writing exactly one entry"
    return set(advice[ADVICE][0])


def source_fields() -> set[str]:
    """Every key one passage attribution carries."""
    _findings, advice = a_joined_pair()
    return set(advice[ADVICE][0]["sources"][0])


def snippet_fields() -> set[str]:
    """Every key one illustrative snippet carries."""
    _findings, advice = a_joined_pair()
    return set(advice[ADVICE][0]["snippets"][0])


def statuses_the_page_spells() -> set[str]:
    """The advice statuses named as literals anywhere in the page's own source."""
    text = "".join(path.read_text(encoding="utf-8") for path in _components())
    return {status for status in ADVICE_STATUSES if f'"{status}"' in text}


def _components() -> list:
    """Every JSX file the page ships, in a stable order."""
    return sorted(FRONTEND_SRC.rglob("*.jsx"))



# --- every field the panel reads exists ---------------------------------------

def test_every_advice_field_the_page_reads_exists() -> None:
    """`advice.status` decides which of three branches renders; a wrong name renders none."""
    assert unknown(ADVICE, advice_fields(), accessors(ADVICE)) == []


def test_every_source_field_the_page_reads_exists() -> None:
    """A passage is shown as a link with a heading, so a wrong name is a link to nothing."""
    assert unknown(SOURCE, source_fields(), accessors(SOURCE)) == []


def test_every_snippet_field_the_page_reads_exists() -> None:
    """`snippet.code` is the illustration itself: undefined renders as an empty block."""
    assert unknown(SNIPPET, snippet_fields(), accessors(SNIPPET)) == []


def test_the_sweeps_read_the_accessors_the_components_are_written_with() -> None:
    """Guard: three empty lists would satisfy all three checks above having read nothing."""
    assert len(accessors(ADVICE)) >= MINIMUM_ADVICE_ACCESSORS
    assert len(accessors(SOURCE)) >= MINIMUM_SOURCE_ACCESSORS
    assert len(accessors(SNIPPET)) >= MINIMUM_SNIPPET_ACCESSORS


def test_a_field_no_entry_carries_is_reported_with_its_file() -> None:
    """Guard on the check itself: a bad field is named with its file, not passed over."""
    planted = [(THE_FILE_THAT_WOULD_READ_IT, FIELD_THAT_DOES_NOT_EXIST)]
    assert unknown(ADVICE, advice_fields(), planted) == [
        f"{THE_FILE_THAT_WOULD_READ_IT}: {ADVICE}.{FIELD_THAT_DOES_NOT_EXIST}"]


# --- a refusal is a refusal, not an absence -----------------------------------

def test_the_page_spells_every_status_the_vocabulary_has() -> None:
    """A status the page does not know falls through to whatever its default branch says."""
    assert statuses_the_page_spells() == set(ADVICE_STATUSES)


def test_a_refused_entry_carries_its_reason_and_no_guidance() -> None:
    """Which is why a check on `guidance` alone would render two thirds of a real run as blank."""
    entry = rejected_entry("F-01", A_REFUSAL_REASON, REFUSED_ON)
    assert entry["status"] == REJECTED
    assert entry["guidance"] is None
    assert entry["reason"] == A_REFUSAL_REASON
    assert entry["rejected_on"] == REFUSED_ON


def test_an_unavailable_entry_carries_a_reason_too() -> None:
    """The third status: no model was reachable, which is not the model refusing."""
    entry = unavailable_entry("F-01")
    assert entry["status"] == UNAVAILABLE
    assert entry["guidance"] is None
    assert entry["reason"] is not None


def test_written_advice_is_the_only_status_carrying_text() -> None:
    """The producer's own rule, restated here because the page's branching depends on it."""
    entry = written_entry("F-01")
    assert entry["status"] == WRITTEN
    assert entry["guidance"]


def test_the_document_counts_all_three_statuses_whether_or_not_they_occurred() -> None:
    """`status_counts` is what a reader sees first, and a zero must be a zero and not a gap."""
    advice = remediation_document([written_entry("F-01"),
                                   rejected_entry("F-02", A_REFUSAL_REASON)])
    assert set(advice["status_counts"]) == set(ADVICE_STATUSES)
    assert advice["status_counts"][UNAVAILABLE] == 0


def test_the_panel_says_something_different_when_there_is_no_entry_at_all() -> None:
    """Three branches, not two: absent, refused, and written are three different facts."""
    text = (_component_named(THE_FILE_THAT_WOULD_READ_IT)).read_text(encoding="utf-8")
    assert "holds no entry for this finding" in text
    assert "not the same as advice that was refused" in text


def _component_named(name: str):
    """One JSX file by name, insisting the page still ships it."""
    found = [path for path in _components() if path.name == name]
    assert len(found) == 1, f"expected exactly one {name}, found {len(found)}"
    return found[0]
