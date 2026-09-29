"""The check that makes a stale README a test failure, skipped unless it is asked for.

`README.md` prints real CLI output beside the answer file that produced it.
Twice in one afternoon a rendering change left those blocks false and a person
caught it by hand; this is that person, made structural:

    DOCS_LIVE_SCAN=1 python -m pytest tests/docs/test_readme_live.py

It is off by default because it scans a fetched repository with Syft and Trivy;
`doc_live` says what it needs and runs it. The markers themselves are guarded in
`test_readme_markers.py`, which needs no corpus and so is not gated: damage to a
marker is caught by anyone running `pytest`, and only the question of whether
the printed output still reproduces waits for a scan.
"""

import os

import pytest

from doc_live import fail_on_stale_blocks
from doc_pages import README

LIVE = "DOCS_LIVE_SCAN"

pytestmark = pytest.mark.skipif(
    not os.environ.get(LIVE),
    reason=f"set {LIVE}=1 to run {README.path.name}'s own commands for real",
)


def test_every_block_the_readme_prints_still_reproduces(tmp_path):
    """Run each command the README documents and fail with the new text of every drifted line."""
    fail_on_stale_blocks(README, tmp_path)
