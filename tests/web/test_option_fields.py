"""The request is declared three times, and the three declarations must agree.

`AuditOptions` (pydantic, in `web/run_routes.py`) is the JSON body the page posts.
`AuditRequest` (a frozen dataclass, in `web/audit_request.py`) is what the
refusal rules are written against. One line joins them --
`AuditRequest(**options.model_dump())` -- so a field added to one alone is not
a validation error a caller can read and fix. It is a `TypeError` raised inside
the handler, and a 500 in the browser. It moved out of `api.py` with the routes
that use it, which is the only thing about this file that changed when the
endpoint became a job.

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

The field *set* is what is asserted, not the field *list*: adding an option to
both declarations is an ordinary change and must stay one. What may not happen
is adding it to one.
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

# One request with nothing left defaulted, so the join is shown to carry every
# value across rather than to construct successfully.
POSTED = {"url": "https://example.invalid/owner/demo-app", "semantic_probe": True,
          "draft_key": True, "compare_models": True, "cloud_model": "vendor/hosted"}


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


def test_the_two_declarations_name_the_same_fields() -> None:
    """The join is `AuditRequest(**options.model_dump())`; a field in one alone is a 500."""
    assert request_fields() == option_fields()


def test_both_declarations_name_the_fields_that_send_source_off_the_machine() -> None:
    """Non-vacuity: two empty sets are equal, so the sweep is given something to find."""
    assert CONSEQUENTIAL_FIELDS <= request_fields()
    assert CONSEQUENTIAL_FIELDS <= option_fields()


def test_every_posted_option_reaches_the_request_the_join_builds() -> None:
    """Not just constructible: each value posted is the value the rules are applied to."""
    joined = AuditRequest(**AuditOptions(**POSTED).model_dump())
    assert joined == AuditRequest(**POSTED)


def test_the_joined_request_is_the_one_the_page_asked_for() -> None:
    """Guard on the test above: the two sides would agree if both were the defaults."""
    joined = AuditRequest(**AuditOptions(**POSTED).model_dump())
    assert joined.compare_models is True
    assert joined.cloud_model == POSTED["cloud_model"]


def test_the_page_starts_with_the_fields_the_endpoint_declares() -> None:
    """The third declaration: a key too few nobody can set, one too many is silently dropped."""
    assert initial_keys() == option_fields()


def test_exactly_one_component_declares_what_the_form_starts_as() -> None:
    """Two copies would make the check above true of one of them and blind to the other."""
    assert len(declaring_files()) == 1


def test_the_pages_declaration_names_the_fields_that_send_source_off_the_machine() -> None:
    """Non-vacuity: an INITIAL the regex failed to read would be an empty set."""
    assert CONSEQUENTIAL_FIELDS <= initial_keys()
