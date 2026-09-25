"""Guards on the gate: everything a report reader sees is compared, and nothing about layout."""

from pathlib import Path

import pytest

import eval_samples as samples
from cli.council_run import OLLAMA_PROVIDER, assess_one, build_roster
from council.ruling import Basis
from council_eval.commands import main
from council_eval.gate import differences, recorded_findings, replayed_findings
from council_eval.recording import RecordingClient
from report.text_council import advisory_lines

OTHER_ANSWERS = samples.ANSWERS | {"AV": samples.reply("L"), "UI": samples.DECLINED}
# Every metric quoted from the advisory, so two members answering alike settle
# `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`, which scores 7.5.
ALL_QUOTED = {
    metric: samples.reply(value)
    for metric, value in zip("AV AC PR UI S C I A".split(), "N L N N U N N H".split())
}
FIGURE = "  ·  CVSS 7.5 High"

MEASUREMENTS = Path(__file__).resolve().parents[3] / "measurements"
PILOT = MEASUREMENTS / "council_eval_runs" / "pilot-vulnscout"
RECORDED = MEASUREMENTS / "council_runs" / "gpu-full.report.txt"
# The two pairs the pilot's README gates: the scored pair, and the clean third runs.
GATED_PAIRS = [
    ("qwen2.5-7b-instruct.run1", "llama3.2-latest.run2"),
    ("qwen2.5-7b-instruct.run3", "llama3.2-latest.run3"),
]


def outcome(first=samples.ANSWERS, second=OTHER_ANSWERS):
    """Put the sample finding to two members, by default disagreeing on AV and quoting UI alone."""
    servers = {
        samples.MODEL: samples.FakeServer(first),
        samples.OTHER_MODEL: samples.FakeServer(second),
    }
    client = RecordingClient(post=lambda url, payload: servers[payload["model"]](url, payload))
    roster = build_roster((samples.MODEL, samples.OTHER_MODEL))
    return assess_one(samples.finding(), roster, {OLLAMA_PROVIDER: client})


def settled_outcome():
    """Put the sample finding to two members that quote the advisory alike on every metric."""
    return outcome(ALL_QUOTED, ALL_QUOTED)


def report_of(lines: list[str]) -> str:
    """Wrap a council block in the report around it, as the recorded file holds it."""
    return "\n".join(["SOURCES AGREE (1)", "", "COUNCIL (1)", *lines, "", "MATCHED NOTHING"])


def test_a_recording_of_the_same_record_passes_the_gate():
    recorded = recorded_findings(report_of(advisory_lines(outcome())))
    assert differences(recorded, replayed_findings((outcome(),))) == []


def test_the_facts_read_are_the_heading_the_settled_count_and_the_unsettled_lines():
    facts = recorded_findings(report_of(advisory_lines(outcome())))[samples.KEY]
    assert facts.heading.startswith(f"{samples.KEY}  no vector")
    assert facts.settled == 4
    assert facts.entries[0].startswith("AV  ·  contested")


def test_a_value_one_member_quoted_alone_reconciles_with_the_wording_before_sole():
    # Three settled with two quotations agreeing and UI quoted by one member alone:
    # before `4526250` all four read as AGREED.
    lines = advisory_lines(outcome())
    sole, agreed = f"      1  {Basis.SOLE.value}", f"      3  {Basis.AGREED.value}"
    assert sole in lines and agreed in lines
    kept = [line for line in lines if line != sole]
    before = [line.replace(agreed, f"      4  {Basis.AGREED.value}") for line in kept]
    assert differences(recorded_findings(report_of(before)), replayed_findings((outcome(),))) == []


def test_a_recording_that_names_sole_must_match_the_replay_s_bases_exactly():
    lines = advisory_lines(outcome())
    moved = [line.replace(f"3  {Basis.AGREED.value}", f"4  {Basis.AGREED.value}") for line in lines]
    found = differences(recorded_findings(report_of(moved)), replayed_findings((outcome(),)))
    assert any("do not reconcile" in one for one in found)


def test_a_member_value_that_moved_is_named():
    was, became = "small:1b (small)  N  ·", "small:1b (small)  A  ·"
    lines = [line.replace(was, became) for line in advisory_lines(outcome())]
    found = differences(recorded_findings(report_of(lines)), replayed_findings((outcome(),)))
    assert any("is now" in one for one in found)


def test_a_quotation_wrapped_differently_is_the_same_quotation():
    lines = advisory_lines(outcome())
    at = next(i for i, line in enumerate(lines) if line.lstrip().startswith("“"))
    head, tail = lines[at][:40], lines[at][40:]
    rewrapped = [*lines[:at], head, f"        {tail}", *lines[at + 1 :]]
    recorded = recorded_findings(report_of(rewrapped))
    assert differences(recorded, replayed_findings((outcome(),))) == []


def test_a_finding_in_only_one_of_the_two_is_named():
    found = differences(recorded_findings(report_of(advisory_lines(outcome()))), {})
    assert found == [f"{samples.KEY} is in only one of the two"]


def test_a_report_with_no_council_block_is_refused():
    with pytest.raises(ValueError, match="this one has 0"):
        recorded_findings("SOURCES AGREE (1)\n")


def with_heading(outcome_, heading: str) -> str:
    """Render one outcome's block as a recording, its heading line replaced."""
    lines = advisory_lines(outcome_)
    return report_of([heading, *lines[1:]])


def test_a_recording_made_before_the_settled_figure_passes_without_it():
    heading = advisory_lines(settled_outcome())[0]
    assert heading.endswith(FIGURE)
    recorded = recorded_findings(with_heading(settled_outcome(), heading.replace(FIGURE, "")))
    assert differences(recorded, replayed_findings((settled_outcome(),))) == []


def test_a_recording_showing_a_different_figure_is_named():
    heading = advisory_lines(settled_outcome())[0].replace("7.5 High", "9.8 Critical")
    recorded = recorded_findings(with_heading(settled_outcome(), heading))
    found = differences(recorded, replayed_findings((settled_outcome(),)))
    assert any("heading" in one for one in found)


def test_a_recording_without_the_figure_still_has_its_vector_compared():
    heading = advisory_lines(settled_outcome())[0].replace(FIGURE, "").replace("A:H", "A:L")
    recorded = recorded_findings(with_heading(settled_outcome(), heading))
    found = differences(recorded, replayed_findings((settled_outcome(),)))
    assert any("heading" in one for one in found)


@pytest.mark.parametrize("pair", GATED_PAIRS, ids=["scored pair", "third runs"])
def test_the_pilots_passes_replay_what_the_recorded_audit_printed(pair, capsys):
    # The pilot's README says the gate passes. Held here, offline from the saved
    # passes, so a change to the council block the recording predates turns red.
    replies = [str(PILOT / f"{one}.replies.jsonl") for one in pair]
    dataset = str(PILOT / "vulnscout.dataset.json")
    argv = ["gate", "--dataset", dataset, "--replies", *replies, "--recorded", str(RECORDED)]
    assert main(argv) == 0
    assert "gate passed" in capsys.readouterr().out
