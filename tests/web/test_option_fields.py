"""The request is declared three times, and the three declarations must agree.

`AuditOptions` (pydantic, in `web/run_routes.py`) is the JSON body the page posts.
`AuditRequest` (a frozen dataclass, in `web/audit_request.py`) is what the
refusal rules are written against. Three lines join them --
`model_dump()`, then `pop("auditor")`, then `AuditRequest(**named)` -- so a
field added to one alone is not a validation error a caller can read and fix.
It is a `TypeError` raised inside the handler, and a 500 in the browser.

**The two declarations differ by exactly one field, and that is the design.**
`auditor` is posted, so `AuditOptions` declares it; it is not an option of the
audit, so `AuditRequest` does not. The route pops it and hands it to
`Registry.start` beside the request. Asserting the two field sets *equal* is
what this file used to do, and it is what let the name reach `options` -- which
`docs/SCHEMAS.md` calls "exactly `AuditRequest`'s fields, so a re-run is exact",
and a re-run carrying a name would re-run the audit as someone else. So the
relationship is asserted as one named difference rather than as equality: a
second extra field is as much a defect as the first was.

The third declaration is `INITIAL` in the frontend: the object the form starts
as and posts as its body. It is found by searching the JSX rather than by a
fixed path -- it began in `App.jsx` and now lives in `pages/AuditPage.jsx`,
which broke this file once and should not again -- and exactly one file may
declare it. It drifts the same way and is *silent*
about it in both directions -- a key missing there is an option nobody can set,
which pydantic then fills from its default, and a key too many is dropped
without a word, because a pydantic model ignores extra fields unless told
otherwise. Neither is an error anybody sees. It is parsed out of the JSX as
text: there is no JavaScript in this suite, and running it must not need Node.

Three declarations rather than one is a deliberate trade. `audit_request.py` is
free of FastAPI so the refusals can be tested on a checkout with no web extra
installed, which `test_audit_request.py` does and this file cannot; `App.jsx`
is JavaScript because the page is. The cost of both choices is exactly this
file, and it is cheaper than the alternatives.

**A fourth reader is not in this file.** The history row shows what a stored run
asked for, reading `run.options.x` and `options[key]` off the record -- names
that come from the same dataclass and drift the same way, and that
`test_jsx_record_fields.py` cannot see because it sweeps `run.<field>` and stops
at `options`. `test_jsx_stored_option_fields.py` holds those. It is a separate
file because this one is already at the ~200-line rule, not because the subject
is different.

The field *set* is what is asserted, not the field *list*: adding an option to
both declarations is an ordinary change and must stay one. What may not happen
is adding it to one.

It keeps `auditor: str = ""` rather than making it required of pydantic, so a
body that omits it is refused by the rules with the other refusals, as a 400
naming what to do, rather than by pydantic as a 422 nobody reads.
"""

import dataclasses
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")

from audit_request import AuditRequest    # noqa: E402
from run_routes import AuditOptions       # noqa: E402

# Where the third declaration lives, and how to read it: the object literal
# between `const INITIAL = {` and the `};` that closes it, then one key per
# line. The `export` is optional in the pattern because the constant is now
# imported by another component, and which file holds it is not this test's
# business -- only that one file does.
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
INITIAL_PATTERN = re.compile(r"(?:export )?const INITIAL = \{(.*?)\n\};", re.DOTALL)
KEY_PATTERN = re.compile(r"^\s*([A-Za-z_]\w*):", re.MULTILINE)

# The three fields that decide whether the audited source leaves this machine.
# Named as a floor under the sweep: a comparison of two empty sets is true, and
# would stay true if both declarations were emptied.
CONSEQUENTIAL_FIELDS = frozenset({"url", "compare_models", "cloud_model"})

# One body with nothing left defaulted, so the join is shown to carry every
# value across rather than to construct successfully. A field left defaulted
# here would be a field the join was never shown to carry.
POSTED = {"url": "https://example.invalid/owner/demo-app", "auditor": "Quokka Reviewer",
          "model": "a-second-model:7b-instruct", "semantic_probe": True,
          "draft_key": True, "compare_models": True, "cloud_model": "vendor/hosted"}

# The one field the posted body carries that the audited request does not.
AUDITOR_FIELD = "auditor"


def request_fields() -> set[str]:
    """The field names of the dataclass the refusal rules are written against."""
    return {field.name for field in dataclasses.fields(AuditRequest)}


def option_fields() -> set[str]:
    """The field names of the model the page's JSON body is parsed into."""
    return set(AuditOptions.model_fields)


def declaring_files() -> list[Path]:
    """Every JSX file that declares the object the form starts as."""
    return [source for source in sorted(FRONTEND_SRC.rglob("*.jsx"))
            if INITIAL_PATTERN.search(source.read_text(encoding="utf-8"))]


def initial_keys() -> set[str]:
    """The keys the form starts with, which are the keys it posts."""
    declared = declaring_files()
    if len(declared) != 1:
        raise AssertionError(
            f"expected one `const INITIAL = {{...}};` object under {FRONTEND_SRC}, "
            f"found {[str(path) for path in declared]}")
    body = INITIAL_PATTERN.search(declared[0].read_text(encoding="utf-8"))
    return set(KEY_PATTERN.findall(body.group(1)))


def joined(posted: dict) -> AuditRequest:
    """The request the route builds from a posted body, joined the way the route joins it."""
    named = AuditOptions(**posted).model_dump()
    named.pop(AUDITOR_FIELD)
    return AuditRequest(**named)


def test_the_posted_body_is_the_request_plus_the_name_and_nothing_else() -> None:
    """The one permitted difference, named. A second extra field is a `TypeError` in the handler."""
    assert option_fields() == request_fields() | {AUDITOR_FIELD}


def test_the_name_is_posted_and_is_not_a_field_of_the_audited_request() -> None:
    """Both halves said plainly, because the asymmetry is what `options` depends on."""
    assert AUDITOR_FIELD in option_fields()
    assert AUDITOR_FIELD not in request_fields()


def test_a_body_with_no_name_at_all_still_parses() -> None:
    """`auditor: str = ""` is why: a missing name is a 400 from the rules, not a 422 from pydantic.

    The refusal carries a sentence saying what to do. A 422 carries pydantic's
    own validation shape, which the page's error path -- which keeps only
    `detail` -- would show as nothing useful at all.
    """
    without = {key: value for key, value in POSTED.items() if key != AUDITOR_FIELD}
    assert AuditOptions(**without).auditor == ""


def test_both_declarations_name_the_fields_that_send_source_off_the_machine() -> None:
    """Non-vacuity: two empty sets are equal, so the sweep is given something to find."""
    assert CONSEQUENTIAL_FIELDS <= request_fields()
    assert CONSEQUENTIAL_FIELDS <= option_fields()


def test_every_posted_option_reaches_the_request_the_join_builds() -> None:
    """Not just constructible: each value posted is the value the rules are applied to."""
    audited = {key: value for key, value in POSTED.items() if key != AUDITOR_FIELD}
    assert joined(POSTED) == AuditRequest(**audited)


def test_the_joined_request_is_the_one_the_page_asked_for() -> None:
    """Guard on the test above: the two sides would agree if both were the defaults."""
    built = joined(POSTED)
    assert built.compare_models is True
    assert built.cloud_model == POSTED["cloud_model"]


def test_the_name_the_body_carried_survives_the_join_that_drops_it() -> None:
    """Dropped from the request, not from the run: the route hands it to `Registry.start`."""
    assert AuditOptions(**POSTED).auditor == POSTED[AUDITOR_FIELD]
    assert not hasattr(joined(POSTED), AUDITOR_FIELD)


def test_the_page_starts_with_the_fields_the_endpoint_declares() -> None:
    """The third declaration: a key too few nobody can set, one too many is silently dropped."""
    assert initial_keys() == option_fields()


def test_exactly_one_component_declares_what_the_form_starts_as() -> None:
    """Two copies would make the check above true of one of them and blind to the other."""
    assert len(declaring_files()) == 1


def test_the_pages_declaration_names_the_fields_that_send_source_off_the_machine() -> None:
    """Non-vacuity: an INITIAL the regex failed to read would be an empty set."""
    assert CONSEQUENTIAL_FIELDS <= initial_keys()
