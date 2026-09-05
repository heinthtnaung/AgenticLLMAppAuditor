"""The typed link from one LLM surface to the component it came from.

`ComponentRef` is named in the proposal's data model beside `Surface`,
`Finding` and `GraphState`, and had never been written down: the link lived only
as a dict built inline in `mapping.py`.

**`Component` is deliberately absent.** It was written and then deleted: nothing
in `src/` would have built one. A component is read out of `sbom.json` and
matched, and wrapping those dicts in a class purely to make a proposal row read
"Yes" is ceremony -- and a class no production code constructs is dead code by
this project's own rule. `docs/PROPOSAL_COVERAGE.md` records that half as not
delivered rather than quietly counting it.

**This changes no artifact.** `ComponentRef.as_entry()` produces exactly the
dict `mapping.json` already held, field for field and in the same order, so the
file is byte-identical and its schema is untouched. What the dataclass adds is
a name for the thing, one place where its fields are declared, and a refusal:
a reference whose reason is outside `MAPPING_REASONS` cannot be constructed,
where a dict could hold anything.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentRef:
    """One surface's reference to the component it resolved to, and how.

    `reason` says what kind of answer this is -- a third-party package, the
    standard library, first-party code, something used but never declared, or
    unresolved.

    `purl` may be *versionless* when `component_version_count` is above one:
    a surface's import cannot say which installed copy it loads, so `mapping`
    deliberately drops the version rather than naming one by sort order. The
    invariant here is only that a purl implies at least one match -- an earlier
    draft required exactly one and was refuted by the ambiguous-purl tests,
    which is what those tests are for.
    """

    surface_id: str
    module: str
    package_root: str | None
    component_name: str | None
    ecosystem: str | None
    purl: str | None
    component_version_count: int
    reason: str
    resolved_by: str

    def __post_init__(self) -> None:
        """Refuse a reference a later phase could not act on."""
        # Imported here rather than at module scope: `mapping` imports this
        # module, and naming it at the top would close the circle.
        from artifacts.mapping import MAPPING_REASONS
        if self.reason not in MAPPING_REASONS:
            raise ValueError(f"unknown mapping reason {self.reason!r}; expected {MAPPING_REASONS}")
        if not self.surface_id:
            raise ValueError("a component reference must name the surface it came from")
        if self.purl and not self.component_version_count:
            raise ValueError(
                f"{self.surface_id} carries a purl but matched no component")

    def as_entry(self) -> dict:
        """The `mapping.json` entry for this reference, in the order the file has always held."""
        return {
            "surface_id": self.surface_id,
            "module": self.module,
            "package_root": self.package_root,
            "component_name": self.component_name,
            "ecosystem": self.ecosystem,
            "purl": self.purl,
            "component_version_count": self.component_version_count,
            "reason": self.reason,
            "resolved_by": self.resolved_by,
        }
