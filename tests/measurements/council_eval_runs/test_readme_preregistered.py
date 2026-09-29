"""The 2 x 2's readings were fixed before its numbers existed, and stay as they were fixed."""

from hashlib import sha256
from pathlib import Path

README = Path(__file__).resolve().parents[3] / "measurements" / "council_eval_runs" / "README.md"
BEGIN = "<!-- preregistered: begin -->"
END = "<!-- preregistered: end -->"

# The digest sent to the team lead on 2026-09-25, before the first variant pass.
# A section that no longer hashes to it was edited after the results were known.
PREREGISTERED_SHA256 = "feb118da20f6b2c6aa575834be47d2b21188f6f411c77a7bb2b7deffb283c481"


def preregistered() -> str:
    """Give the README's text between the two markers, exactly."""
    text = README.read_text(encoding="utf-8")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError(f"{README} must hold each preregistration marker exactly once")
    return text.split(BEGIN, 1)[1].split(END, 1)[0]


def test_the_readings_are_as_they_were_fixed_before_the_runs():
    assert sha256(preregistered().encode("utf-8")).hexdigest() == PREREGISTERED_SHA256
