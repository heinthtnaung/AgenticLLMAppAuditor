"""Every field the page reads off a record is a field that record really carries.

The page renders `findings.json` and `surfaces.json` verbatim -- `docs/SCHEMAS.md`
says the wrapper "re-keys nothing, drops nothing, adds nothing" -- so the JSX is
reading `src/`'s dataclasses directly, across a language boundary with no
compiler and no type across it. JavaScript answers `undefined` for a field that
does not exist and React renders `undefined` as nothing at all, so the mistake
is silent in both directions: nothing throws, and the value is simply missing
from the page. `FindingList.jsx` read `finding.evidence` for weeks. `Finding`
has never had such a field.

**The allowed names are taken from the serialiser, not transcribed.** A record
is built and written through `build_findings_document` and `surfaces_to_json`,
and the keys of what comes out are what the JSX may read. That covers the
dataclass fields and the two names the serialiser adds on its way past --
`finding_id` and `probe_id` on the findings document, `id` on a surface -- with
no second list to keep in step. Three tests below pin those additions against
the dataclasses so the derivation cannot quietly widen.

**The run record is the fourth prefix, and it is read across the same boundary.**
`POST /api/audit` answers with a job rather than an audit now, and the history
table and the run summary read `run.x` and `record.x` off it -- so the same
defect this file exists for reopened on a shape that is not in `src/` at all.
Its allowed names are derived the same way, from `web/run_record.py`:
`DURABLE_FIELDS` (the dataclass) plus `COMPUTED_FIELDS` (added at read time)
plus the two keys `body` adds, `result` and `schema_version`. That derivation is
pinned by a test below, so it cannot quietly widen either.

**Two components joined the run-record sweep with the run overlay**, and they
are floored by name below: `RunOverlay.jsx`, the card an audit advances in, and
`RunStamps.jsx`, the timestamps extracted out of `RunSummary.jsx` so the overlay
and the report show one of them rather than two. The whole-page sweep would pass
having read neither, which is the only thing a per-file floor adds -- the
`unknown` checks above already cover every `record.x` in the page wherever it is
written.

**The coverage block is the fifth shape, and it is not in this file.** The
advisory section reads three more -- the block, one unreached component, one
advisory against it -- and `test_jsx_coverage_fields.py` sweeps those against
the same kind of `src/` builder, over the sweep this file shares with it in
`jsx_sweep.py`.

What this cannot see: a field read through a variable (`finding[key]`), or one
reached after destructuring. The sweep is textual and looks for `finding.x`,
`surface.x`, `probe.x`, `run.x` and `record.x` here, which is how all the
components are written today; a field read in a `.js` module rather than a
`.jsx` one is also outside it. `jsx_sweep.py` records the rest of what its
regex does and does not match.

No fastapi here. It reads the JSX as text, the artifact records from `src/`, and
the run record from `web/run_record.py`, which is free of fastapi on purpose --
so this runs on a clean checkout with no web extra installed.
"""

import dataclasses
import json

from artifacts.finding import Finding, Probe
from artifacts.surface import Surface, surfaces_to_json
from findings_fixtures import build_document, confirmed_probe, probe_finding, static_finding
from run_record import COMPUTED_FIELDS, DURABLE_FIELDS, RunRecord
from surface_fixtures import PYTHON_SURFACES

from .jsx_sweep import accessors, field_names, unknown

# The record names the components bind, spelled as the JSX spells them. The run
# record answers to two: the history table calls one row a `run`, the run page
# calls the record it polled a `record`, and both are the same shape.
FINDING = "finding"
SURFACE = "surface"
PROBE = "probe"
RUN = "run"
RUN_DETAIL = "record"

# What the serialiser adds that the dataclass does not declare. Named here so
# the three tests below can hold the derived sets to exactly this much more.
FINDING_ADDITIONS = frozenset({"finding_id"})
PROBE_ADDITIONS = frozenset({"probe_id"})
SURFACE_ADDITIONS = frozenset({"id"})

# What `run_record.body` adds to the record's own fields on its way to the wire.
BODY_ADDITIONS = frozenset({"result", "schema_version"})

# The one field the probe rationale joins on, and it is the same field on both
# records: `findings_document.py` writes `probe_id` on the probe and on the
# finding that cites it. Named so the sweep is shown to be reading the fixed
# code -- the JSX used to rebuild `probe_name:subject_id`, which is a second
# spelling of a format `src/` owns, in a language nothing binds to it.
PROBE_JOIN_FIELD = "probe_id"

# Floors under each sweep: one that matched nothing would otherwise pass having
# checked nothing. The finding and surface floors sit under what the components
# read today, so an ordinary edit need not move them. The probe floor is exactly
# what is read -- a probe record is touched for `outcome`, `probe_id` and
# `detail`, and nothing else -- because the join stopped rebuilding `Probe.id`.
MINIMUM_FINDING_ACCESSORS = 8
MINIMUM_SURFACE_ACCESSORS = 4
MINIMUM_PROBE_ACCESSORS = 3

# The two run-record floors. Measured today: twelve reads off a row, all in the
# history table, and twenty-four off a record across three components -- the run
# summary, the page that polls it and `App.jsx`. Both floors sit well under
# that, so an ordinary edit need not move them; they are here to catch a sweep
# that read nothing, not to count the page.
MINIMUM_RUN_ACCESSORS = 8
MINIMUM_RUN_DETAIL_ACCESSORS = 10

# The two components the run overlay is built from, and a floor under each: the
# page-wide sweep above would be satisfied by a run overlay that read nothing at
# all. Measured today at five accessors each, so these sit just under.
OVERLAY_COMPONENTS = {"RunOverlay.jsx": 4, "RunStamps.jsx": 4}

# A field no record has ever carried, to show the check reports rather than
# tolerates one. This is the accessor that shipped for weeks.
FIELD_THAT_DOES_NOT_EXIST = "evidence"


def served_finding_fields() -> set[str]:
    """Every key a finding carries in findings.json, read off the serialiser's output."""
    return set(build_document([static_finding()])["findings"][0])


def served_probe_fields() -> set[str]:
    """Every key a probe record carries in findings.json, read off the same output."""
    probe = confirmed_probe()
    return set(build_document([probe_finding(probe)], [probe])["probes"][0])


def served_surface_fields() -> set[str]:
    """Every key a surface carries in surfaces.json, read off `surfaces_to_json`."""
    written = json.loads(surfaces_to_json([PYTHON_SURFACES[0]], []))
    return set(written["surfaces"][0])


def served_run_fields() -> set[str]:
    """Every key a run body carries, derived from the record rather than transcribed."""
    return {*DURABLE_FIELDS, *COMPUTED_FIELDS, *BODY_ADDITIONS}


def declared(record: type) -> set[str]:
    """The field names a dataclass declares, before any serialiser adds to them."""
    return {field.name for field in dataclasses.fields(record)}


# --- what the page reads exists -----------------------------------------------

def test_every_finding_field_the_page_reads_exists() -> None:
    """`finding.evidence` rendered as nothing for weeks; this is what would have said so."""
    assert unknown(FINDING, served_finding_fields(), accessors(FINDING)) == []


def test_every_surface_field_the_page_reads_exists() -> None:
    """The surfaces table joins to `Surface` the same way, across the same silent boundary."""
    assert unknown(SURFACE, served_surface_fields(), accessors(SURFACE)) == []


def test_every_probe_field_the_page_reads_exists() -> None:
    """The probe rationale is keyed on one of these, so a wrong name empties the map."""
    assert unknown(PROBE, served_probe_fields(), accessors(PROBE)) == []


def test_every_run_field_the_history_table_reads_exists() -> None:
    """`run.x` on a history row: the same silent boundary, on a shape `src/` does not own."""
    assert unknown(RUN, served_run_fields(), accessors(RUN)) == []


def test_every_run_field_the_run_page_reads_exists() -> None:
    """`record.x` on a polled run, which is where `result` and `stages` are read."""
    assert unknown(RUN_DETAIL, served_run_fields(), accessors(RUN_DETAIL)) == []


# --- the sweep really swept ---------------------------------------------------

def test_the_sweep_read_the_accessors_the_components_are_written_with() -> None:
    """Guard: three empty lists would satisfy every artifact check above having read nothing."""
    assert len(accessors(FINDING)) >= MINIMUM_FINDING_ACCESSORS
    assert len(accessors(SURFACE)) >= MINIMUM_SURFACE_ACCESSORS
    assert len(accessors(PROBE)) >= MINIMUM_PROBE_ACCESSORS


def test_the_sweep_read_the_run_accessors_too() -> None:
    """The same guard for the fourth prefix, which is read under two names."""
    assert len(accessors(RUN)) >= MINIMUM_RUN_ACCESSORS
    assert len(accessors(RUN_DETAIL)) >= MINIMUM_RUN_DETAIL_ACCESSORS


def test_the_run_sweep_read_the_two_components_the_overlay_is_built_from() -> None:
    """Named, because the page-wide floors above pass whatever these two files contain."""
    read = [where for where, _ in accessors(RUN_DETAIL)]
    short = {where: read.count(where) for where, floor in OVERLAY_COMPONENTS.items()
             if read.count(where) < floor}
    assert short == {}, f"the run-record sweep read too little of: {short}"


def test_both_sides_of_the_probe_join_read_the_same_served_field() -> None:
    """`probe.probe_id` and `finding.probe_id`: the format itself stays in `src/`."""
    assert PROBE_JOIN_FIELD in field_names(PROBE)
    assert PROBE_JOIN_FIELD in field_names(FINDING)


def test_an_accessor_no_record_answers_is_reported_and_named() -> None:
    """Guard on the check itself: a bad field is named with its file, not passed over."""
    planted = [("FindingList.jsx", FIELD_THAT_DOES_NOT_EXIST)]
    assert unknown(FINDING, served_finding_fields(), planted) == [
        f"FindingList.jsx: {FINDING}.{FIELD_THAT_DOES_NOT_EXIST}"]


# --- the served fields are the declared ones plus the serialiser's own --------

def test_a_served_finding_is_its_dataclass_plus_the_id_the_document_adds() -> None:
    """Pins the derivation: the allowed set may not widen without this test moving."""
    assert served_finding_fields() == declared(Finding) | FINDING_ADDITIONS


def test_a_served_probe_is_its_dataclass_plus_the_id_the_document_adds() -> None:
    """`probe_id` is the serialised spelling of `Probe.id`, which is not a field."""
    assert served_probe_fields() == declared(Probe) | PROBE_ADDITIONS


def test_a_served_surface_is_its_dataclass_plus_the_id_the_scan_adds() -> None:
    """`surfaces_to_json` adds `id`; everything else on the row is a declared field."""
    assert served_surface_fields() == declared(Surface) | SURFACE_ADDITIONS


def test_a_served_run_is_its_dataclass_plus_the_computed_and_body_keys() -> None:
    """Pins the fourth derivation: the allowed set may not widen without this test moving."""
    assert served_run_fields() == declared(RunRecord) | set(COMPUTED_FIELDS) | BODY_ADDITIONS
