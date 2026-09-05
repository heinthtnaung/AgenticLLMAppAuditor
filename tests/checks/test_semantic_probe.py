"""The semantic probe's own answers: one template, one closed question, one record.

This file is about what `run_over_repo` returns for a whole app: the four probe
outcomes, the finding beside a confirmed one, and what is asked of the model at
all. Its siblings hold the other halves -- `test_semantic_probe_replies.py` is
about the shapes a local model's answer really arrives in,
`test_semantic_probe_reading.py` calls `read_verdict` and `template_text`
directly, and `test_semantic_probe_document.py` covers what these records do to
`findings.json` and to the report, which is a different contract with different
guards behind it.

Every model answer here is a string a test wrote. The check takes its model call
as an argument and `tests/parsing/test_offline_containment.py` bars it from
importing `model_client`, so nothing in this file needs a server, and a test that
passed with Ollama down proves the injection rather than hiding a skip.
"""

import pytest

from artifacts.finding import CONFIRMED, INCONCLUSIVE, NOT_RUN, PROBE, REFUTED
from checks import semantic_probe
from checks.semantic_probe import NO_MODEL, NO_TEXT, OWASP_ID, TITLE, run_over_repo
from semantic_probe_fixtures import (
    Answering,
    F_STRING_APP,
    F_STRING_TEMPLATE,
    F_STRING_VARIABLE,
    HIDDEN_TEMPLATE_APP,
    NON_LITERAL_APP,
    NO_PROMPT_APP,
    PROBE_ID,
    PROMPT_LINE,
    PROMPT_SURFACE_ID,
    PROMPT_SURFACE_NAME,
    Refusing,
    TEMPLATE_TEXT,
    app_and_surfaces,
    only_probe,
    probe_over,
)

# A well-formed answer of each kind: the verdict word alone on the first line,
# the reasoning on the second, which is what RED_TEAM_PROMPT asks for.
VULNERABLE_REPLY = "VULNERABLE\nThe {question} value is dropped straight into the instructions."
VULNERABLE_RATIONALE = "The {question} value is dropped straight into the instructions."
SAFE_REPLY = "SAFE\nThe template names no variable, so nothing external reaches it."
SAFE_RATIONALE = "The template names no variable, so nothing external reaches it."

# The title as it has to read: a description of what the template does. Spelled
# out rather than imported, because every other assertion below compares
# `finding.title` to the module's own constant and would hold whatever it said.
DESCRIPTIVE_TITLE = ("Prompt template interpolates a value into instruction text "
                     "without delimiters")


# --- the four outcomes -------------------------------------------------------

def test_a_vulnerable_verdict_produces_one_finding_on_the_template(tmp_path) -> None:
    """The finding names the surface the model was asked about, by file and line."""
    findings, _probe = only_probe(tmp_path, VULNERABLE_REPLY)
    assert len(findings) == 1
    finding = findings[0]
    assert (finding.file, finding.line) == ("agent.py", PROMPT_LINE)
    assert finding.surface_id == PROMPT_SURFACE_ID
    assert finding.surface_name == PROMPT_SURFACE_NAME
    assert (finding.owasp_id, finding.rule_id, finding.title) == (
        OWASP_ID, semantic_probe.CHECK_NAME, TITLE)


def test_a_vulnerable_finding_is_detected_by_probe_and_cites_the_confirmed_probe(tmp_path) -> None:
    """`detection` is the vocabulary's `probe`, and `probe_id` is that probe's id.

    Both halves are load-bearing: `findings_document._check_probe_citations`
    refuses a probe finding whose id confirmed nothing, so a mismatch here would
    make the whole document unbuildable rather than merely wrong.
    """
    findings, probe = only_probe(tmp_path, VULNERABLE_REPLY)
    assert findings[0].detection == PROBE
    assert probe.outcome == CONFIRMED
    assert findings[0].probe_id == probe.id == PROBE_ID


def test_the_finding_title_describes_the_template_rather_than_asserting_a_verdict(
        tmp_path) -> None:
    """The tool's claim is structural; the verdict is the model's, and is quoted beside it.

    "Structurally vulnerable to injection" is a conclusion this auditor cannot
    reach: it never runs the audited app, and a model's opinion about a payload
    is in part a fact about that model. So the title says what the template does
    and the probe's detail carries who said what about it.
    """
    findings, probe = only_probe(tmp_path, VULNERABLE_REPLY)
    assert findings[0].title == DESCRIPTIVE_TITLE == TITLE
    assert probe.detail == VULNERABLE_RATIONALE


def test_the_models_reasoning_is_carried_as_the_probes_detail(tmp_path) -> None:
    """The rationale is evidence a reader weighs, so it is kept verbatim, not summarised."""
    _findings, probe = only_probe(tmp_path, VULNERABLE_REPLY)
    assert probe.detail == VULNERABLE_RATIONALE
    assert probe.reason is None


def test_a_safe_verdict_produces_a_refuted_probe_and_no_finding(tmp_path) -> None:
    """"The model looked and cleared it" is a result worth recording, and is not a finding."""
    findings, probe = only_probe(tmp_path, SAFE_REPLY)
    assert findings == []
    assert probe.outcome == REFUTED
    assert probe.detail == SAFE_RATIONALE


def test_an_unreachable_model_is_recorded_as_a_probe_that_did_not_run(tmp_path) -> None:
    """The audit finishes: an absent server is a missing answer, never a crashed audit."""
    repo, surfaces = app_and_surfaces(tmp_path)
    ask = Refusing(RuntimeError("cannot reach the local model server"))
    findings, probes = run_over_repo(str(repo), surfaces, ask)
    assert findings == []
    assert [(p.outcome, p.reason) for p in probes] == [(NOT_RUN, NO_MODEL)]
    assert ask.calls == 1


def test_the_unreachable_probe_says_which_server_error_it_saw(tmp_path) -> None:
    """Rule 8: the record has to tell a reader why nothing was concluded, not just that."""
    repo, surfaces = app_and_surfaces(tmp_path)
    _findings, probes = run_over_repo(
        str(repo), surfaces, Refusing(RuntimeError("connection refused")))
    assert "connection refused" in probes[0].detail


def test_a_wiring_bug_propagates_rather_than_being_filed_as_an_absent_model(tmp_path) -> None:
    """Only `RuntimeError` is a missing server. A `TypeError` is this project's own defect.

    Swallowing it would file a broken call signature as `model_unavailable` --
    an artifact saying the model could not be reached when it was never asked,
    which is a false record of what the audit did.
    """
    repo, surfaces = app_and_surfaces(tmp_path)
    with pytest.raises(TypeError, match="ask.. takes 1 argument"):
        run_over_repo(str(repo), surfaces, Refusing(TypeError("ask() takes 1 argument")))


def test_a_template_assembled_out_of_sight_is_inconclusive(tmp_path) -> None:
    """No readable text at that line means the trace left static analysis, not a safe template."""
    findings, probe = only_probe(tmp_path, VULNERABLE_REPLY, HIDDEN_TEMPLATE_APP)
    assert findings == []
    assert (probe.outcome, probe.reason) == (INCONCLUSIVE, NO_TEXT)


def test_an_unreadable_template_is_never_sent_to_the_model(tmp_path) -> None:
    """Guard: without this the inconclusive record could come from a model that said SAFE."""
    _findings, _probes, ask = probe_over(tmp_path, VULNERABLE_REPLY, HIDDEN_TEMPLATE_APP)
    assert ask.prompts == []


def test_a_template_named_by_a_variable_is_inconclusive_too(tmp_path) -> None:
    """The commonest way a prompt is built out of sight, and the same state as above.

    **Left failing on purpose.** `template_text` renders `from_template(TEMPLATE)`
    as `{TEMPLATE}`, so the check sends a template made of one placeholder to the
    model and records whatever it answers about instructions nobody read. The
    `SAFE` direction is the damaging one: it writes "the model read the template
    as structurally safe" about text this auditor never saw, which is defect 1 one
    level up. The fix belongs in `template_text` -- render as now, then answer ""
    when the rendered text is nothing but placeholders -- not in this assertion.
    """
    findings, probe = only_probe(tmp_path, VULNERABLE_REPLY, NON_LITERAL_APP)
    assert findings == []
    assert (probe.outcome, probe.reason) == (INCONCLUSIVE, NO_TEXT)


def test_a_template_named_by_a_variable_is_never_sent_to_the_model(tmp_path) -> None:
    """Left failing with its sibling above, and for the same reason: `{TEMPLATE}` is sent."""
    _findings, _probes, ask = probe_over(tmp_path, VULNERABLE_REPLY, NON_LITERAL_APP)
    assert ask.prompts == []


# --- the opt-in ---------------------------------------------------------------

def test_without_a_model_the_check_returns_nothing_at_all(tmp_path) -> None:
    """The default: no probes, no findings, so a default audit is unchanged by this check."""
    repo, surfaces = app_and_surfaces(tmp_path)
    assert run_over_repo(str(repo), surfaces) == ([], [])
    assert run_over_repo(str(repo), surfaces, None) == ([], [])


def test_the_repository_it_returns_nothing_for_really_holds_a_template(tmp_path) -> None:
    """Guard: the two empty answers above would pass on an app with nothing to probe."""
    repo, surfaces = app_and_surfaces(tmp_path)
    assert [s.id for s in semantic_probe.prompt_surfaces(surfaces, "agent.py")] == [
        PROMPT_SURFACE_ID]


def test_an_app_with_no_prompt_template_produces_no_probe_even_with_a_model(tmp_path) -> None:
    """Nothing to look at is not a clean bill, so there is no record of having looked."""
    repo, surfaces = app_and_surfaces(tmp_path, NO_PROMPT_APP)
    ask = Answering(VULNERABLE_REPLY)
    assert run_over_repo(str(repo), surfaces, ask) == ([], [])
    assert ask.prompts == []


def test_the_model_is_shown_the_template_inside_the_red_team_prompt(tmp_path) -> None:
    """What was asked is as much a fact about the run as what came back."""
    _findings, _probes, ask = probe_over(tmp_path, SAFE_REPLY)
    assert len(ask.prompts) == 1
    assert TEMPLATE_TEXT in ask.prompts[0]
    assert "VULNERABLE or SAFE" in ask.prompts[0]


def test_an_f_strings_interpolation_point_reaches_the_prompt_the_model_is_sent(tmp_path) -> None:
    """The value the question is about must be in the text, not deleted before it is asked.

    The earlier renderer kept the string constants only, so this template arrived
    as "You are a " + newline + " agent. Answer the user." -- the variable gone
    and a separator put in its place. The model was then asked whether a value
    sits there undelimited, about a template with neither.
    """
    _findings, _probes, ask = probe_over(tmp_path, SAFE_REPLY, F_STRING_APP)
    assert len(ask.prompts) == 1
    assert F_STRING_TEMPLATE in ask.prompts[0]
    assert F_STRING_VARIABLE in ask.prompts[0]
