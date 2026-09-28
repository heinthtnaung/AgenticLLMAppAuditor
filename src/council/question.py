"""What any question put to a local model carries: its two turns, and what it is about.

A member is asked about one metric (`council.prompt.MemberPrompt`); the explainer
is asked why the published sources differ (`council.explanation_prompt`). Both go
through the one pinned client in `council.ollama`, so temperature, seed, `think`
and the window guard cannot differ between them.
"""

from typing import Protocol


class Question(Protocol):
    """A prompt for a local model: the standing instruction, the turn answered, its subject."""

    @property
    def system(self) -> str:
        """Give the standing instruction."""

    @property
    def user(self) -> str:
        """Give the turn the model answers."""

    @property
    def subject(self) -> str:
        """Name what the question is about, as a refusal says it: a metric, or an explanation."""
