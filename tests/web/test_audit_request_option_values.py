"""A model name the command line would read as another option.

`model` and `cloud_model` are the only two fields whose *text* reaches
`main.build_parser`, and until now they reached it unvalidated. A value starting
with `-` makes `parse_args` print usage and call `sys.exit`, and **`SystemExit`
is a `BaseException`**: it escaped both of `run_jobs._work`'s catches, the
worker thread died, the `finally` freed the slot, and the run row said `running`
for ever -- `history_store._reconcile` only runs when the store is opened, so
nothing cleared it until the server restarted. Reachable from an
unauthenticated `POST /api/audit`.

Two fixes, held in two places. This file is the request rule, which is the one
that stops it happening; `test_run_jobs_worker_escape.py` is the worker's own
catch, which is defence in depth for the *next* escape rather than for this one.

**The sweep is driven off `PASS_THROUGH_VALUES`**, not off the two field names,
for the same reason `_option_shaped_values` is: a third value-carrying option
added to that map would otherwise pass its text through with nothing checking
it, and no test would say so.

Free of FastAPI, like `web/audit_request.py` and `test_audit_request.py` beside
it: nothing here starts a server, opens a socket or runs an audit. The last
section builds the real parser, which is the whole reason the rule exists.
"""

import pytest

from audit_request import PASS_THROUGH_VALUES, AuditRequest
from main import build_parser

URL = "https://example.invalid/owner/demo"

# The value that was measured, and a long option that reads as a request for
# usage rather than as a model nobody has pulled.
OPTION_SHAPED = "-x"
LONG_OPTION_SHAPED = "--help"
OPTION_SHAPED_VALUES = (OPTION_SHAPED, LONG_OPTION_SHAPED)

# The same value as a browser text field leaves it. Stripped before the check,
# because it is stripped before `to_argv` builds the command line.
PADDED = f"  {OPTION_SHAPED}  "

# An ordinary name for each option. The local one carries two dashes *inside*
# it, which is the case a `"-" in value` rule would have refused: every model
# this project pulls is spelled that way.
ORDINARY = {"model": "qwen2.5-coder:7b-instruct", "cloud_model": "vendor/hosted-model-1"}

# What each value-carrying option needs beside it to be an otherwise legal
# request: a local model only counts if something would consult one, and a
# hosted model only under comparison. Named so a refusal that comes back is
# about the value and never about the combination.
LEGAL_BESIDE = {"model": {"semantic_probe": True},
                "cloud_model": {"compare_models": True}}

# What the refusal has to say, so a caller is told which field to fix.
MAY_NOT_START_WITH = "may not start with '-'"

# Every field the sweep covers, read off the module's own map.
VALUE_FIELDS = tuple(PASS_THROUGH_VALUES)


def a_request_naming(field: str, value: str) -> AuditRequest:
    """One otherwise-legal request whose value-carrying option holds `value`."""
    return AuditRequest(url=URL, **{field: value}, **LEGAL_BESIDE[field])


# --- the rule ---------------------------------------------------------------

@pytest.mark.parametrize("field", VALUE_FIELDS)
@pytest.mark.parametrize("value", OPTION_SHAPED_VALUES)
def test_a_value_that_reads_as_an_option_is_refused(field: str, value: str) -> None:
    """The fault itself, on both fields: this is the text that reaches argparse."""
    said = a_request_naming(field, value).refusals()
    assert len(said) == 1, said
    assert MAY_NOT_START_WITH in said[0]


@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_the_refusal_names_the_field_and_quotes_what_was_sent(field: str) -> None:
    """A refusal a caller cannot act on is a dead end; this one names the box to fix."""
    said = a_request_naming(field, OPTION_SHAPED).refusals()[0]
    assert field in said
    assert repr(OPTION_SHAPED) in said


@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_a_padded_value_is_refused_too(field: str) -> None:
    """Stripped first, because `to_argv` strips: the padding never reaches the parser either."""
    assert a_request_naming(field, PADDED).refusals() != []


# --- the off positions ------------------------------------------------------

@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_an_ordinary_name_is_not_refused(field: str) -> None:
    """Non-vacuity: a rule that only ever fires is indistinguishable from one that always does."""
    assert a_request_naming(field, ORDINARY[field]).refusals() == []


@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_a_dash_inside_the_name_is_not_a_refusal(field: str) -> None:
    """`qwen2.5-coder:7b-instruct` is what this machine pulls; only a *leading* dash is an option."""
    assert "-" in ORDINARY[field]
    assert a_request_naming(field, ORDINARY[field]).refusals() == []


@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_an_empty_value_is_not_refused(field: str) -> None:
    """An unfilled box names no model and builds no option, so there is nothing to refuse."""
    assert AuditRequest(url=URL, **LEGAL_BESIDE[field]).refusals() == []


# --- the map the sweep is driven off ----------------------------------------

def test_every_value_carrying_option_is_swept() -> None:
    """The guard on this file: a third field added to the map arrives with no case here.

    `LEGAL_BESIDE` is what makes a request about that field legal otherwise, so
    a field with no entry cannot be swept silently -- it raises a `KeyError`
    rather than passing.
    """
    assert set(LEGAL_BESIDE) == set(PASS_THROUGH_VALUES)
    assert VALUE_FIELDS, "the map named nothing, so every sweep above is vacuous"


# --- why the rule exists at all ---------------------------------------------

@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_the_real_parser_exits_on_the_value_this_refuses(field: str) -> None:
    """The measured consequence, driven through the parser the wrapper actually calls.

    `to_argv` still builds the command line -- the refusal is the only thing
    between this text and `parse_args`, which does not return at all. What that
    does to a run row is `test_run_jobs_worker_escape.py`.
    """
    argv = a_request_naming(field, OPTION_SHAPED).to_argv()
    with pytest.raises(SystemExit):
        build_parser().parse_args(argv)


def test_the_class_the_parser_raises_is_not_an_exception() -> None:
    """The whole reason this was a wedged row and not a failed run.

    `except Exception` does not hold a `SystemExit`, so the worker thread died
    silently and the row it had written was never rewritten.
    """
    assert not issubclass(SystemExit, Exception)
