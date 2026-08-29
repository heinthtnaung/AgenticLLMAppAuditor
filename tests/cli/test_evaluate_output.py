"""What the evaluation entry point prints: counts, their bounds, and never a rate.

`scorer.py` and `SCHEMAS.md` both state that nothing in the tool prints a rate,
and this entry point is the one place that promise could be broken. The gates on
the artifact would not protect a division here either: the clean app is
`precision_reportable` with `produced_finding_count: 0`, so precision there is
0/0. The counts are printed and the division is the reader's.

The other line under test is `false_positives: None`, which must read as "not
measurable". A `0` there is the exact lie the artifact refuses -- a plausible
shape that says the run raised no false alarms when the truth is that its key
never claimed to list every finding.
"""

import re

import pytest

import evaluate
from evaluate_helpers import scored
from evaluation_fixtures import (
    APP,
    findings_document,
    grading_key,
    key_entry,
    unrelated_finding,
)
from findings_fixtures import static_finding

# A decimal point with a digit after it, searched inside a token rather than
# matched against the whole of it: `0.33`, `.33` and `share=0.33` are all rates,
# and a guard that only matches a bare token lets every one of them through.
FLOAT_TOKEN = re.compile(r"\d*\.\d")

# A path holds dots and slashes and is not a rate; the written path is printed.
def rate_tokens(printed: str) -> list[str]:
    """Return every printed token that looks like a rate, ignoring file paths."""
    tokens = [token for token in re.split(r"\s+", printed) if "/" not in token]
    return [token for token in tokens if FLOAT_TOKEN.search(token.strip("()[]{},;"))]


def incomplete_key_run(tmp_path, monkeypatch, **staging) -> dict:
    """Score a run whose key does not claim completeness, so false positives are undefined."""
    return scored(tmp_path, monkeypatch,
                  key=grading_key([key_entry()], findings_complete=False), **staging)


def test_the_printed_output_carries_the_counts_and_their_denominators(
        tmp_path, monkeypatch, capsys) -> None:
    """Guard for the two tests below: the run does print a per-app count line."""
    scored(tmp_path, monkeypatch)
    assert f"  {APP}: 1 of 1 matched, 0 missed" in capsys.readouterr().out


def test_the_printed_output_holds_no_percentage(tmp_path, monkeypatch, capsys) -> None:
    """Nothing in the tool prints a rate, and this entry point is where one could appear."""
    scored(tmp_path, monkeypatch)
    assert "%" not in capsys.readouterr().out


def test_the_printed_output_holds_no_float(tmp_path, monkeypatch, capsys) -> None:
    """A bare decimal is a rate whether or not it wears a percent sign."""
    scored(tmp_path, monkeypatch)
    assert rate_tokens(capsys.readouterr().out) == []


@pytest.mark.parametrize("planted", ["recall (0.33)", "recall .33", "share=0.33", "0.33"])
def test_the_no_rate_guard_catches_a_planted_rate(planted: str) -> None:
    """The guard above is only worth having if it fires, so plant one and check it does.

    Written because the first version matched a whole token, so any punctuation
    around the number defeated it and the invariant went unheld.
    """
    assert rate_tokens(f"  recall pool: 2 of 6\n  {planted}\n") == [planted.split()[-1]]


def test_the_no_rate_guard_does_not_fire_on_the_written_path() -> None:
    """The first printed line carries a file path, which holds dots and is not a rate."""
    assert rate_tokens("wrote /tmp/x.y/artifacts/agentic_auditor/evaluation.json\n") == []


def test_an_unmeasurable_false_positive_count_is_reported_as_not_measurable(
        tmp_path, monkeypatch) -> None:
    """A key that does not claim completeness leaves precision undefined, and says so."""
    document = incomplete_key_run(
        tmp_path, monkeypatch,
        findings=findings_document([static_finding(), unrelated_finding()]))
    assert "false positives not measurable" in evaluate.app_lines(document)[0]


def test_an_unmeasurable_false_positive_count_is_never_reported_as_zero(
        tmp_path, monkeypatch) -> None:
    """`0` there reads as a run with no false alarms, over a key that never claimed so."""
    document = incomplete_key_run(
        tmp_path, monkeypatch,
        findings=findings_document([static_finding(), unrelated_finding()]))
    assert "false positives 0" not in evaluate.app_lines(document)[0]


def test_a_measurable_false_positive_count_is_reported_as_the_number(
        tmp_path, monkeypatch) -> None:
    """The contrast: a complete key does support the count, and then 0 is the truth."""
    document = scored(tmp_path, monkeypatch)
    assert "false positives 0" in evaluate.app_lines(document)[0]


def test_each_app_line_is_followed_by_what_bounds_it(tmp_path, monkeypatch) -> None:
    """A count never travels without its qualifications, so they share the same block."""
    document = scored(tmp_path, monkeypatch)
    assert evaluate.app_lines(document)[1].startswith("    bounded by: ")


def test_the_qualifications_that_bound_a_count_are_printed_beside_it(
        tmp_path, monkeypatch, capsys) -> None:
    """`small_sample` and `model_disabled` hold on every corpus run and must be visible."""
    scored(tmp_path, monkeypatch)
    assert "    bounded by: advisory_data_not_ingested, model_disabled, small_sample" \
        in capsys.readouterr().out


def test_each_pooled_total_names_the_apps_it_rests_on(tmp_path, monkeypatch) -> None:
    """A pooled count cannot be quoted without knowing which apps went into it."""
    document = scored(tmp_path, monkeypatch)
    assert f"recall pool: 1 of 1 over {APP}" in evaluate.totals_lines(document)[0]


def test_a_refused_f1_is_printed_as_its_reason_and_not_as_a_number(
        tmp_path, monkeypatch) -> None:
    """F1 is refused with the reason stated, because a silent omission reads as unimplemented."""
    document = incomplete_key_run(tmp_path, monkeypatch)
    assert evaluate.totals_lines(document)[-1] == (
        "  f1: no app supports both precision and recall")
