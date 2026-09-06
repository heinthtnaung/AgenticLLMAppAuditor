"""Where each arm of `--compare-models` writes, asserted with no run involved.

`compare_run.CLOUD_ARTIFACTS_DIR` is the second copy of a literal
`evaluation.document` already owns -- `test_evaluate.py` pins
`main.DEFAULT_ARTIFACTS_DIR` to the `agentic_auditor` one for exactly that
reason, and this file is that test's twin for the cloud one.

These are claims about constants, so they need neither a model nor an audit.
They live apart from `test_compare_arms.py`, which drives the whole run: that
file was the one place both jobs were done, and it outgrew the size a reader
can hold at once.
"""

import compare_run
import evaluate
import main
from evaluation.document import CLOUD_AUDITOR, SCORED_SYSTEMS


def test_the_cloud_arms_directory_is_named_for_the_cloud_auditor() -> None:
    """`compare_run.py` writes the literal rather than importing it; the copy must agree."""
    assert compare_run.CLOUD_ARTIFACTS_DIR.name == CLOUD_AUDITOR


def test_the_cloud_arms_default_sits_inside_the_directory_the_scorer_defaults_to() -> None:
    """So `evaluate --system cloud_auditor` with no flags scores exactly where the arm wrote."""
    assert compare_run.CLOUD_ARTIFACTS_DIR == evaluate.DEFAULT_ARTIFACTS_DIR / CLOUD_AUDITOR


def test_the_two_arms_default_to_two_different_directories() -> None:
    """The structural half of "neither overwrites the other", with no run involved."""
    assert compare_run.CLOUD_ARTIFACTS_DIR != main.DEFAULT_ARTIFACTS_DIR


def test_the_cloud_arm_is_a_system_the_scorer_will_accept() -> None:
    """`build_evaluation` refuses a system outside the vocabulary, so the name must be in it."""
    assert CLOUD_AUDITOR in SCORED_SYSTEMS
