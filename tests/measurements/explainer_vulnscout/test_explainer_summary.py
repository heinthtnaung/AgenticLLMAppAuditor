"""Guards on re-scoring in one step: `--write` puts the summary and the README's block in place."""

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "measurements"))

from explainer_vulnscout import summary as scoring  # noqa: E402

RECORD = ROOT / "measurements" / "explainer_vulnscout"
BEGIN = "<!-- scored: begin -->\n```text\n"
END = "```\n<!-- scored: end -->"
BEFORE = "# A stand-in record\n\nProse above the block.\n\n"
AFTER = "\n\nProse below the block.\n"


def stand_in(folder: Path, readme: str) -> Path:
    """Make a record folder of the real replies and the README given, and give it."""
    shutil.copy(RECORD / "replies.jsonl", folder / "replies.jsonl")
    (folder / "README.md").write_text(readme, encoding="utf-8")
    return folder


def shown(summary: str) -> str:
    """Give the summary's first and last sections, the part the README shows."""
    sections = summary.split("\n\n")
    return sections[0] + "\n\n" + sections[-1]


def test_writing_puts_the_summary_beside_the_replies_and_its_counts_in_the_readme(tmp_path):
    folder = stand_in(tmp_path, BEFORE + BEGIN + "stale\n" + END + AFTER)
    scoring.write_record(folder)
    written = (folder / "summary.txt").read_text(encoding="utf-8")
    assert written == scoring.summary(folder / "replies.jsonl")
    assert (folder / "README.md").read_text(encoding="utf-8") == (
        BEFORE + BEGIN + shown(written) + END + AFTER
    )


@pytest.mark.parametrize("readme", [
    BEFORE + AFTER,
    BEFORE + BEGIN + "stale\n" + AFTER,
    BEFORE + BEGIN + "one\n" + END + BEGIN + "two\n" + END + AFTER,
])
def test_a_readme_without_one_pair_of_markers_is_refused_and_nothing_is_written(tmp_path, readme):
    folder = stand_in(tmp_path, readme)
    with pytest.raises(ValueError, match="exactly once"):
        scoring.write_record(folder)
    assert not (folder / "summary.txt").exists()
    assert (folder / "README.md").read_text(encoding="utf-8") == readme


def test_a_summary_not_in_three_sections_is_refused_rather_than_shown_in_part():
    with pytest.raises(ValueError, match="scoring, rows and counts"):
        scoring.scored_block("scored by x\n\nrows only\n")


def test_without_write_the_summary_of_the_replies_named_is_printed_and_nothing_written(
    tmp_path, capsys
):
    folder = stand_in(tmp_path, BEFORE + BEGIN + "stale\n" + END + AFTER)
    assert scoring.main([str(folder / "replies.jsonl")]) == 0
    assert capsys.readouterr().out == scoring.summary(folder / "replies.jsonl")
    assert sorted(one.name for one in folder.iterdir()) == ["README.md", "replies.jsonl"]


@pytest.mark.parametrize("argv", [[], ["replies.jsonl", "--write"]])
def test_neither_or_both_of_a_replies_file_and_write_is_refused(argv):
    with pytest.raises(SystemExit):
        scoring.main(argv)
