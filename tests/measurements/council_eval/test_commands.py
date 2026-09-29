"""Guards on the subcommands: the gate passes on a faithful replay and fails on a changed one."""

import io
import json
from pathlib import Path

import pytest

import eval_samples as samples
from council_eval import commands
from council_eval.collect import collect
from council_eval.compose import replay_roster
from council_eval.dataset import write_dataset
from council_eval.replies import read_replies
from report.text_council import advisory_lines

OTHER_ANSWERS = samples.ANSWERS | {"AV": samples.reply("L"), "UI": samples.DECLINED}
SERVERS = {samples.MODEL: samples.ANSWERS, samples.OTHER_MODEL: OTHER_ANSWERS}


def two_passes(tmp_path):
    """Freeze the sample item and take one pass per model over it, the way `collect` does."""
    dataset = tmp_path / "dataset.json"
    write_dataset((samples.item(),), {"repository": "example"}, dataset)
    paths = []
    for model, answers in SERVERS.items():
        path = tmp_path / f"{model.replace(':', '-')}.jsonl"
        header = samples.header(model)
        collect((samples.item(),), model, path, header, samples.Asking(answers), io.StringIO())
        paths.append(path)
    return dataset, paths


def recorded_report(tmp_path, paths, was: str = "", became: str = ""):
    """Render the replayed pair as the audit would print it, one phrase changed if asked."""
    (outcome,) = replay_roster((samples.item(),), tuple(SERVERS), read_replies(tuple(paths)))
    lines = [line.replace(was, became) if was else line for line in advisory_lines(outcome)]
    report = tmp_path / "recorded.report.txt"
    report.write_text("\n".join(["COUNCIL (1)", *lines, ""]))
    return report


def gate(dataset, paths, report) -> int:
    """Run the gate subcommand."""
    replies = [str(path) for path in paths]
    return commands.main(
        ["gate", "--dataset", str(dataset), "--replies", *replies, "--recorded", str(report)]
    )


def test_the_gate_passes_a_replay_that_prints_what_was_recorded(tmp_path, capsys):
    dataset, paths = two_passes(tmp_path)
    assert gate(dataset, paths, recorded_report(tmp_path, paths)) == 0
    assert "gate passed" in capsys.readouterr().out


def test_the_gate_fails_a_replay_that_prints_something_else(tmp_path, capsys):
    dataset, paths = two_passes(tmp_path)
    changed = recorded_report(tmp_path, paths, was="  L  ·", became="  A  ·")
    assert gate(dataset, paths, changed) == commands.GATE_FAILED
    assert "is now" in capsys.readouterr().out


def test_scoring_measures_each_model_alone_and_the_pair(tmp_path, capsys):
    dataset, paths = two_passes(tmp_path)
    commands.main(["score", "--dataset", str(dataset), "--replies", *map(str, paths)])
    rosters = [line for line in capsys.readouterr().out.splitlines() if line.startswith("ROSTER")]
    assert rosters == [
        f"ROSTER {samples.MODEL}  (1 items)",
        f"ROSTER {samples.OTHER_MODEL}  (1 items)",
        f"ROSTER {samples.MODEL} + {samples.OTHER_MODEL}  (1 items)",
    ]


def test_the_totals_count_every_metric_and_name_every_vector(tmp_path):
    dataset, paths = two_passes(tmp_path)
    outcomes = replay_roster((samples.item(),), tuple(SERVERS), read_replies(tuple(paths)))
    expected = "8 metrics: 4 settled, 1 contested, 3 unresolved; 0 vectors"
    assert commands.totals_lines(outcomes) == [expected]


@pytest.mark.parametrize(
    "argv, step",
    [
        (["dataset", "--repository", "r", "--out", "o"], commands.run_dataset),
        (["collect", "--dataset", "d", "--model", "m", "--out", "o"], commands.run_collect),
        (["gate", "--dataset", "d", "--replies", "a", "--recorded", "r"], commands.run_gate),
        (["score", "--dataset", "d", "--replies", "a", "b"], commands.run_score),
    ],
)
def test_each_step_is_a_subcommand(argv, step):
    assert commands.parser().parse_args(argv).run is step


def test_a_pass_is_asked_in_the_product_s_words_unless_it_names_a_variant():
    base = ["collect", "--dataset", "d", "--model", "m", "--out", "o"]
    assert commands.parser().parse_args(base).variant == "baseline"
    assert commands.parser().parse_args([*base, "--variant", "reversed"]).variant == "reversed"


def test_a_variant_nobody_defined_is_refused():
    with pytest.raises(SystemExit):
        commands.main(["collect", "--dataset", "d", "--model", "m", "--out", "o", "--variant", "x"])


def test_a_dataset_names_a_cache_in_the_home_directory_from_the_home_mark():
    home = {"HOME": "/home/someone"}
    assert commands.home_relative(Path("/home/someone/.cache/trivy"), home) == "~/.cache/trivy"


def test_a_frozen_dataset_names_its_cache_from_the_home_mark(tmp_path, monkeypatch):
    # The scanners are stubbed; the cache, its date and the file written are real.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("TRIVY_CACHE_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    metadata = tmp_path / ".cache" / "trivy" / "db" / "metadata.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text('{"UpdatedAt": "2026-09-23T20:20:57Z"}')
    monkeypatch.setattr(commands, "vulnscout_items", lambda repository, cache: (samples.item(),))
    monkeypatch.setattr(commands.syft_runner, "installed_version", lambda: "1.52.0")
    monkeypatch.setattr(commands.trivy_runner, "installed_version", lambda: "0.74.0")
    out = tmp_path / "dataset.json"
    commands.main(["dataset", "--repository", "repo", "--out", str(out)])
    assert json.loads(out.read_text())["built_from"]["trivy_cache"] == "~/.cache/trivy"


@pytest.mark.parametrize("home", [{"HOME": "/home/someone"}, {}])
def test_a_cache_outside_the_home_directory_is_named_whole(home):
    assert commands.home_relative(Path("/var/cache/trivy"), home) == "/var/cache/trivy"


def test_an_unknown_step_is_refused():
    with pytest.raises(SystemExit):
        commands.main(["nothing"])
