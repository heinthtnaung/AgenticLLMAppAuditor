"""Guards on what a recorded run says it came from: asked, written down, never guessed."""

import sys
from pathlib import Path

# The recorder is a script beside the corpus it measures, not a package in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "measurements"))

import run_provenance as provenance  # noqa: E402
from run_provenance import RecordingFailed  # noqa: E402


def test_ollama_unreadable_once_the_run_is_over_is_recorded_rather_than_raised(monkeypatch):
    # The exit code is already in hand by then, and raising would lose it.
    def failing(command):
        """Fail the way `ollama ps` does with the server down."""
        raise RecordingFailed("ollama ps exited 1: could not connect")

    monkeypatch.setattr(provenance, "captured", failing)
    assert provenance.ollama_at_end() == "unavailable: ollama ps exited 1: could not connect"
