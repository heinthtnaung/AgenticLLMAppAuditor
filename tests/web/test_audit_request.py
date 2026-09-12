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

The last test parses the built argv with `main.build_parser()`, which is the
claim `to_argv`'s docstring makes: the parser owns the defaults, so a flag it
does not accept is a failure here rather than at the first real request.
"""

from audit_request import PASS_THROUGH_FLAGS, REQUIRED_SCHEME, AuditRequest
from main import build_parser

URL = "https://example.invalid/owner/demo"
CLOUD_MODEL = "vendor/hosted-model-1"

# The two short refusals, spelled as the module writes them. The third is a
# paragraph explaining what a filesystem path would cost, so it is matched by
# its opening rather than transcribed and left to drift.
NO_REPOSITORY = "no repository was given"
CLOUD_WITHOUT_COMPARISON = "a cloud model was named but model comparison is off"
NOT_HTTPS_OPENING = f"the repository must be an {REQUIRED_SCHEME} link"

# What the command line spells for each option, read from the map the module
# owns rather than respelled here.
PROBE_FLAG = PASS_THROUGH_FLAGS["semantic_probe"]
DRAFT_KEY_FLAG = PASS_THROUGH_FLAGS["draft_key"]
COMPARE_FLAG = PASS_THROUGH_FLAGS["compare_models"]
CLOUD_MODEL_FLAG = "--cloud-model"


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
    asked = AuditRequest(url=URL, cloud_model=CLOUD_MODEL)
    assert asked.refusals() == [CLOUD_WITHOUT_COMPARISON]


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
    """All four together, in the order the flag map declares, with the model last."""
    asked = AuditRequest(url=URL, semantic_probe=True, draft_key=True,
                         compare_models=True, cloud_model=CLOUD_MODEL)
    assert asked.to_argv() == [URL, PROBE_FLAG, DRAFT_KEY_FLAG, COMPARE_FLAG,
                               CLOUD_MODEL_FLAG, CLOUD_MODEL]


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
    assert asked.to_argv() == [URL, COMPARE_FLAG, CLOUD_MODEL_FLAG, CLOUD_MODEL]


def test_the_built_command_line_parses_with_the_real_parser() -> None:
    """The claim `to_argv` makes: it is built for `main.build_parser`, not a hand-made Namespace."""
    asked = AuditRequest(url=URL, semantic_probe=True, draft_key=True,
                         compare_models=True, cloud_model=CLOUD_MODEL)
    args = build_parser().parse_args(asked.to_argv())
    assert (args.repo_path, args.cloud_model) == (URL, CLOUD_MODEL)
    assert (args.semantic_probe, args.draft_key, args.compare_models) == (True, True, True)


def test_the_parser_defaults_every_flag_off_for_a_bare_request() -> None:
    """The other direction: nothing the request left alone arrives switched on."""
    args = build_parser().parse_args(AuditRequest(url=URL).to_argv())
    assert (args.semantic_probe, args.draft_key, args.compare_models) == (False, False, False)
    assert args.cloud_model is None
