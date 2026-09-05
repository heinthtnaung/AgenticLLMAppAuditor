"""Counts what left the machine, so the exposure claim is auditable not asserted.

The proposal asks for "the data-exposure implications of sending sensitive audit
artefacts to an external inference provider". A byte count alone is a weak
answer: what matters is *which fields* went, and the paths and identifiers are
the sensitive part rather than the size.
"""

from dataclasses import dataclass, field


@dataclass
class Ledger:
    """Every prompt sent to a hosted model in one run, and what was in it."""

    prompts: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)

    def record(self, prompt: str, subject: str) -> None:
        """Note one transmission and the surface it was about."""
        self.prompts.append(prompt)
        self.subjects.append(subject)

    def summary(self) -> dict:
        """Counts and the field kinds transmitted. No prompt text: the log holds that."""
        return {
            "requests": len(self.prompts),
            "bytes_sent": sum(len(p.encode()) for p in self.prompts),
            "surfaces_described": sorted(set(self.subjects)),
            "field_kinds_transmitted": [
                "prompt template source text",
                "surface file paths and line numbers",
                "surface kinds and names",
            ],
        }


# Stated rather than measured, because no client can measure them. Naming the
# routing one specifically is worth more than the byte count: OpenRouter selects
# an upstream provider per request, so without pinned routing the operator
# cannot say which company received the data.
UNMEASURABLE = (
    "provider retention period",
    "whether the data is used for training",
    "sub-processors and jurisdiction",
    "which upstream provider served the request, unless routing is pinned",
)
