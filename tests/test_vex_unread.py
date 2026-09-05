"""Nothing under src/ reads vex/, and the manifest says why it is empty.

A different invariant from `test_scorer_boundary.py`, which is why it lives
apart. That file's thesis is that the answer key flows one way, and its
`SCORED_TREES` covers only the five trees that make up the tool -- not
`src/deps/`, where the planned VEX reader would live, nor `main.py` or
`outputs.py`. An assertion added there would have checked those directories and passed while
`src/deps/vex_reader.py` quietly read the folder.

The thesis here is narrower: a half-wired reader could make a supply-chain claim
the data cannot support. No upstream VEX document exists, so a reader would have
nothing honest to say. An empty folder with a manifest claims nothing at all,
and that is the point.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from ast_scan import (
    imported_modules, module_name, modules_using_value, parse, source_files)

VEX_DIR = Path(__file__).resolve().parents[1] / "vex"
MANIFEST = VEX_DIR / "manifest.json"

# The folder's name, as a module would have to write it to open the folder.
# Matched as a *value* only (`modules_using_value`, shared with the
# forbidden-claims guard): a module may explain where VEX is written without
# that reading as touching it, and only a value can open a path or name a
# program.
#
# Matched case-sensitively, which is a decision rather than an oversight. The
# question this gate asks is who could *open the folder or run the program*,
# and lower-case `vex` is how a module spells a path (`vex/`), a filename
# (`emit_vex.py`) or a program (`vexctl`). The bare acronym in rendered prose
# -- `"## VEX (exploitability statements)"` in `report_gaps.py`, `"no VEX:
# ..."` in `pipeline.py` -- opens nothing and runs nothing. Folding case was
# tried and reverted: it widens the gate to "who says the word VEX", which puts
# four prose-only modules on the allow-list and dilutes it until nobody reads
# it, and it makes `artifacts/vex.py`'s "needs no exemption at all" untrue.
#
# The residual risk, accepted and recorded rather than hidden: a module writing
# only the acronym escapes this gate. It still cannot name a path, so
# `test_no_source_module_names_a_path_into_the_committed_folder` -- the
# invariant this file's docstring calls the real one -- holds either way.
VEX_TOKEN = "vex"

# The path the real invariant is about. Since Phase 5 this project *emits* VEX,
# so `vex` alone appears legitimately under src/ -- in `vexctl`, in
# `findings.openvex.json`, in the emitter's own module names. What must never
# appear is a path *into* the committed folder, which is what reading it needs.
UPSTREAM_PATH = "vex/"

# The modules allowed to name the token as a value, by name rather than by
# pattern. Every other module under src/ may not name it, and the mutation check
# below proves the search bites.
#
# The allow-list is a review gate, not a prohibition: the real invariant is the
# test below it, that nothing names a path *into* the committed folder, and a
# justified entry here is the intended workflow rather than a weakening. Each
# one says why it is not a reader.
#
# `artifacts/vex.py` is deliberately absent -- it decides what to claim from
# field names alone and names neither the program nor the file, so it needs no
# exemption at all.
ALLOWED_TO_NAME_VEX = frozenset({
    # The emitter, which runs `vexctl` and writes `findings.openvex.json`.
    "emit_vex.py",
    # Counts the findings carrying `advisory_id` -- the field `artifacts/vex.py`
    # branches on -- under the metric name `with_vex_evidence`. It reads no
    # document and names no path into `vex/`.
    "evaluation/evidence.py",
    # Prints that same count under the label "VEX". A label and a metric key,
    # not a path: renaming them would make `evaluation.json` stop using the
    # proposal's own term for what it measures.
    "evaluate.py",
    # Renders a `- **VEX Status**:` line saying what a finding *would become* if
    # the emitter ran, and tells the reader to run `python src/emit_vex.py`.
    # Both are rendered prose: it opens nothing, reads no document, and names
    # no path into `vex/`.
    "report.py",
})

SOURCES = ("upstream_published", "project_authored")
SNAPSHOT_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

PLANTED_READER = 'MANIFEST = "vex/manifest.json"\n'


@pytest.fixture(scope="module")
def manifest() -> dict:
    """The manifest, read from disk so `document_count: 0` is a fact and not an unread file."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_only_the_allowed_modules_name_vex_at_all() -> None:
    """An allow-list, so a new reader cannot appear unnoticed beside the emitter."""
    naming = modules_using_value(VEX_TOKEN)
    assert naming == set(ALLOWED_TO_NAME_VEX), \
        f"unlisted: {sorted(naming - set(ALLOWED_TO_NAME_VEX))}"


def test_no_source_module_names_a_path_into_the_committed_folder() -> None:
    """The real invariant, and sharper than the token: nothing opens `vex/`.

    The emitter writes its document under `artifacts/`, so even it has no
    business naming the committed input folder. A module that did would be a
    consumer, and consuming is what the two recorded blockers do not support.
    """
    assert modules_using_value(UPSTREAM_PATH) == set()


def test_the_matcher_would_notice_a_module_that_did(tmp_path: Path) -> None:
    """The check above is only worth having if it fires, so plant a reader and see.

    Without this, "no module names vex" is indistinguishable from a search that
    looked in the wrong place.
    """
    planted = tmp_path / "vex_reader.py"
    planted.write_text(PLANTED_READER, encoding="utf-8")
    assert modules_using_value(VEX_TOKEN, tmp_path) == {module_name(planted, tmp_path)}


def test_no_source_module_imports_a_vex_reader() -> None:
    """A path built from a constant defeats a string search, so check imports too.

    Two names here, one in the allow-list above: the command imports its own
    statement builder, and `artifacts/vex.py` carries the token in its module
    name without ever naming it as a value. Anything else importing one would
    be a new consumer.
    """
    allowed = {"artifacts.vex", "emit_vex"}
    for path in source_files():
        named = {name for name in imported_modules(parse(path)) if VEX_TOKEN in name}
        assert not named - allowed, f"{module_name(path)} imports {named - allowed}"


def test_the_manifest_exists_and_parses(manifest: dict) -> None:
    """A committed manifest is what makes the folder's emptiness a claim rather than an absence."""
    assert manifest["schema_version"] == 1


def test_the_document_count_agrees_with_the_list(manifest: dict) -> None:
    """The count is a restatement, so it can disagree; a test is what stops it."""
    assert manifest["document_count"] == len(manifest["documents"])


def test_the_manifest_says_why_it_is_empty(manifest: dict) -> None:
    """`document_count: 0` alone reads as an oversight. The note is what distinguishes them."""
    assert manifest["note"].strip()
    assert manifest["document_count"] == 0, "a document was added; this test should now be removed"


def test_every_document_is_pinned_and_placed(manifest: dict) -> None:
    """Vacuous while the folder is empty, and load-bearing the moment it is not."""
    for entry in manifest["documents"]:
        assert (VEX_DIR.parent / entry["path"]).is_file(), entry["path"]
        assert entry["source"] in SOURCES
        assert SNAPSHOT_DATE.match(entry["snapshot_date"]), entry["snapshot_date"]


def test_every_document_digest_matches_its_bytes(manifest: dict) -> None:
    """A loose file has no commit of its own, so the digest is what makes "pinned" checkable."""
    for entry in manifest["documents"]:
        raw = (VEX_DIR.parent / entry["path"]).read_bytes()
        assert entry["document_digest"] == f"sha256:{hashlib.sha256(raw).hexdigest()}"


def test_only_a_project_authored_document_lacks_an_upstream_url(manifest: dict) -> None:
    """The two facts must agree: something published upstream has somewhere it came from."""
    for entry in manifest["documents"]:
        published = entry["source"] == "upstream_published"
        assert (entry["upstream_url"] is not None) == published, entry["path"]


def test_the_documents_are_sorted_by_path(manifest: dict) -> None:
    """Sorted, so two edits to the manifest do not produce a spurious diff."""
    paths = [entry["path"] for entry in manifest["documents"]]
    assert paths == sorted(paths)
