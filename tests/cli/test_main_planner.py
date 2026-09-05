"""`planner.json` on disk: written by every run, and read by nothing.

That last part is why this file exists. No reader would break if the artifact
were wrong, missing or malformed (`docs/SCHEMAS.md`), so the only thing holding
it to its schema is a test that opens the file the CLI wrote.

Three claims, in order of what a reader loses without them: the file is written
at all; what it says about the order agrees with what `findings.json` says the
run did; and its `status`/`identifier` pair is honest, both on a default run
that offered no model and under `--semantic-probe`, which offers one.

The app is written by the test, Syft is stubbed, and the model under the flag
is `cli_helpers`' stand-in -- nothing here opens a socket or needs a tool
installed.
"""

import json
from pathlib import Path

import model_client
from artifacts.findings_document import MODEL_DISABLED, MODEL_USED
from artifacts.planner_document import DOCUMENT_FIELDS, build_planner_document
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.known_advisory import CHECK_NAME as ADVISORY_CHECK
from checks.output_handling import CHECK_NAME as QUERY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from cli_helpers import read_artifact, run_cli, stub_syft
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from outputs import FINDINGS_NAME, PLANNER_NAME

APP_NAME = "planned-app"

# One agent built with no callback handler, importing a package the manifest
# declares. Enough for five of the six graph checks to have a subject; the
# advisory check has none, because `stub_syft` turns Trivy off.
APP_SOURCE = """from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
"""

STUB_GENERATOR_OUTPUT = {
    "components": [{"type": "library", "name": "langchain", "version": "0.3.25"}],
}

# What this app plans, in the order `run_checks` names them. Written out so the
# file's contents are asserted rather than compared with themselves.
PLANNED_ORDER = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK,
                 QUERY_CHECK, AUDITABILITY_CHECK]


def write_app(tmp_path: Path) -> Path:
    """Write the app whose checks the planner orders, and declare its one package."""
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / "main.py").write_text(APP_SOURCE, encoding="utf-8")
    (repo / PYPI_MANIFEST).write_text("langchain==0.3.25\n", encoding="utf-8")
    return repo


def audit(monkeypatch, tmp_path: Path, flags: tuple[str, ...] = ()) -> Path:
    """Run the CLI over the written app and return the directory it wrote into."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts",
                   flags=flags) == 0
    return tmp_path / "artifacts"


# --- the file is written ----------------------------------------------------

def test_the_run_writes_planner_json_beside_the_findings(monkeypatch, tmp_path) -> None:
    """An eleventh artifact: without this test nothing at all would notice its absence."""
    artifacts = audit(monkeypatch, tmp_path)
    assert (artifacts / APP_NAME / PLANNER_NAME).is_file()


def test_the_written_planner_carries_every_documented_field(monkeypatch, tmp_path) -> None:
    """`docs/SCHEMAS.md` promises five fields, and no reader is there to miss a sixth."""
    document = read_artifact(audit(monkeypatch, tmp_path), APP_NAME, PLANNER_NAME)
    assert sorted(document) == sorted(DOCUMENT_FIELDS)


def test_the_written_planner_would_still_be_accepted_by_its_builder(
        monkeypatch, tmp_path) -> None:
    """Rebuilt from the file: a document the builder would refuse must not be on disk."""
    document = read_artifact(audit(monkeypatch, tmp_path), APP_NAME, PLANNER_NAME)
    assert build_planner_document(document, document["findings_schema_version"]) == document


def test_the_written_bytes_are_sorted_indented_and_end_in_one_newline(
        monkeypatch, tmp_path) -> None:
    """The same on-disk form as every other artifact, asserted where it is actually written."""
    text = (audit(monkeypatch, tmp_path) / APP_NAME / PLANNER_NAME).read_text(encoding="utf-8")
    assert list(json.loads(text)) == sorted(DOCUMENT_FIELDS)
    assert '\n  "order": [' in text
    assert text.endswith("}\n") and not text.endswith("\n\n")


# --- what it says about the run ---------------------------------------------

def test_the_written_order_is_the_checks_this_app_plans(monkeypatch, tmp_path) -> None:
    """The order is the one fact the file records, so it is asserted name by name."""
    document = read_artifact(audit(monkeypatch, tmp_path), APP_NAME, PLANNER_NAME)
    assert document["order"] == PLANNED_ORDER


def test_the_advisory_check_is_absent_because_no_advisory_data_was_read(
        monkeypatch, tmp_path) -> None:
    """Guard: the order holds the checks that had a subject, not every check that exists."""
    document = read_artifact(audit(monkeypatch, tmp_path), APP_NAME, PLANNER_NAME)
    assert ADVISORY_CHECK not in document["order"]


def test_the_order_and_the_findings_coverage_name_the_same_checks(
        monkeypatch, tmp_path) -> None:
    """A planner that ordered checks the audit never ran would be a record of nothing.

    Asserted on a default run only, and deliberately not generalised: an edge
    check runs outside the graph and so is never in the plan, which is why
    `--semantic-probe` on an app with a template puts a name in `checks_run`
    that this order will not hold.
    """
    artifacts = audit(monkeypatch, tmp_path)
    planner_document = read_artifact(artifacts, APP_NAME, PLANNER_NAME)
    findings = read_artifact(artifacts, APP_NAME, FINDINGS_NAME)
    assert sorted(planner_document["order"]) == findings["coverage"]["checks_run"]


def test_the_planner_records_the_findings_schema_it_ordered_the_checks_for(
        monkeypatch, tmp_path) -> None:
    """What invalidates this file, in place of a timestamp, taken from the file beside it."""
    artifacts = audit(monkeypatch, tmp_path)
    planner_document = read_artifact(artifacts, APP_NAME, PLANNER_NAME)
    findings = read_artifact(artifacts, APP_NAME, FINDINGS_NAME)
    assert planner_document["findings_schema_version"] == findings["schema_version"]


# --- who chose the order ----------------------------------------------------

def test_a_default_run_names_no_model(monkeypatch, tmp_path) -> None:
    """No model is offered without the flag, so the order was this project's own."""
    document = read_artifact(audit(monkeypatch, tmp_path), APP_NAME, PLANNER_NAME)
    assert document["status"] == MODEL_DISABLED
    assert document["identifier"] is None


def test_the_probe_flag_records_the_model_that_was_asked_to_order_the_checks(
        monkeypatch, tmp_path) -> None:
    """`--semantic-probe` is what hands a model to the edge, planner included."""
    document = read_artifact(
        audit(monkeypatch, tmp_path, ("--semantic-probe",)), APP_NAME, PLANNER_NAME)
    assert document["status"] == MODEL_USED
    assert document["identifier"] == model_client.MODEL


def test_a_model_that_answered_with_prose_leaves_the_planned_order_alone(
        monkeypatch, tmp_path) -> None:
    """The stand-in answers advice, not JSON: no opinion is a safe answer, not a shorter run."""
    document = read_artifact(
        audit(monkeypatch, tmp_path, ("--semantic-probe",)), APP_NAME, PLANNER_NAME)
    assert document["order"] == PLANNED_ORDER
