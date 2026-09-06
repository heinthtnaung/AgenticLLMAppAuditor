"""The one verdict the semantic probe reaches on its own, and the sentence it says it in.

A template holding no interpolation point cannot meet this check's criterion --
there is no runtime value to sit in its instructions -- so `judge` refutes it
from the text alone and never asks. Both halves matter. The refutation is the
*only* probe state whose marker is the detail text rather than a reason code
(`Probe.__post_init__` forbids a reason on a concluded probe), which is why
`experiments/agreement.reason_without_a_model` matches on `STATIC_REFUTATION`
and why the constant exists at all; and reaching it without a request is what
keeps a model's opinion about a wholly static prompt out of the artifact -- the
local model called one injectable on a measured run.

Neither half was pinned before: the call site could be given a different
sentence, or the branch removed outright, and the whole suite still passed.

Its own file rather than a section of `test_semantic_probe.py`, which is at the
200-line ceiling rule 18 sets. The app is written into `tmp_path` here as
everywhere -- and a synthetic tree is weaker than a real one: one small file, no
template shape nobody thought of.
"""

from pathlib import Path

from artifacts.finding import REFUTED, Finding, Probe
from checks import semantic_probe
from checks.semantic_probe import STATIC_REFUTATION, interpolates_anything, judge
from parsing.extractor_python import parse_file
from semantic_probe_fixtures import (
    FILE,
    STATIC_TEMPLATE_APP,
    STATIC_TEMPLATE_SURFACE_ID,
    STATIC_TEMPLATE_TEXT,
    Answering,
    app_and_surfaces,
    probe_over,
)

# A stand-in that would flag anything it is shown, so a probe reading `refuted`
# below can only have been reached without asking it.
FLAGGING_REPLY = "VULNERABLE\nThe template drops a value into the instructions."


def judge_the_static_template(tmp_path: Path) -> tuple[Finding | None, Probe, Answering]:
    """Judge the app's one placeholder-free template, off the tree a real audit reads."""
    repo, surfaces = app_and_surfaces(tmp_path, STATIC_TEMPLATE_APP)
    surface = semantic_probe.prompt_surfaces(surfaces, FILE)[0]
    text = semantic_probe.template_text(parse_file(repo / FILE), surface.line)
    ask = Answering(FLAGGING_REPLY)
    finding, probe = judge(surface, text, ask)
    return finding, probe, ask


def test_the_template_the_test_builds_really_holds_no_interpolation_point(tmp_path) -> None:
    """Non-vacuity: the text was read and has no placeholder, so the right branch is under test.

    Without this the tests below would also pass on a template whose text could
    not be read at all, which is a different state with a different record.
    """
    repo, surfaces = app_and_surfaces(tmp_path, STATIC_TEMPLATE_APP)
    surface = semantic_probe.prompt_surfaces(surfaces, FILE)[0]
    text = semantic_probe.template_text(parse_file(repo / FILE), surface.line)
    assert surface.id == STATIC_TEMPLATE_SURFACE_ID
    assert text == STATIC_TEMPLATE_TEXT
    assert interpolates_anything(text) is False


def test_a_template_with_no_interpolation_point_is_refuted_and_is_not_a_finding(
        tmp_path) -> None:
    """The check settles it itself: a refuted probe, no finding, and no reason code."""
    finding, probe, _ask = judge_the_static_template(tmp_path)
    assert finding is None
    assert probe.outcome == REFUTED
    assert probe.reason is None
    assert probe.subject_id == STATIC_TEMPLATE_SURFACE_ID


def test_the_refutation_carries_the_sentence_the_study_matches_on(tmp_path) -> None:
    """`agreement.reason_without_a_model` reads this detail; another sentence it cannot see."""
    _finding, probe, _ask = judge_the_static_template(tmp_path)
    assert probe.detail == STATIC_REFUTATION


def test_the_refutation_is_reached_without_asking_the_model(tmp_path) -> None:
    """The point of deciding it here: a stand-in that flags everything is never consulted."""
    _finding, _probe, ask = judge_the_static_template(tmp_path)
    assert ask.prompts == []


def test_a_whole_repository_run_refutes_it_without_asking_either(tmp_path) -> None:
    """The same through `run_over_repo`, which is how the audit actually reaches `judge`."""
    findings, probes, ask = probe_over(tmp_path, FLAGGING_REPLY, STATIC_TEMPLATE_APP)
    assert findings == []
    assert [(p.outcome, p.detail) for p in probes] == [(REFUTED, STATIC_REFUTATION)]
    assert ask.prompts == []
