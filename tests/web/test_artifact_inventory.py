"""`ALL_NAMES` is every file a run can leave on disk, held against the writers.

`src/artifacts/names.py` keeps one spelling of each artifact name -- the VEX
document's and the two export suffixes moved there out of `emit_vex.py` and
`export_reports.py` -- and `ALL_NAMES` collects all sixteen. The download
endpoint takes that tuple as its allowlist, so a name the writers produce and
this tuple omits is a file a user cannot download while the page offers "every
artifact". That is the defect this file exists to catch, which is why nothing
below transcribes the names it checks.

It lives in this folder because that is the reader the inventory was widened
for, but it imports no wrapper module and asserts nothing about the endpoint:
what a request is answered with is the wrapper's own tests' subject. This one
is about the writers.

Which half is observed and which derived, because the two are not equally strong:

- **Observed.** The audit's eleven come from a real `audit_run.audit` over a tree
  written into `tmp_path`, listed off disk afterwards. A documents dict spelled
  out by this test could not catch a writer producing an unlisted name: the dict
  would be keyed by the very names under test, and would agree with itself.
- **Observed.** The four exports come from a real `export_reports.export_all`
  over that same directory. Two files or four: the PDF half needs fpdf2 and a
  Unicode font on the machine, neither of which this suite requires, so it is
  asserted when `export_reports` says this machine can render one and derived
  from `PDF_SUFFIX` when it cannot.
- **Derived, and it cannot be otherwise.** `vexctl` authors the VEX document,
  and it is an external binary this suite does not require and must not run. So
  what is checked is the name `emit_vex` would write -- its own constant, which
  is now this module's.

Syft, Trivy, the model and the knowledge base are replaced at their seams (see
`cli_helpers`), so nothing here needs a tool, a server or a socket. The tree is
synthetic and so weaker than a real repository: nothing in it is oversized,
non-UTF-8, malformed or shaped in a way nobody foresaw.
"""

from pathlib import Path

import pytest

from artifacts.names import (
    ALL_NAMES, HTML_SUFFIX, PDF_SUFFIX, REMEDIATION_REPORT_NAME, REPORT_NAME,
    VEX_NAME)
from cli_helpers import stub_knowledge, stub_model, stub_syft
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from mixed_app_fixtures import write_mixed_app
import audit_run
import emit_vex
import export_reports

# How many names the audit path owns. "Eleven" is a number this repo quotes in
# `names.py`, in `docs/TODO.md`, in the frontend's dashboard and in several
# tests, so it is asserted against a real run rather than left to agree by habit.
AUDIT_NAME_COUNT = 11

# The eleven, the VEX document, and the two reports rendered in two formats.
ALL_NAME_COUNT = 16

# What the audited tree declares, so the run really builds a bill of materials
# and writes eleven files instead of the eight a manifest-less app leaves.
DECLARED_PACKAGE = "langchain==0.3.25\n"
STUBBED_SCAN = {"components": [{"type": "library", "name": "langchain",
                                "version": "0.3.25"}]}


def exported_as(report_name: str, suffix: str) -> str:
    """What one Markdown report is called once it is rendered with that suffix."""
    return Path(report_name).with_suffix(suffix).name


# The four exports, derived here from the two report names and the two suffix
# constants. `names.py` derives them with `str.replace`; two derivations of the
# same four names disagree on a typo, where one would agree with itself.
HTML_EXPORTS = frozenset({exported_as(REPORT_NAME, HTML_SUFFIX),
                          exported_as(REMEDIATION_REPORT_NAME, HTML_SUFFIX)})
PDF_EXPORTS = frozenset({exported_as(REPORT_NAME, PDF_SUFFIX),
                         exported_as(REMEDIATION_REPORT_NAME, PDF_SUFFIX)})


def audited_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Audit a tree written here, and return the directory the run wrote into."""
    repo = write_mixed_app(tmp_path)
    (repo / PYPI_MANIFEST).write_text(DECLARED_PACKAGE, encoding="utf-8")
    stub_syft(monkeypatch, STUBBED_SCAN)
    stub_model(monkeypatch)
    stub_knowledge(monkeypatch)
    written = audit_run.audit(repo, tmp_path / "artifacts")["artifacts"]
    assert written.is_dir(), "the audit wrote where its result says it did"
    return written


def files_in(directory: Path) -> set[str]:
    """The names of the files sitting in one directory."""
    return {path.name for path in directory.iterdir()}


def pdf_can_be_rendered() -> bool:
    """Say whether this machine has what the export stage needs to write a PDF."""
    return export_reports.pdf_reason(export_reports.font_directory()) == ""


# --- the tuple itself ---------------------------------------------------------

def test_the_inventory_lists_sixteen_names_with_no_duplicate() -> None:
    """A repeated name would make an allowlist look longer than the set it allows."""
    assert len(ALL_NAMES) == ALL_NAME_COUNT
    assert len(set(ALL_NAMES)) == ALL_NAME_COUNT


def test_the_vex_name_is_the_one_the_emitter_would_write() -> None:
    """One spelling, in the twelfth place: the emitter reads it here, not its own copy."""
    assert emit_vex.DOCUMENT_NAME == VEX_NAME
    assert ALL_NAMES[AUDIT_NAME_COUNT] == VEX_NAME


def test_the_last_four_names_are_the_two_reports_rendered_twice() -> None:
    """Derived from the report names and both suffix constants, not from the tuple."""
    assert set(ALL_NAMES[AUDIT_NAME_COUNT + 1:]) == HTML_EXPORTS | PDF_EXPORTS


# --- what the writers really produce ------------------------------------------

def test_the_audit_writes_exactly_eleven_files(monkeypatch, tmp_path) -> None:
    """Counted off disk rather than trusted, since the number is quoted all over the repo."""
    assert len(files_in(audited_artifacts(monkeypatch, tmp_path))) == AUDIT_NAME_COUNT


def test_the_first_eleven_names_are_what_the_audit_really_wrote(monkeypatch,
                                                                tmp_path) -> None:
    """Observed off disk, so a twelfth artifact fails here until it is listed too."""
    written = files_in(audited_artifacts(monkeypatch, tmp_path))
    assert written == set(ALL_NAMES[:AUDIT_NAME_COUNT])


def test_every_file_the_export_stage_writes_is_listed(monkeypatch, tmp_path) -> None:
    """The exports run for real over the audited directory, PDF where one can be made."""
    exported, _reason = export_reports.export_all(audited_artifacts(monkeypatch, tmp_path))
    names = {path.name for path in exported}
    expected = HTML_EXPORTS | (PDF_EXPORTS if pdf_can_be_rendered() else frozenset())
    assert names == expected
    assert names <= set(ALL_NAMES)


def test_no_name_a_writer_produces_is_missing_from_the_inventory(monkeypatch,
                                                                 tmp_path) -> None:
    """The whole claim as one equality: every writer's output, unioned, is the inventory.

    The PDF pair is added from the suffix constant rather than observed, so this
    holds on a machine with no renderer and no font; everything else in the
    union came off disk or out of the emitter's own constant.
    """
    written = audited_artifacts(monkeypatch, tmp_path)
    audit_files = files_in(written)
    exported, _reason = export_reports.export_all(written)
    produced = (audit_files | {path.name for path in exported}
                | {emit_vex.DOCUMENT_NAME} | PDF_EXPORTS)
    assert produced == set(ALL_NAMES)
