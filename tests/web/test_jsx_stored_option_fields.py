"""Every option the history row shows is one a stored run really carries.

The history table shows what each run asked for, read off `run.options` -- which
`docs/SCHEMAS.md` calls "exactly `AuditRequest`'s fields, so a re-run is exact".
That is a fourth reader of the request's field names, and the first one that
reads them **back** rather than posting them: `test_option_fields.py` holds the
three *declarations* against each other, and this holds what the page reads out
of the stored copy.

**It is a blind spot the existing sweep cannot cover, not a second copy of it.**
`test_jsx_record_fields.py` sweeps `run.<field>` and stops there: `run.options`
is a field the record carries, so `run.options.cloudModel` passes that file and
renders as **nothing at all** -- no throw, no warning, an empty place where the
model a person chose should be. One level deeper is exactly where a camel-cased
guess survives, because JavaScript is where the reader is and snake_case is
where the record is.

**Two spellings are swept, and only one of them is in use today.** The three
boolean flags are written as string keys in a `FLAGS` table and read as
`options[key]`, which no accessor sweep can see: a table whose keys drifted
would show "defaults" for a run that asked for all three -- a silent
under-report of what an audit did, which on `compare_models` means a run that
sent source to a third party reads as one that did not. That half carries the
whole non-vacuity floor.

The accessor half -- `options.model` and `options.cloud_model` -- was the other
spelling until 2026-09-18, when the two model names left this component for
columns fed by `run.local_model_identifier` and its three siblings. Those are
one level shallower and `test_jsx_record_fields.py` sweeps them, so the blind
spot moved rather than closed. **The accessor guard is kept as a trap, not
retired**: it is what fires the day someone reaches back into `options` for a
model name, which is exactly the fact-shaped guess `test_jsx_run_options.py`
forbids. A floor over it would now assert that the mistake is present.

**A file of its own rather than a section of `test_option_fields.py`**, which is
already at 175 lines and would pass the ~200-line rule with this in it. The two
are cross-referenced in both directions.

Reads one component as text and the request's fields from `web/audit_request.py`,
which is free of fastapi on purpose -- so this runs on a clean checkout with no
web extra installed.
"""

import dataclasses
import re

from audit_request import PASS_THROUGH_FLAGS, AuditRequest

from .jsx_sweep import FRONTEND_SRC, accessors, strip_comments

COMPONENT = FRONTEND_SRC / "components" / "RunOptions.jsx"

# The prefix the component reads a stored options object by.
OPTIONS = "options"

# The flag table, and one key inside it. Read out of the source rather than
# transcribed: a list written here would be a fifth declaration of the same
# names, which is what this family of tests exists to prevent.
FLAGS_ARRAY = re.compile(r"const FLAGS = \[(.*?)\n\];", re.DOTALL)
FLAG_KEY = re.compile(r'\["(\w+)",')

# A floor, so a sweep that matched nothing cannot pass as a sweep that found no
# fault. Three flag keys today, and no accessors at all -- see the docstring for
# why that one is asserted as an emptiness rather than propped up by a floor.
MINIMUM_FLAG_KEYS = 3

# A field no request has ever carried, in the spelling a reader writing
# JavaScript reaches for first. This is the mistake the file is for.
FIELD_THAT_DOES_NOT_EXIST = "cloudModel"


def request_fields() -> set[str]:
    """Every field a stored `options` object carries, from the dataclass itself."""
    return {field.name for field in dataclasses.fields(AuditRequest)}


def accessors_read() -> list[tuple[str, str]]:
    """Every `options.x` the page reads, paired with the file that reads it."""
    return accessors(OPTIONS)


def flag_keys() -> set[str]:
    """The keys the component's flag table is written with."""
    found = FLAGS_ARRAY.search(strip_comments(COMPONENT.read_text(encoding="utf-8")))
    assert found, f"{COMPONENT.name} no longer declares `const FLAGS = [...];`"
    return set(FLAG_KEY.findall(found.group(1)))


def unknown_accessors(read: list[tuple[str, str]]) -> list[str]:
    """Name every `options.x` a request cannot answer, file and all, or return nothing."""
    allowed = request_fields()
    return sorted({f"{where}: {OPTIONS}.{name}" for where, name in read
                   if name not in allowed})


def unknown_names() -> list[str]:
    """Every option name the page reads that a request cannot answer, both spellings."""
    return sorted([*unknown_accessors(accessors_read()),
                   *[f"FLAGS: {name}" for name in flag_keys() - request_fields()]])


# --- every name the row reads is a name the record carries ---------------------

def test_every_option_the_row_reads_as_an_accessor_exists() -> None:
    """`options.cloudModel` is `undefined`, and React renders `undefined` as nothing."""
    assert unknown_accessors(accessors_read()) == []


def test_every_key_the_flag_table_is_written_with_exists() -> None:
    """The half no accessor sweep can see: these are read as `options[key]`."""
    assert sorted(flag_keys() - request_fields()) == []


def test_nothing_the_component_reads_is_unknown() -> None:
    """Both halves in one list, which is what a failure should report."""
    assert unknown_names() == []


# --- the sweep really swept ----------------------------------------------------

def test_the_component_reads_its_options_through_the_flag_table_alone() -> None:
    """Stated rather than floored: an accessor here would be a model name coming back.

    This is the measurement behind the docstring's claim, so the emptiness is a
    finding of its own and not a check that quietly passes on a file nobody
    read -- `test_the_flag_table_was_found_and_read` is what proves the read.
    """
    assert accessors_read() == []


def test_the_flag_table_was_found_and_read() -> None:
    """Non-vacuity: an empty set is a subset of everything."""
    assert len(flag_keys()) >= MINIMUM_FLAG_KEYS


def test_a_name_no_request_answers_is_reported_with_its_file() -> None:
    """Planted: the checks above are empty lists either way, so the report is measured."""
    planted = [("RunOptions.jsx", FIELD_THAT_DOES_NOT_EXIST)]
    assert unknown_accessors(planted) == [
        f"RunOptions.jsx: {OPTIONS}.{FIELD_THAT_DOES_NOT_EXIST}"]


# --- and the flags it shows are the flags that change what the audit does ------

def test_the_flags_shown_are_the_ones_the_wrapper_passes_through() -> None:
    """`PASS_THROUGH_FLAGS` is what becomes a command-line flag; those are what a run did.

    Equality rather than containment: a flag added to the request and not to
    this table is an option a reader is never told was on, and
    `compare_models` is the one that sends the audited source to a third party.
    """
    assert flag_keys() == set(PASS_THROUGH_FLAGS)
