"""The two documents the page renders come back exactly as the audit wrote them.

`findings.json` and `surfaces.json` are contracts with their own
`schema_version`, described in `docs/SCHEMAS.md`. Reshaping either one for a
browser would invent an undocumented artifact that drifts from the ones the rest
of the project reads, so the wrapper returns them untouched -- and "untouched"
is asserted here by re-serialising what came back and comparing it to the bytes
on disk, not by spot-checking a field.

The documents are written by this test rather than produced by an audit. That is
deliberate and it is weaker: nothing here is a document the auditor really
built, so a defect that only shows on a real one is not caught by this file.
`test_api_audit.py` closes that half by running the audit and comparing the
reply to what landed on disk. What this file adds is the shapes an audit cannot
easily be made to produce on demand -- a missing artifact, a directory that does
not exist, an unexpected key.

Nothing here imports fastapi, so it runs on a clean checkout with no web extra.
"""

import dataclasses
import json
from pathlib import Path

from artifacts.coverage import coverage
from artifacts.finding import SCHEMA_VERSION as FINDINGS_SCHEMA_VERSION
from artifacts.finding import STATIC, Finding
from artifacts.findings_document import MODEL_DISABLED, build_findings_document, model_run
from artifacts.names import FINDINGS_NAME, SURFACES_NAME
from artifacts.surface import SCHEMA_VERSION as SURFACES_SCHEMA_VERSION
from artifacts.surface import Surface, surfaces_to_json
from artifacts_read import RENDERED, read_documents

# The two short keys the page reads the reply under.
FINDINGS_KEY = "findings"
SURFACES_KEY = "surfaces"

# One surface and one finding over it, built by the record types themselves and
# serialised by the real document builders. Hand-written dicts stood here until
# one of them carried an `evidence` object that `Finding` has never declared,
# and `FindingList.jsx` was written to render it -- a field invented by a test
# fixture, read by a page, and present in nothing the auditor writes. A document
# assembled by `artifacts/` cannot invent one.
SURFACE = Surface(kind="TOOL_CALL", name="ShellTool", file="agent.py", line=7,
                  language="python", detail="ShellTool()")
FINDING = Finding(owasp_id="LLM06", rule_id="permissions",
                  title="A shell tool the agent can call unchecked",
                  detection=STATIC, surface_id=SURFACE.id, surface_kind=SURFACE.kind,
                  surface_name=SURFACE.name, file=SURFACE.file, line=SURFACE.line,
                  narrative="Treat the value as data rather than as instruction.")

# Both documents are nested and mixed-typed -- `coverage` and `model_run` are
# objects, `findings` a list of records, `line` an integer -- so a wrapper that
# flattened or re-keyed anything would fail the byte comparisons below.
FINDINGS_DOCUMENT = build_findings_document(
    [FINDING], [], coverage(1, ["permissions", "taint"]), model_run(MODEL_DISABLED))
SURFACES_DOCUMENT = json.loads(surfaces_to_json([SURFACE], []))

# How the file is written, and the one shape the round trip is compared in. Both
# ends use it, so the comparison is about content and not about indentation.
JSON_STYLE = {"indent": 2, "sort_keys": True}

# An artifact the wrapper is not asked for. Present in a real run and rendered
# by nothing, so it must not appear in the reply.
UNREAD_ARTIFACT = "report.md"

# A key no schema declares, to prove the reader validates nothing away.
UNEXPECTED_KEY = "an_unexpected_key"


def write_documents(tmp_path: Path, findings: dict | None = FINDINGS_DOCUMENT,
                    surfaces: dict | None = SURFACES_DOCUMENT) -> Path:
    """Write an app's artifact directory holding either, both or neither document."""
    app_artifacts = tmp_path / "artifacts" / "demo-app"
    app_artifacts.mkdir(parents=True)
    for name, document in ((FINDINGS_NAME, findings), (SURFACES_NAME, surfaces)):
        if document is not None:
            (app_artifacts / name).write_text(json.dumps(document, **JSON_STYLE),
                                              encoding="utf-8")
    return app_artifacts


def test_the_written_finding_carries_only_fields_the_contract_declares() -> None:
    """The fixture's own guard: an invented field here is how the page came to render one."""
    declared = {field.name for field in dataclasses.fields(Finding)} | {"finding_id"}
    assert set(FINDINGS_DOCUMENT["findings"][0]) == declared


def test_the_two_names_read_are_the_ones_the_artifact_module_owns() -> None:
    """The names come from `artifacts/names.py`, so a rename there is not a second spelling."""
    assert dict(RENDERED) == {FINDINGS_KEY: FINDINGS_NAME, SURFACES_KEY: SURFACES_NAME}


def test_both_documents_are_returned_under_their_short_keys(tmp_path) -> None:
    """The reply holds exactly two keys, whatever else the directory contains."""
    result = read_documents(write_documents(tmp_path))
    assert set(result) == {FINDINGS_KEY, SURFACES_KEY}


def test_the_findings_document_is_what_the_file_holds(tmp_path) -> None:
    """Parsed here independently and compared, rather than trusted from the wrapper."""
    app_artifacts = write_documents(tmp_path)
    on_disk = json.loads((app_artifacts / FINDINGS_NAME).read_text(encoding="utf-8"))
    assert read_documents(app_artifacts)[FINDINGS_KEY] == on_disk


def test_the_surfaces_document_is_what_the_file_holds(tmp_path) -> None:
    """The same for the second artifact, so neither is right only by the other's accident."""
    app_artifacts = write_documents(tmp_path)
    on_disk = json.loads((app_artifacts / SURFACES_NAME).read_text(encoding="utf-8"))
    assert read_documents(app_artifacts)[SURFACES_KEY] == on_disk


def test_the_findings_document_re_serialises_to_the_bytes_on_disk(tmp_path) -> None:
    """The strongest form of "unmodified": every key, every nesting level, nothing added."""
    app_artifacts = write_documents(tmp_path)
    returned = read_documents(app_artifacts)[FINDINGS_KEY]
    assert json.dumps(returned, **JSON_STYLE) == (
        app_artifacts / FINDINGS_NAME).read_text(encoding="utf-8")


def test_the_surfaces_document_re_serialises_to_the_bytes_on_disk(tmp_path) -> None:
    """The same byte comparison for the second artifact."""
    app_artifacts = write_documents(tmp_path)
    returned = read_documents(app_artifacts)[SURFACES_KEY]
    assert json.dumps(returned, **JSON_STYLE) == (
        app_artifacts / SURFACES_NAME).read_text(encoding="utf-8")


def test_the_schema_version_of_each_document_survives(tmp_path) -> None:
    """The field a reshaping would drop first, named on both documents rather than implied."""
    result = read_documents(write_documents(tmp_path))
    assert result[FINDINGS_KEY]["schema_version"] == FINDINGS_SCHEMA_VERSION
    assert result[SURFACES_KEY]["schema_version"] == SURFACES_SCHEMA_VERSION


def test_a_key_no_schema_declares_is_returned_too(tmp_path) -> None:
    """The reader validates nothing away: the page renders whatever the audit wrote."""
    document = {**FINDINGS_DOCUMENT, UNEXPECTED_KEY: ["kept"]}
    app_artifacts = write_documents(tmp_path, findings=document)
    assert read_documents(app_artifacts)[FINDINGS_KEY][UNEXPECTED_KEY] == ["kept"]


def test_a_missing_findings_file_is_none_rather_than_an_error(tmp_path) -> None:
    """An audit that could not build one still produced the other, and the page says so."""
    result = read_documents(write_documents(tmp_path, findings=None))
    assert result[FINDINGS_KEY] is None
    assert result[SURFACES_KEY] == SURFACES_DOCUMENT


def test_a_missing_surfaces_file_is_none_rather_than_an_error(tmp_path) -> None:
    """The same in the other direction, so neither None is the other's side effect."""
    result = read_documents(write_documents(tmp_path, surfaces=None))
    assert result[SURFACES_KEY] is None
    assert result[FINDINGS_KEY] == FINDINGS_DOCUMENT


def test_a_directory_that_does_not_exist_yields_two_nones(tmp_path) -> None:
    """The failure path: a run that wrote nothing at all is answered, not raised on."""
    result = read_documents(tmp_path / "never-written")
    assert result == {FINDINGS_KEY: None, SURFACES_KEY: None}


def test_an_artifact_the_page_does_not_render_is_not_read(tmp_path) -> None:
    """Two of eleven artifacts, so a report beside them stays out of the reply."""
    app_artifacts = write_documents(tmp_path)
    (app_artifacts / UNREAD_ARTIFACT).write_text("# Report\n", encoding="utf-8")
    assert set(read_documents(app_artifacts)) == {FINDINGS_KEY, SURFACES_KEY}
