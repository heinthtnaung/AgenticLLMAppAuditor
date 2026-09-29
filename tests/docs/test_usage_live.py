"""The check that makes a stale usage guide a test failure, skipped unless it is asked for.

`docs/USAGE.md` prints the audit run with two answers changed, beside the answer
file it derives them from. This reruns it:

    DOCS_LIVE_SCAN=1 python -m pytest tests/docs/test_usage_live.py

It is off by default because it scans a fetched repository with Syft and Trivy;
`doc_live` says what it needs and runs it. The council progress the guide prints
is not rerun: it needs Ollama, and `test_usage_markers.py` pins it as the one
output of this tool the guide leaves unmarked.
"""

import os

import pytest

from doc_live import fail_on_stale_blocks
from doc_pages import USAGE

LIVE = "DOCS_LIVE_SCAN"

pytestmark = pytest.mark.skipif(
    not os.environ.get(LIVE),
    reason=f"set {LIVE}=1 to run {USAGE.path.name}'s own commands for real",
)


def test_every_block_the_usage_guide_prints_still_reproduces(tmp_path):
    """Run each command the usage guide documents and fail with the new text of any drifted line."""
    fail_on_stale_blocks(USAGE, tmp_path)
