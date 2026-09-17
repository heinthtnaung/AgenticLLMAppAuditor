"""What `progress.stage` announces, and the order a real audit announces it in.

`stage` was added for the web UI, which shows an audit advancing rather than a
spinner. Four claims are held here rather than described: the stderr line is
printed whether anyone is listening or not, an injected listener is handed every
boundary in the order it happened, a name outside `STAGES` is refused instead of
becoming a ninth stage no caller can render, and every name inside it is
accepted.

The last three tests drive real code -- an audit over a tree written into
`tmp_path`, and `pipeline.publish` -- with Syft, Trivy, the model, vexctl and the
renderer replaced at their seams (see `cli_helpers` and `pipeline_helpers`),
because the order the call sites fire in is the one thing a unit test of `stage`
cannot see. A synthetic tree is weaker than a real one: nothing here is
oversized, non-UTF-8, malformed or shaped in a way nobody foresaw.

Nothing in this file opens a socket, starts a process or requires a tool.
"""

from pathlib import Path

import pytest

from cli_helpers import stub_knowledge, stub_model, stub_syft
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from mixed_app_fixtures import APP_NAME, write_mixed_app
from pipeline_helpers import stub_export, stub_vex
from reporting import progress
from reporting.progress import STAGES, stage
import main
import pipeline

# The vocabulary, spelled out beside the constant rather than only imported:
# `STAGES == STAGES` would hold over any reordering, and a caller that renders
# "not started yet" from this list reads its order as a promise.
EXPECTED_STAGES = ("fetch", "surfaces", "dependencies", "advisories", "checks",
                   "advice", "write", "publish")

# The one boundary a local-path audit never reaches: `publish` is
# `pipeline.publish`, which only a URL run gets to.
URL_ONLY_STAGE = "publish"
LOCAL_RUN_STAGES = tuple(name for name in EXPECTED_STAGES if name != URL_ONLY_STAGE)

# One boundary and its detail, for the tests about a single announcement.
SAMPLE_STAGE = "checks"
SAMPLE_DETAIL = "4 findings"

# Three real boundaries, announced in the order a run announces them -- which is
# not alphabetical order, so a listener that sorted what it heard would fail.
THREE_BOUNDARIES = ("surfaces", "checks", "write")

# A plausible name that is not in the vocabulary. Deliberately not a prefix or a
# suffix of a real one, so the refusal cannot be satisfied by a near match.
NOT_A_STAGE = "uploading"

# What the audited tree declares, so the dependency stage really builds
# documents instead of reporting that there is no bill of materials.
DECLARED_PACKAGE = "langchain==0.3.25\n"
STUBBED_SCAN = {"components": [{"type": "library", "name": "langchain",
                                "version": "0.3.25"}]}


def record() -> tuple[list[tuple[str, str]], progress.StageListener]:
    """A listener and the list it appends every boundary it hears to."""
    heard: list[tuple[str, str]] = []
    return heard, lambda name, detail: heard.append((name, detail))


# --- one announcement ---------------------------------------------------------

def test_a_stage_prints_its_name_and_detail_to_stderr(capsys) -> None:
    """The default audience is a person watching a command line, and stdout is not it."""
    stage(SAMPLE_STAGE, SAMPLE_DETAIL)
    printed = capsys.readouterr()
    assert printed.err == f"-- {SAMPLE_STAGE}: {SAMPLE_DETAIL}\n"
    assert printed.out == "", "a caller piping the artifact paths keeps a clean stdout"


def test_a_stage_with_no_detail_prints_only_its_name(capsys) -> None:
    """The detail is optional, and an absent one leaves no dangling colon."""
    stage(SAMPLE_STAGE)
    assert capsys.readouterr().err == f"-- {SAMPLE_STAGE}\n"


def test_an_injected_listener_is_handed_the_name_and_the_detail() -> None:
    """Both halves, unchanged: the name is what a caller joins on, the detail is prose."""
    heard, listener = record()
    stage(SAMPLE_STAGE, SAMPLE_DETAIL, listener)
    assert heard == [(SAMPLE_STAGE, SAMPLE_DETAIL)]


def test_a_listener_does_not_replace_the_stderr_line(capsys) -> None:
    """Two audiences, not one: the command line kept its output when the UI arrived."""
    heard, listener = record()
    stage(SAMPLE_STAGE, SAMPLE_DETAIL, listener)
    assert capsys.readouterr().err == f"-- {SAMPLE_STAGE}: {SAMPLE_DETAIL}\n"
    assert heard == [(SAMPLE_STAGE, SAMPLE_DETAIL)], "the listener heard it too"


def test_an_explicit_none_listener_prints_what_omitting_it_prints(capsys) -> None:
    """A caller with nobody to notify passes None, and nothing else changes."""
    stage(SAMPLE_STAGE, SAMPLE_DETAIL, None)
    with_none = capsys.readouterr().err
    stage(SAMPLE_STAGE, SAMPLE_DETAIL)
    assert with_none == f"-- {SAMPLE_STAGE}: {SAMPLE_DETAIL}\n"
    assert with_none == capsys.readouterr().err


# --- the closed vocabulary ----------------------------------------------------

def test_the_vocabulary_is_the_eight_boundaries_a_run_has() -> None:
    """A closed list is a contract, so the whole list is pinned and not just its length."""
    assert STAGES == EXPECTED_STAGES


def test_every_member_of_the_vocabulary_is_accepted() -> None:
    """No caller can be refused for naming a real stage, and the order is kept."""
    heard, listener = record()
    for name in STAGES:
        stage(name, "", listener)
    assert heard == [(name, "") for name in STAGES]


def test_a_listener_receives_each_boundary_in_the_order_it_was_announced() -> None:
    """Order is the point: a progress display reads it as what has already happened."""
    heard, listener = record()
    for name in THREE_BOUNDARIES:
        stage(name, "", listener)
    assert heard == [(name, "") for name in THREE_BOUNDARIES]


def test_an_unknown_stage_is_refused_and_the_reason_names_the_vocabulary() -> None:
    """A typo must not become a ninth stage that shows as pending for the rest of the run."""
    with pytest.raises(ValueError) as refusal:
        stage(NOT_A_STAGE)
    message = str(refusal.value)
    assert NOT_A_STAGE in message
    for name in STAGES:
        assert name in message, name


def test_a_refused_stage_announces_nothing_at_all(capsys) -> None:
    """The refusal comes first: nothing is printed and no listener is notified."""
    heard, listener = record()
    with pytest.raises(ValueError):
        stage(NOT_A_STAGE, SAMPLE_DETAIL, listener)
    assert capsys.readouterr().err == ""
    assert heard == []


# --- the order a real run announces them in -----------------------------------

def audit_with_a_listener(monkeypatch: pytest.MonkeyPatch,
                          tmp_path: Path) -> list[tuple[str, str]]:
    """Audit a tree written here and return every boundary the listener heard."""
    repo = write_mixed_app(tmp_path)
    (repo / PYPI_MANIFEST).write_text(DECLARED_PACKAGE, encoding="utf-8")
    stub_syft(monkeypatch, STUBBED_SCAN)
    stub_model(monkeypatch)
    stub_knowledge(monkeypatch)
    heard, listener = record()
    args = main.build_parser().parse_args(
        [str(repo), "--artifacts-dir", str(tmp_path / "artifacts")])
    produced = main.run(args, listener)
    assert produced["app"] == APP_NAME, "the audit really ran over the written tree"
    return heard


def announced_positions(heard: list[tuple[str, str]]) -> list[int]:
    """Where each boundary heard sits in the vocabulary, in the order it was heard."""
    return [STAGES.index(name) for name, _ in heard]


def test_a_local_audit_announces_every_stage_but_publish(monkeypatch, tmp_path) -> None:
    """Seven boundaries: a directory argument publishes nothing, so it ends at `write`."""
    heard = audit_with_a_listener(monkeypatch, tmp_path)
    assert [name for name, _ in heard] == list(LOCAL_RUN_STAGES)


def test_the_boundaries_a_real_run_announces_come_in_the_vocabularys_order(
        monkeypatch, tmp_path) -> None:
    """The claim that survives a new call site, which the exact list above does not.

    A stage added to the local path fails the test above and is *meant* to; this
    one keeps holding unless the new call site announces out of order, which is
    the defect a reader of a progress display would see and no other test would.
    """
    positions = announced_positions(audit_with_a_listener(monkeypatch, tmp_path))
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions), "no boundary is announced twice"
    assert len(positions) == len(LOCAL_RUN_STAGES), "and none of them is missing"


def test_the_publish_stage_announces_itself(monkeypatch, tmp_path) -> None:
    """The eighth boundary: reached by a URL run only, so no audit above announces it."""
    stub_vex(monkeypatch)
    stub_export(monkeypatch)
    heard, listener = record()
    pipeline.publish(tmp_path / "artifacts", advisories_read=False, on_stage=listener)
    assert [name for name, _ in heard] == [URL_ONLY_STAGE]
