"""Guards on naming a council run's models on both pages: the start of each digest, briefly."""

from dataclasses import replace

from council_runs import DISSENTING, council_ran
from report.council_words import UNKNOWN_DIGEST, UNKNOWN_VERSION, models_named
from report.html_report import as_html
from report.model_identity import (
    ESCALATION_ROLE,
    MEMBER_ROLE,
    ModelDigest,
    OllamaVersion,
    UnknownDigest,
    UnknownOllamaVersion,
)
from report.provenance import LocalModels
from report.record import build_report
from report.text_council import council_block
from report_samples import PROVENANCE, catalogue, component, finding

DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
ASKED = LocalModels(
    server="http://127.0.0.1:11434", context_tokens=8192, timeout_seconds=180.0,
    temperature=0, seed=11, think=False, order_check=True, escalation_model="gemma4:latest",
    ollama_version=OllamaVersion("0.34.3"),
    models=(
        ModelDigest("qwen2.5:7b", MEMBER_ROLE, DIGEST),
        UnknownDigest("gemma4:latest", ESCALATION_ROLE, "the server lists no model named it"),
    ),
)
SAID = "models: qwen2.5:7b 845dbda0ea48, gemma4:latest (escalation) digest unknown; Ollama 0.34.3"


def pages(local: LocalModels) -> tuple[str, str]:
    """Render one council record on the terminal, and the whole web page it lands on."""
    outcome = council_ran(**DISSENTING)
    raised = (finding(component(), advisory_id=outcome.advisory_id),)
    report = build_report(replace(PROVENANCE, local_models=local), catalogue(component()), raised,
                          {}, (outcome,))
    return council_block(report), as_html(report)


def test_each_model_is_named_with_the_start_of_its_digest_and_the_server_s_version():
    assert models_named(ASKED) == [SAID]
    assert UNKNOWN_DIGEST in SAID


def test_both_pages_carry_the_models_line_the_redesign_puts_in_the_header_meta():
    # The terminal keeps it beside the council; the web page moves it to the
    # masthead meta, where the run's other provenance is.
    assert all(SAID in page for page in pages(ASKED))


def test_a_version_the_server_did_not_give_is_said_to_be_unknown():
    unknown = replace(ASKED, ollama_version=UnknownOllamaVersion("could not be reached"))
    assert models_named(unknown)[0].endswith(f"; {UNKNOWN_VERSION}")


def test_a_record_that_does_not_say_how_the_models_were_asked_names_none():
    assert models_named(None) == []


def test_a_server_elsewhere_is_named_by_its_host_on_both_pages():
    elsewhere = replace(ASKED, server="http://10.205.4.15:11434", remote_host="10.205.4.15")
    said = f"{SAID} on 10.205.4.15, not this machine"
    assert models_named(elsewhere) == [said]
    assert all(said in page for page in pages(elsewhere))


def test_this_machine_goes_unsaid_so_a_local_run_s_line_is_as_it_was():
    assert models_named(ASKED) == [SAID] and ASKED.remote_host == ""
    assert all(" on " not in line for line in models_named(ASKED))
