"""The order-checked readings were fixed before any merged roster or reversed pass, and stay so."""

from hashlib import sha256
from pathlib import Path

README = (
    Path(__file__).resolve().parents[3]
    / "measurements" / "council_eval_runs" / "order-checked-vulnscout" / "README.md"
)
BEGIN = "<!-- preregistered: begin -->"
END = "<!-- preregistered: end -->"

# The digest sent to the team lead on 2026-09-25, before any merged roster was
# computed or any reversed pass taken. A section that no longer hashes to it was
# edited after the results were known.
PREREGISTERED_SHA256 = "0e6a96138315e49bb91c8e06504f229c364e9320b33c11038905b3e37623bcac"


def preregistered() -> str:
    """Give the README's text between the two markers, exactly."""
    text = README.read_text(encoding="utf-8")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError(f"{README} must hold each preregistration marker exactly once")
    return text.split(BEGIN, 1)[1].split(END, 1)[0]


def test_the_readings_are_as_they_were_fixed_before_the_runs():
    assert sha256(preregistered().encode("utf-8")).hexdigest() == PREREGISTERED_SHA256
