"""What the web UI may ask for, refused and passed through.

`web/audit_request.py` is free of FastAPI on purpose, so this file is too: the
rules a browser request is held to are testable on a clean checkout where
the server packages were never installed. Nothing here starts a server, opens
a socket or runs an audit.

Every refusal is exercised on and off, because a rule that only ever fires is
indistinguishable from one that always does. The `to_argv` cases assert the
whole list rather than membership, so a flag the request did not ask for cannot
hide in it -- a checkbox that quietly grew a `--compare-models` would send the
audited repository's source to a third party.

**`auditor` is not a field of this request, and the absence is the subject of
three tests below.** It was one, and `options` is stored as `asdict(asked)` --
so the name landed in the options a re-run replays, and replaying them would
re-run the audit *as someone else*. The name now travels beside the request and
lands on the run record; the rules that refuse a bad one are
`test_auditor_refusals.py`, and that no artifact ever holds one is
`test_auditor_not_in_artifacts.py`.

The last test parses the built argv with `main.build_parser()`, which is the
claim `to_argv`'s docstring makes: the parser owns the defaults, so a flag it
does not accept is a failure here rather than at the first real request.
"""

import dataclasses

import pytest

from audit_request import (
    PASS_THROUGH_FLAGS, PASS_THROUGH_VALUES, REQUIRED_SCHEME, REQUIRES, AuditRequest)
from main import build_parser

URL = "https://example.invalid/owner/demo"
CLOUD_MODEL = "vendor/hosted-model-1"

# A local model this machine need not have pulled: `to_argv` builds a command
# line, it does not check one, and nothing here starts an audit.
LOCAL_MODEL = "a-second-model:7b-instruct"

# A stand-in for any value-carrying option, where only the option's spelling is
# the subject and the value is not.
ANY_VALUE = "some-value"

# The field this request may not grow back, and a name to look for it under.
AUDITOR_FIELD = "auditor"
AUDITOR = "Quokka Reviewer"

# The two short refusals, spelled as the module writes them. The third is a
# paragraph explaining what a filesystem path would cost, so it is matched by
# its opening rather than transcribed and left to drift.
NO_REPOSITORY = "no repository was given"
CLOUD_WITHOUT_COMPARISON = "a cloud model was named but model comparison is off"
NOT_HTTPS_OPENING = f"the repository must be an {REQUIRED_SCHEME} link"
# The fourth, also a paragraph: it names the three options that would consult a
# model, so it is matched by its opening for the same reason as the one above.
LOCAL_MODEL_UNCONSULTED_OPENING = (
    "a local model was named but nothing here would consult one")

# The three options that make an audit call a model at all. Any one of them is
# enough, which is why this rule is not an entry in `REQUIRES` -- that map pairs
# an option with *one* other option it depends on.
CONSULT_A_MODEL = ("semantic_probe", "draft_key", "compare_models")

# What the command line spells for each option, read from the map the module
# owns rather than respelled here.
PROBE_FLAG = PASS_THROUGH_FLAGS["semantic_probe"]
DRAFT_KEY_FLAG = PASS_THROUGH_FLAGS["draft_key"]
COMPARE_FLAG = PASS_THROUGH_FLAGS["compare_models"]
MODEL_OPTION = PASS_THROUGH_VALUES["model"]
CLOUD_MODEL_OPTION = PASS_THROUGH_VALUES["cloud_model"]

# The six fields a request really is, so the absence above is asserted against
# a named whole rather than against one missing name. A request that lost a
# field would be as wrong as one that grew the name back. `model` joined them
# when a run gained the right to name which pulled model it audits with.
EXPECTED_REQUEST_FIELDS = {"url", "model", "semantic_probe", "draft_key",
                           "compare_models", "cloud_model"}

# The one dependency between options, as the module declares it: `--cloud-model`
# names the hosted arm, which exists only under `--compare-models`. `model` is
# deliberately not in it -- an ordinary audit may name a local model.
EXPECTED_REQUIREMENTS = {"cloud_model": "compare_models"}


def request_fields() -> set[str]:
    """The field names of the dataclass the refusal rules are written against."""
    return {field.name for field in dataclasses.fields(AuditRequest)}


def test_a_plain_https_request_is_refused_for_nothing() -> None:
    """Non-vacuity: a request that breaks no rule returns an empty list, not a message."""
    assert AuditRequest(url=URL).refusals() == []


def test_an_empty_url_is_refused() -> None:
    """No repository is the first thing checked, and it is said in those words."""
    assert AuditRequest(url="").refusals() == [NO_REPOSITORY]


def test_a_url_of_only_whitespace_is_refused_as_empty() -> None:
    """A padded field from a browser is empty, not a repository named ' '."""
    assert AuditRequest(url="   \n").refusals() == [NO_REPOSITORY]


def test_a_filesystem_path_is_refused() -> None:
    """The refusal this endpoint exists to make: a path resolves against the server's disk."""
    refused = AuditRequest(url="/etc/passwd").refusals()
    assert len(refused) == 1
    assert refused[0].startswith(NOT_HTTPS_OPENING)


def test_an_http_url_is_refused() -> None:
    """The scheme is checked, not merely the presence of one: `http://` is not `https://`."""
    refused = AuditRequest(url="http://example.invalid/owner/demo").refusals()
    assert len(refused) == 1
    assert refused[0].startswith(NOT_HTTPS_OPENING)


def test_a_cloud_model_named_with_comparison_off_is_refused() -> None:
    """A named hosted model that nothing would use is a request that misreads itself."""
    assert AuditRequest(url=URL, cloud_model=CLOUD_MODEL).refusals() == [
        CLOUD_WITHOUT_COMPARISON]


def test_a_cloud_model_named_with_comparison_on_is_allowed() -> None:
    """The same field with the flag it belongs to is the supported request, not a refusal."""
    asked = AuditRequest(url=URL, compare_models=True, cloud_model=CLOUD_MODEL)
    assert asked.refusals() == []


def test_comparison_without_a_named_model_is_allowed() -> None:
    """The command line falls back to the configured model, so an empty field is legal."""
    assert AuditRequest(url=URL, compare_models=True).refusals() == []


def test_two_faults_are_both_reported() -> None:
    """Every reason, not the first: a caller fixing one must not discover the next by rerunning."""
    asked = AuditRequest(url="", cloud_model=CLOUD_MODEL)
    assert asked.refusals() == [NO_REPOSITORY, CLOUD_WITHOUT_COMPARISON]


# --- the name that is not a field here ----------------------------------------

def test_the_request_declares_exactly_the_six_options_it_audits_with() -> None:
    """Named as a whole set: a request that lost a field is as wrong as one that grew a name."""
    assert request_fields() == EXPECTED_REQUEST_FIELDS


def test_the_request_has_no_field_for_who_asked_for_it() -> None:
    """It had one. `options` is `asdict(asked)`, so the name rode in what a re-run replays."""
    assert AUDITOR_FIELD not in request_fields()


def test_what_a_re_run_replays_names_nobody() -> None:
    """The consequence, said as the stored options: replaying these re-runs the same audit.

    Not the same assertion as the field check above. That one reads the
    declaration; this one reads what is actually written to the `options`
    column, which is the value a re-run would be built from.
    """
    stored = dataclasses.asdict(AuditRequest(url=URL, compare_models=True,
                                             cloud_model=CLOUD_MODEL))
    assert AUDITOR_FIELD not in stored
    assert not any(AUDITOR in str(value) for value in stored.values())


def test_the_parser_has_no_option_the_auditor_could_travel_in() -> None:
    """The other direction: nothing the command line accepts is a place to put a name."""
    parsed = build_parser().parse_args(AuditRequest(url=URL).to_argv())
    assert AUDITOR_FIELD not in vars(parsed)


# --- the command line the request means ---------------------------------------

def test_a_bare_request_passes_the_url_and_nothing_else() -> None:
    """The default command line is the URL alone: no flag is invented for a default."""
    assert AuditRequest(url=URL).to_argv() == [URL]


def test_no_flag_that_was_not_asked_for_appears() -> None:
    """Stated as the whole flag vocabulary, so a fourth flag added later is covered too."""
    argv = AuditRequest(url=URL).to_argv()
    assert set(argv) & set(PASS_THROUGH_FLAGS.values()) == set()


def test_the_semantic_probe_flag_is_passed_through() -> None:
    """The flag that puts model-authored findings in findings.json rides along when asked."""
    assert AuditRequest(url=URL, semantic_probe=True).to_argv() == [URL, PROBE_FLAG]


def test_the_draft_key_flag_is_passed_through() -> None:
    """The flag that lets the model author a grading key draft rides along when asked."""
    assert AuditRequest(url=URL, draft_key=True).to_argv() == [URL, DRAFT_KEY_FLAG]


def test_the_compare_models_flag_is_passed_through() -> None:
    """The flag that sends the audited source to a third party rides along when asked."""
    assert AuditRequest(url=URL, compare_models=True).to_argv() == [URL, COMPARE_FLAG]


def test_every_option_at_once_builds_the_whole_command_line() -> None:
    """All six together: the flags in the order their map declares, then the value options."""
    asked = AuditRequest(url=URL, model=LOCAL_MODEL, semantic_probe=True, draft_key=True,
                         compare_models=True, cloud_model=CLOUD_MODEL)
    assert asked.to_argv() == [URL, PROBE_FLAG, DRAFT_KEY_FLAG, COMPARE_FLAG,
                               MODEL_OPTION, LOCAL_MODEL,
                               CLOUD_MODEL_OPTION, CLOUD_MODEL]


def test_a_cloud_model_never_rides_along_without_comparison() -> None:
    """The refused combination must also build no command line naming the hosted model."""
    argv = AuditRequest(url=URL, cloud_model=CLOUD_MODEL).to_argv()
    assert argv == [URL]
    assert CLOUD_MODEL not in argv


def test_an_empty_cloud_model_is_not_passed_as_a_flag() -> None:
    """`--cloud-model ''` would name no model; the parser's own default is the answer."""
    assert AuditRequest(url=URL, compare_models=True,
                        cloud_model="  ").to_argv() == [URL, COMPARE_FLAG]


def test_the_url_and_the_model_name_are_stripped() -> None:
    """A browser field arrives padded, and a padded URL is not a directory name."""
    asked = AuditRequest(url=f"  {URL}  ", compare_models=True,
                         cloud_model=f" {CLOUD_MODEL} ")
    assert asked.to_argv() == [URL, COMPARE_FLAG, CLOUD_MODEL_OPTION, CLOUD_MODEL]


def test_the_built_command_line_parses_with_the_real_parser() -> None:
    """The claim `to_argv` makes: it is built for `main.build_parser`, not a hand-made Namespace."""
    asked = AuditRequest(url=URL, model=LOCAL_MODEL, semantic_probe=True, draft_key=True,
                         compare_models=True, cloud_model=CLOUD_MODEL)
    args = build_parser().parse_args(asked.to_argv())
    assert (args.repo_path, args.model, args.cloud_model) == (URL, LOCAL_MODEL, CLOUD_MODEL)
    assert (args.semantic_probe, args.draft_key, args.compare_models) == (True, True, True)


def test_the_parser_defaults_every_flag_off_for_a_bare_request() -> None:
    """The other direction: nothing the request left alone arrives switched on."""
    args = build_parser().parse_args(AuditRequest(url=URL).to_argv())
    assert (args.semantic_probe, args.draft_key, args.compare_models) == (False, False, False)
    assert args.cloud_model is None
    # None, not "": the parser owns the default, and `local_model` resolves
    # `name or MODEL`. A request naming no model must not name one.
    assert args.model is None


# --- the local model a run may name -------------------------------------------

def test_a_named_local_model_is_passed_through() -> None:
    """The option that decides which pulled model answers, and so which one the artifact names."""
    assert AuditRequest(url=URL, model=LOCAL_MODEL).to_argv() == [
        URL, MODEL_OPTION, LOCAL_MODEL]


def test_a_named_local_model_with_nothing_to_consult_it_is_refused() -> None:
    """An ordinary audit makes no model call at all, so naming one is a request that does nothing.

    `audit_run.local_model(wanted, name)` returns None when nothing asked for a
    model, and `audit_run.audit` with None is the offline path -- no socket, no
    call, `findings.json` byte-identical. So the name would be accepted,
    recorded in the run's options, replayed on a re-run, and never used. Said
    rather than silently ignored, which is the rule the hosted model already
    follows.
    """
    said = AuditRequest(url=URL, model=LOCAL_MODEL).refusals()
    assert len(said) == 1
    assert said[0].startswith(LOCAL_MODEL_UNCONSULTED_OPENING)


@pytest.mark.parametrize("option", CONSULT_A_MODEL)
def test_each_option_that_consults_a_model_lets_a_name_through(option: str) -> None:
    """All three, not the one that made the rule: an option that stopped asking is a silent gate."""
    assert AuditRequest(url=URL, model=LOCAL_MODEL, **{option: True}).refusals() == []


def test_the_refusal_names_what_would_lift_it() -> None:
    """A refusal a reader cannot act on is a dead end; this one lists the three ways out."""
    said = AuditRequest(url=URL, model=LOCAL_MODEL).refusals()[0]
    assert "semantic probe" in said
    assert "drafted key" in said
    assert "model comparison" in said


def test_the_local_model_rule_is_not_one_of_the_named_dependencies() -> None:
    """`REQUIRES` pairs an option with one other; this rule is satisfied by any of three."""
    assert "model" not in REQUIRES


def test_an_empty_local_model_is_not_passed_as_an_option() -> None:
    """`--model ''` would name no model; the configured one is the answer, so nothing is sent."""
    assert AuditRequest(url=URL, model="").to_argv() == [URL]


def test_a_local_model_of_only_whitespace_is_not_passed_either() -> None:
    """A padded field from a browser is an unfilled field, not a model called ' '."""
    assert AuditRequest(url=URL, model="   ").to_argv() == [URL]


def test_the_local_model_name_is_stripped() -> None:
    """A model name reaches argv, so a padded one would be a model nothing has pulled."""
    assert AuditRequest(url=URL, model=f"  {LOCAL_MODEL}\n").to_argv() == [
        URL, MODEL_OPTION, LOCAL_MODEL]


def test_the_two_model_options_are_told_apart() -> None:
    """One local, one hosted, both value-carrying: swapping them would audit with the wrong one."""
    asked = AuditRequest(url=URL, model=LOCAL_MODEL, compare_models=True,
                         cloud_model=CLOUD_MODEL)
    args = build_parser().parse_args(asked.to_argv())
    assert args.model == LOCAL_MODEL
    assert args.cloud_model == CLOUD_MODEL


# --- the maps that decide all of the above ------------------------------------

def test_the_only_dependency_between_options_is_the_hosted_models() -> None:
    """Stated as the whole map: a second dependency added quietly would gate an option nobody gated."""
    assert REQUIRES == EXPECTED_REQUIREMENTS


def test_every_option_the_maps_name_is_a_field_of_the_request() -> None:
    """A typo'd key would pass through nothing; a typo'd requirement raises `AttributeError`."""
    named = set(PASS_THROUGH_FLAGS) | set(PASS_THROUGH_VALUES) | set(REQUIRES.values())
    assert named <= request_fields()
    assert named, "the maps named nothing, so the check above is vacuous"


def test_every_option_the_maps_spell_is_one_the_real_parser_accepts() -> None:
    """The other half of `to_argv`'s claim: every spelling in the maps, not only the ones a case builds.

    An option the parser does not know exits with a usage error rather than
    returning, so parsing all of them at once is the assertion. The field names
    are checked against the parsed namespace in the same breath, because a map
    whose key is not the option's `dest` passes a value through under a name
    `main.run` never reads.
    """
    argv = [URL, *PASS_THROUGH_FLAGS.values()]
    for option in PASS_THROUGH_VALUES.values():
        argv += [option, ANY_VALUE]
    parsed = vars(build_parser().parse_args(argv))
    assert set(PASS_THROUGH_FLAGS) | set(PASS_THROUGH_VALUES) <= set(parsed)
