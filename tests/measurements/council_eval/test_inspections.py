"""Guards on the inspection subcommands: each reads its evidence and names what it found."""

import io

import pytest

import eval_samples as samples
from council_eval import commands
from council_eval.collect import collect
from council_eval.dataset import write_dataset
from council_eval.inspections import NONE, comparison_lines, turn_lines
from council_eval.reruns import RerunComparison
from council_eval.server_log import Load, Request


def one_pass(tmp_path, name: str) -> str:
    """Take one pass of the sample model over the sample item into a file."""
    path = tmp_path / f"{name}.jsonl"
    header = samples.header()
    collect((samples.item(),), samples.MODEL, path, header, samples.Asking(), io.StringIO())
    return str(path)


def test_two_passes_of_the_same_answers_compare_identical(tmp_path, capsys):
    first, second = one_pass(tmp_path, "first"), one_pass(tmp_path, "second")
    commands.main(["compare", "--first", first, "--second", second])
    out = capsys.readouterr().out
    assert "8 calls, 8 with the same request, 8 byte-identical replies" in out
    assert f"differing: {NONE}" in out


def test_a_comparison_names_every_call_that_moved_or_reloaded():
    moved = ((samples.KEY, samples.MODEL, "AC"),)
    found = RerunComparison(samples.MODEL, 8, 8, 7, 0, moved, (), moved)
    lines = comparison_lines(found)
    assert lines[1] == f"  differing: {samples.KEY} AC"
    assert lines[3] == f"  reloaded after an item's first call, second pass: {samples.KEY} AC"


def test_the_quoting_step_counts_each_member_s_unverified_quotations(tmp_path, capsys):
    dataset = tmp_path / "dataset.json"
    write_dataset((samples.item(),), {"repository": "example"}, dataset)
    commands.main(["quoting", "--dataset", str(dataset), "--replies", one_pass(tmp_path, "pass")])
    out = capsys.readouterr().out.splitlines()
    row = [line for line in out if line.startswith(samples.MODEL)][0]
    # Alone, the member settles AV, AC, PR, UI and A on its own quotation; its
    # scope quotation is not in the advisory, and is not the prompt's either.
    assert row.split() == [samples.MODEL, "5", "1", "0"]


def test_the_values_step_counts_what_each_member_named_against_the_last_listed(tmp_path, capsys):
    dataset = tmp_path / "dataset.json"
    write_dataset((samples.item(),), {"repository": "example"}, dataset)
    commands.main(["values", "--dataset", str(dataset), "--replies", one_pass(tmp_path, "pass")])
    rows = [line.split() for line in capsys.readouterr().out.splitlines()[1:]]
    # The sample member answers UI with N, which the product's order lists first.
    assert [samples.MODEL, "UI", "R", "0/1", "N:1"] in rows
    assert [samples.MODEL, "C", "N", "0/1", "declined:1"] in rows


def test_a_server_log_is_kept_in_a_new_file_and_never_over_one(tmp_path):
    journal, out = tmp_path / "journal.txt", tmp_path / "excerpt.tsv"
    journal.write_text("2026-09-24T18:56:32+08:00 HOST ollama[1]: print_info: general.name = Q\n")
    commands.main(["server-log", "--journal", str(journal), "--out", str(out)])
    assert out.read_text() == "2026-09-24T18:56:32+08:00\tload\tQ\n"
    with pytest.raises(FileExistsError):
        commands.main(["server-log", "--journal", str(journal), "--out", str(out)])


def test_the_turns_step_counts_requests_by_path_and_loads_by_model():
    requests = (
        Request("t0", "200", 0.001, "127.0.0.1", "POST", "/api/generate"),
        Request("t1", "200", 0.5, "127.0.0.1", "POST", "/api/generate"),
    )
    lines = turn_lines(requests, (Load("t0", "Qwen"),), calls=1)
    assert lines == [
        "requests: 2 POST /api/generate", "loads: 1 Qwen", f"turns: 1; not of 1 calls: {NONE}",
    ]
