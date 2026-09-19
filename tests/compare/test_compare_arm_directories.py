"""Where each arm of `--compare-models` writes, asserted with no run involved.

`compare_run.cloud_artifacts_dir` is the second copy of a literal
`evaluation.document` already owns -- `test_evaluate.py` pins
`main.DEFAULT_ARTIFACTS_DIR` to the `agentic_auditor` one for exactly that
reason, and this file is that test's twin for the cloud one.

It was `CLOUD_ARTIFACTS_DIR`, a module constant, until the hosted arm started
deriving its directory from the local one so that `--artifacts-dir` moves both
arms rather than one. The claims below are unchanged -- they are about where the
*default* lands -- so each passes the default in rather than reading a constant,
and a fourth test pins the derivation the constant could not express.

These are claims about constants, so they need neither a model nor an audit.
They live apart from `test_compare_arms.py`, which drives the whole run: that
file was the one place both jobs were done, and it outgrew the size a reader
can hold at once.
"""

from pathlib import Path

import compare_run
import evaluate
import main
from evaluation.document import CLOUD_AUDITOR, SCORED_SYSTEMS

# Where the hosted arm lands when the caller names no directory, which is what
# every claim below is about.
DEFAULT_CLOUD_DIR = compare_run.cloud_artifacts_dir(main.DEFAULT_ARTIFACTS_DIR)


def test_the_cloud_arms_directory_is_named_for_the_cloud_auditor() -> None:
    """`compare_run.py` writes the literal rather than importing it; the copy must agree."""
    assert DEFAULT_CLOUD_DIR.name == CLOUD_AUDITOR


def test_the_cloud_arms_default_sits_inside_the_directory_the_scorer_defaults_to() -> None:
    """So `evaluate --system cloud_auditor` with no flags scores exactly where the arm wrote."""
    assert DEFAULT_CLOUD_DIR == evaluate.DEFAULT_ARTIFACTS_DIR / CLOUD_AUDITOR


def test_the_two_arms_default_to_two_different_directories() -> None:
    """The structural half of "neither overwrites the other", with no run involved."""
    assert DEFAULT_CLOUD_DIR != main.DEFAULT_ARTIFACTS_DIR


def test_the_cloud_arm_is_a_system_the_scorer_will_accept() -> None:
    """`build_evaluation` refuses a system outside the vocabulary, so the name must be in it."""
    assert CLOUD_AUDITOR in SCORED_SYSTEMS


def test_a_moved_local_arm_takes_the_hosted_arm_with_it() -> None:
    """What the constant got wrong: isolating one run must isolate both arms.

    `web/run_jobs.py` passes `artifacts/runs/<run_id>/<system>/` so two runs of
    one app cannot overwrite each other. With a fixed cloud directory that held
    for the local arm only, and every compare run's hosted arm still landed in
    one shared folder.
    """
    isolated = Path("artifacts") / "runs" / "abc123" / "agentic_auditor"

    assert compare_run.cloud_artifacts_dir(isolated) == isolated.parent / CLOUD_AUDITOR
    assert compare_run.cloud_artifacts_dir(isolated) != DEFAULT_CLOUD_DIR
