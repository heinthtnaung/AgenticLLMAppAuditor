"""The real vexctl, authoring a real document, read back and applied to a real SARIF.

The counterpart to test_emit_vex_command.py: that file checks which commands
run, this one checks what they produce. Skipped when vexctl is absent, the way
the SARIF export tests skip, because the tool is a prerequisite and
not a dependency.

The filter test is the semantic check and the reason the status matters.
`affected` is not a suppression -- it says a result stands -- so a document
full of them must leave a SARIF report exactly as it was. A tool that dropped
results here would mean this project had published the opposite of its claim.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from advisory_fixtures import ADVISORY_PURL, advisory_document, advisory_finding
from artifacts.sarif import DRIVER_NAME, sarif_to_json, to_sarif
from artifacts.vex import AFFECTED
from emit_vex import PROGRAM_NAME, emit
from vex_fixtures import PRODUCT, app_directory, reaching

SECOND_ADVISORY = "CVE-2024-0002"
TIMEOUT_SECONDS = 60

OPENVEX_CONTEXT = "openvex"


def require_vexctl() -> None:
    """Skip rather than fail when the tool this document's format belongs to is absent."""
    if shutil.which(PROGRAM_NAME) is None:
        pytest.skip(f"{PROGRAM_NAME} is not installed")


def two_statement_document() -> dict:
    """Findings implying two claims about one component, reached from two surfaces."""
    return advisory_document(advisory_finding(),
                             reaching("SearchTool", "app/tools.py", 40,
                                      advisory_id=SECOND_ADVISORY))


def emit_document(tmp_path: Path, name: str = "an-audited-app") -> tuple[Path, dict]:
    """Emit one document with the real tool and return its path and its parsed body."""
    app_dir = app_directory(tmp_path, two_statement_document(), name)
    written = emit(app_dir, PRODUCT)
    return written, json.loads(written.read_text(encoding="utf-8"))


def test_the_emitted_document_is_openvex_authored_by_this_project(tmp_path) -> None:
    """The two facts a reader checks first: what format it is and who is claiming it."""
    require_vexctl()
    _, document = emit_document(tmp_path)
    assert OPENVEX_CONTEXT in document["@context"]
    assert document["author"] == DRIVER_NAME


def test_every_emitted_statement_is_affected(tmp_path) -> None:
    """Through the real tool, not just the pure builder: nothing rewrites the status."""
    require_vexctl()
    _, document = emit_document(tmp_path)
    assert len(document["statements"]) == 2
    assert {one["status"] for one in document["statements"]} == {AFFECTED}


def test_the_app_is_the_product_and_the_component_a_subcomponent(tmp_path) -> None:
    """The whole difference from restating the advisory: this app is what is assessed."""
    require_vexctl()
    _, document = emit_document(tmp_path)
    for statement in document["statements"]:
        product = statement["products"][0]
        assert product["@id"] == PRODUCT
        assert [one["@id"] for one in product["subcomponents"]] == [ADVISORY_PURL]


def test_the_statements_carry_the_surfaces_that_reached_the_component(tmp_path) -> None:
    """The evidence survives the tool: without it the document only restates the database."""
    require_vexctl()
    _, document = emit_document(tmp_path)
    notes = sorted(one["status_notes"] for one in document["statements"])
    assert notes == ["Reached by SearchTool at app/tools.py:40",
                     "Reached by ShellTool at app/agent.py:12"]


def test_two_emissions_of_one_audit_are_byte_identical(tmp_path) -> None:
    """The instant is pinned to the advisory data, so a second run is not a second document."""
    require_vexctl()
    first, _ = emit_document(tmp_path, "first")
    second, _ = emit_document(tmp_path, "second")
    assert first.read_bytes() == second.read_bytes()


# The status this project may never claim, and its justification. Spelled out
# because the ban in test_vexctl_launch.py scans `src/` only -- a test may name
# the counter-case the auditor itself must never state.
SUPPRESSING_STATUS = "not_affected"
SUPPRESSING_JUSTIFICATION = "vulnerable_code_not_in_execute_path"


def test_the_document_suppresses_nothing_in_a_sarif_report(tmp_path) -> None:
    """`affected` is a claim that a result stands, so every one must survive the filter."""
    require_vexctl()
    document, _ = emit_document(tmp_path)
    sarif = to_sarif(two_statement_document())
    report = tmp_path / "findings.sarif.json"
    report.write_text(sarif_to_json(sarif), encoding="utf-8")
    filtered = subprocess.run([PROGRAM_NAME, "filter", str(report), str(document)],
                              capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    assert filtered.returncode == 0, filtered.stderr
    # Compared outright, not by length: a matching count would also pass if the
    # tool had dropped one result and invented another.
    read_back = json.loads(filtered.stdout)["runs"][0]["results"]
    assert read_back == sarif["runs"][0]["results"]


def test_a_suppressing_status_really_would_drop_them(tmp_path) -> None:
    """The check above is only worth having if the filter reads the status at all.

    So flip this project's own document to a suppressing status and watch the
    results vanish. Written here rather than in `src/`, which is where
    `test_vexctl_launch.py` bans the word: a test may author the counter-case
    the auditor itself must never claim.
    """
    require_vexctl()
    document, _ = emit_document(tmp_path)
    flipped = json.loads(document.read_text(encoding="utf-8"))
    for statement in flipped["statements"]:
        statement["status"] = SUPPRESSING_STATUS
        statement["justification"] = SUPPRESSING_JUSTIFICATION
        del statement["action_statement"]
    suppressor = tmp_path / "flipped.openvex.json"
    suppressor.write_text(json.dumps(flipped), encoding="utf-8")

    sarif = to_sarif(two_statement_document())
    report = tmp_path / "flipped.sarif.json"
    report.write_text(sarif_to_json(sarif), encoding="utf-8")
    filtered = subprocess.run([PROGRAM_NAME, "filter", str(report), str(suppressor)],
                              capture_output=True, text=True, timeout=TIMEOUT_SECONDS)

    assert filtered.returncode == 0, filtered.stderr
    assert json.loads(filtered.stdout)["runs"][0]["results"] == [], \
        "vexctl ignored the status, so the test above proves nothing"
