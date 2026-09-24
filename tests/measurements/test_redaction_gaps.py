"""Guards on the redaction measurement: every identifier it found is named, once each."""

import sys
from pathlib import Path

# The measurement is a script beside the corpus it reads, not a package in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "measurements"))

import redaction_gaps  # noqa: E402


def test_each_identifier_in_another_namespace_is_named_once_in_sorted_order(capsys):
    redacted = {"CVE-1": "see SNYK-JS-1 and PYSEC-2021-1", "CVE-2": "and PYSEC-2021-1 again"}
    redaction_gaps.report_namespaces(redacted)
    assert "2 advisories ['PYSEC-2021-1', 'SNYK-JS-1']" in capsys.readouterr().out
