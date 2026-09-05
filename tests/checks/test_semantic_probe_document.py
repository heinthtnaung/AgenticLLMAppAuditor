"""What the semantic probe does to findings.json, to coverage, and to the report.

The check's own answers are `test_semantic_probe.py`'s subject. This file is
about the document-level contracts they meet: the citation guard that refuses a
probe finding with no confirmed probe behind it, the coverage rule that a check
is named only when it had something to examine, and the determinism exemption,
which removes the model's prose and must not remove the model's finding.
`test_semantic_probe_provenance.py` holds the fourth, the `model_run` block.

The first test is the one `README.md` publishes -- a default audit is unchanged
by this check -- so it is a byte comparison against the code path this check was
added to, not a comment saying so.
"""

import json

from artifacts.finding import CONFIRMED, NOT_RUN, PROBE
from artifacts.findings_document import (
    MODEL_AUTHORED_FINDING_FIELD,
    findings_to_json,
    strip_model_authored,
)
from artifacts.surface import surfaces_to_json
from checks import semantic_probe
from checks.run_checks import RISK_CLASS_BY_CHECK
from report import render
from semantic_probe_fixtures import (
    Answering,
    NO_PROMPT_APP,
    PROBE_ID,
    PROMPT_APP_CHECKS_RUN,
    PROMPT_APP_FINDINGS,
    PROMPT_APP_SURFACES,
    PROMPT_LINE,
    PROMPT_SURFACE_ID,
    Refusing,
    audited,
    document_without_the_probe,
)

VULNERABLE_REPLY = "VULNERABLE\nThe {question} value lands inside the instructions."
VULNERABLE_RATIONALE = "The {question} value lands inside the instructions."
SAFE_REPLY = "SAFE\nNothing external reaches the instruction text."

# LLM01 in the 2025 OWASP list, which is the class this check reports -- and
# also the taint check's, which is why membership of `risk_classes_checked` is
# never asserted below as evidence about this probe. On any app that traces an
# untrusted value, LLM01 is claimed whether the probe ran or not, so such an
# assertion would pass over a probe that never happened.
PROBE_RISK_CLASS = semantic_probe.OWASP_ID

APP = "probe-app"


def probe_findings(document: dict) -> list[dict]:
    """The findings this check contributed to the document."""
    return [f for f in document["findings"] if f["rule_id"] == semantic_probe.CHECK_NAME]


# --- the opt-in is byte-for-byte invisible -----------------------------------

def test_a_default_audit_is_byte_identical_to_one_built_before_this_check_existed(
        tmp_path) -> None:
    """The guarantee `README.md` publishes, compared as bytes rather than described.

    `document_without_the_probe` is `build_findings` with the probe lines
    deleted, so this compares today's default audit against the code path the
    check was added to. Anything the check touched unconditionally -- a coverage
    field, an extra probe, a changed model_run -- shows up here as a diff.
    """
    document, surfaces = audited(tmp_path, ask=None, probe_model=None)
    before = document_without_the_probe(tmp_path / APP, surfaces)
    assert findings_to_json(document).encode("utf-8") == findings_to_json(before).encode("utf-8")


def test_that_byte_comparison_is_made_over_a_document_with_findings_in_it(tmp_path) -> None:
    """Guard: two empty documents are byte-identical too, and would prove nothing.

    Named literals, so an audit that quietly stopped producing anything cannot
    keep the comparison above green.
    """
    document, surfaces = audited(tmp_path, ask=None, probe_model=None)
    assert len(surfaces) == PROMPT_APP_SURFACES
    assert document["finding_count"] == PROMPT_APP_FINDINGS
    assert len(document["coverage"]["checks_run"]) == PROMPT_APP_CHECKS_RUN
    assert PROMPT_SURFACE_ID in [s.id for s in surfaces]


def test_a_default_audit_leaves_the_probe_out_of_the_record_entirely(tmp_path) -> None:
    """No probe, no finding, no name in coverage: the check is opted into, never defaulted on."""
    document, _surfaces = audited(tmp_path, ask=None, probe_model=None)
    assert document["probes"] == []
    assert probe_findings(document) == []
    assert semantic_probe.CHECK_NAME not in document["coverage"]["checks_run"]


# --- a confirmed verdict reaches the artifact --------------------------------

def test_a_confirmed_verdict_builds_a_document_that_satisfies_the_citation_guard(
        tmp_path) -> None:
    """`_check_probe_citations` refuses a probe finding citing nothing confirmed, and lets this by.

    That the document builds at all is the assertion: the guard runs inside
    `build_findings_document`, so a probe id that did not match would raise here
    rather than produce a wrong artifact.
    """
    document, _surfaces = audited(tmp_path, Answering(VULNERABLE_REPLY))
    finding = probe_findings(document)[0]
    confirmed = [p["probe_id"] for p in document["probes"] if p["outcome"] == CONFIRMED]
    assert finding["detection"] == PROBE
    assert finding["probe_id"] == PROBE_ID
    assert confirmed == [PROBE_ID]


def test_the_confirmed_finding_is_anchored_on_the_template_it_was_asked_about(tmp_path) -> None:
    """A reader has to be able to open the file at the line the model judged."""
    document, _surfaces = audited(tmp_path, Answering(VULNERABLE_REPLY))
    finding = probe_findings(document)[0]
    assert (finding["file"], finding["line"]) == ("agent.py", PROMPT_LINE)
    assert finding["surface_id"] == PROMPT_SURFACE_ID


def test_the_probe_adds_exactly_one_finding_to_the_static_ones(tmp_path) -> None:
    """The static checks are untouched: the probe adds a finding, it replaces none."""
    document, _surfaces = audited(tmp_path, Answering(VULNERABLE_REPLY))
    assert document["finding_count"] == PROMPT_APP_FINDINGS + 1
    assert len(probe_findings(document)) == 1


def test_the_report_renders_the_probe_line_under_the_finding(tmp_path) -> None:
    """`report._probe_lines` publishes the evidence, so the verdict is never a bare claim."""
    document, surfaces = audited(tmp_path, Answering(VULNERABLE_REPLY))
    text = render(APP, document, json.loads(surfaces_to_json(surfaces, [])))
    assert f"- **Probe**: `{PROBE_ID}` — {VULNERABLE_RATIONALE}" in text
    assert f"- **Reached by**: `{semantic_probe.CHECK_NAME}`, {PROBE} analysis" in text


def test_the_report_names_the_template_line_beside_that_probe(tmp_path) -> None:
    """Guard: the probe line above could render under a finding pointing anywhere."""
    document, surfaces = audited(tmp_path, Answering(VULNERABLE_REPLY))
    text = render(APP, document, json.loads(surfaces_to_json(surfaces, [])))
    assert f"- **Where**: `agent.py:{PROMPT_LINE}`" in text
    assert semantic_probe.TITLE in text


# --- coverage names the check only when it looked ----------------------------

def test_the_check_is_named_in_coverage_when_it_produced_a_probe(tmp_path) -> None:
    """It had a template and a model, so it looked, and coverage says so."""
    coverage = audited(tmp_path, Answering(VULNERABLE_REPLY))[0]["coverage"]
    assert semantic_probe.CHECK_NAME in coverage["checks_run"]


def test_the_check_declares_the_risk_class_it_reports(tmp_path) -> None:
    """A check named in `checks_run` must have a class behind it, or coverage cannot be built."""
    coverage = audited(tmp_path, Answering(VULNERABLE_REPLY))[0]["coverage"]
    assert RISK_CLASS_BY_CHECK[semantic_probe.CHECK_NAME] == PROBE_RISK_CLASS
    assert PROBE_RISK_CLASS in coverage["risk_classes_checked"]


def test_a_refuted_verdict_still_counts_as_the_check_having_looked(tmp_path) -> None:
    """"Looked and cleared it" is a result, and this project reports it as one."""
    document, _surfaces = audited(tmp_path, Answering(SAFE_REPLY))
    assert probe_findings(document) == []
    assert semantic_probe.CHECK_NAME in document["coverage"]["checks_run"]
    assert document["probe_count"] == 1


def test_an_app_with_no_prompt_template_leaves_the_check_out_of_coverage(tmp_path) -> None:
    """A model was offered and there was nothing to ask about, so nothing is claimed.

    Naming it here would read as "the templates were examined and cleared" on an
    app that has none, which is the misreading this project's absence rule exists
    to prevent.
    """
    document, surfaces = audited(tmp_path, Answering(VULNERABLE_REPLY), NO_PROMPT_APP)
    assert surfaces, "the app must still yield surfaces, or this proves nothing"
    assert document["probes"] == []
    assert semantic_probe.CHECK_NAME not in document["coverage"]["checks_run"]


def test_a_run_whose_every_call_was_refused_leaves_the_check_out_of_coverage(tmp_path) -> None:
    """The one instrument this check has was unreachable, so it did not look.

    `SCHEMAS.md` defines a name in `checks_run` as "this check had something to
    examine", and the Phase 4 scorer turns an absence into
    `no_check_for_risk_class`. Naming the probe on a run where the server
    refused every connection would report the templates as examined and silent
    -- an ordinary miss -- when nothing read them at all.
    """
    document, _surfaces = audited(tmp_path, Refusing(RuntimeError("connection refused")))
    assert [p["outcome"] for p in document["probes"]] == [NOT_RUN]
    assert semantic_probe.CHECK_NAME not in document["coverage"]["checks_run"]


def test_that_absence_is_measured_on_an_app_that_really_holds_a_template(tmp_path) -> None:
    """Guard: an app with nothing to probe is absent from coverage for a different reason."""
    document, _surfaces = audited(tmp_path, Refusing(RuntimeError("connection refused")))
    assert document["probe_count"] == 1
    assert document["probes"][0]["subject_id"] == PROMPT_SURFACE_ID


# --- the determinism exemption ------------------------------------------------

def test_stripping_the_model_authored_fields_keeps_the_probe_finding(tmp_path) -> None:
    """A verdict is evidence, and evidence stays inside the byte-compared projection.

    `SCHEMAS.md` exempts exactly two fields from `findings.json`'s determinism
    rule -- `model_run.ranking` and each finding's `narrative` -- and a probe
    finding is neither. So this is the visible consequence of running
    `--semantic-probe`, spelled out here rather than left to be discovered: the
    finding a model decided on is compared like any other, and two runs whose
    model answered differently differ in the artifact. Silently widening the
    exemption to cover it would hide that instead of stating it.
    """
    document, _surfaces = audited(tmp_path, Answering(VULNERABLE_REPLY))
    kept = probe_findings(strip_model_authored(document))
    assert len(kept) == 1
    assert kept[0]["probe_id"] == PROBE_ID
    assert (kept[0]["file"], kept[0]["line"]) == ("agent.py", PROMPT_LINE)
    assert kept[0]["title"] == semantic_probe.TITLE


def test_stripping_takes_only_the_prose_from_a_probe_finding(tmp_path) -> None:
    """The one field that goes is the one the schema names, and the probes are untouched."""
    document, _surfaces = audited(tmp_path, Answering(VULNERABLE_REPLY))
    stripped = strip_model_authored(document)
    before = probe_findings(document)[0]
    assert set(probe_findings(stripped)[0]) == set(before) - {MODEL_AUTHORED_FINDING_FIELD}
    assert stripped["probes"] == document["probes"]
    assert stripped["finding_count"] == document["finding_count"]
