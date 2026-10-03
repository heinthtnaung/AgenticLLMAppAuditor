"""The README's scored block is the summary's, so a re-scoring that leaves it stale turns red."""

from pathlib import Path

RECORDS = Path(__file__).resolve().parents[3] / "measurements" / "explainer_vulnscout"
BEGIN = "<!-- scored: begin -->\n```text\n"
END = "```\n<!-- scored: end -->"
SECTION = "\n\n"


def scored_block() -> str:
    """Give the README's text between the two markers, exactly."""
    text = (RECORDS / "README.md").read_text(encoding="utf-8")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("the explainer README must hold each scored-block marker exactly once")
    return text.split(BEGIN, 1)[1].split(END, 1)[0]


def test_the_scored_block_is_the_summary_s_scoring_and_its_counts():
    sections = (RECORDS / "summary.txt").read_text(encoding="utf-8").split(SECTION)
    assert len(sections) == 3
    scoring, _, counts = sections
    assert scored_block() == scoring + SECTION + counts
