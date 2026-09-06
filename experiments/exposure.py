"""Counts what left the machine, so the exposure claim is auditable not asserted.

The proposal asks for "the data-exposure implications of sending sensitive audit
artefacts to an external inference provider". A byte count alone is a weak
answer: what matters is *which fields* went, and the paths and identifiers are
the sensitive part rather than the size.

**The field list used to be a constant, and that made it wrong.** It named the
prompt template's source text on runs that transmitted none -- `build_findings`
drives the planner through the same seam as the probe, and a statically refuted
template is decided without a request. The kinds are now derived from the
prompts actually recorded, so a run that sent only a planner prompt says so.
"""

from dataclasses import dataclass, field

from prompt_kinds import FIELD_KINDS, field_kinds


@dataclass
class Ledger:
    """Every prompt sent to a model in one run, and what each of them carried."""

    prompts: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)

    def record(self, prompt: str, kind: str) -> None:
        """Note one transmission and which kind of prompt it was."""
        if kind not in FIELD_KINDS:
            raise ValueError(f"unknown prompt kind {kind!r}; expected one of "
                             f"{tuple(sorted(FIELD_KINDS))}")
        self.prompts.append(prompt)
        self.kinds.append(kind)

    def summary(self) -> dict:
        """Counts and the field kinds transmitted. No prompt text: the log holds that."""
        return {
            "requests": len(self.prompts),
            "bytes_sent": sum(len(p.encode()) for p in self.prompts),
            "prompt_kinds": sorted(set(self.kinds)),
            "field_kinds_transmitted": field_kinds(self.kinds),
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
