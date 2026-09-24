"""Guards on reading a scan into the corpus: every advisory the index holds, in its order."""

import sys
from pathlib import Path

# The corpus reader is a script beside the scans it runs, not a package in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "measurements"))

import advisories  # noqa: E402


def test_a_scan_gives_every_advisory_of_every_purl_in_the_order_indexed(monkeypatch, tmp_path):
    indexed = {"pkg:npm/a@1": ("first", "second"), "pkg:npm/b@1": ("third",)}
    monkeypatch.setattr(advisories, "run_json_scanner", lambda command: {})
    monkeypatch.setattr(advisories, "read_advisories", lambda document: indexed)
    assert advisories.scan(advisories.FILESYSTEM_SUBCOMMAND, tmp_path) == (
        "first", "second", "third",
    )
