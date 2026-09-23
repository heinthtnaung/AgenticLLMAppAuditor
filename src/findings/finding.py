"""The join: a CVE affecting an installed component is a finding.

That is the whole rule. There is no reachability analysis here and no notion of
a CVE that does not count because nothing calls it -- a component is installed
or it is not, and an advisory is published against that exact version or it is
not. Syft says the first, Trivy says the second, and the versioned purl is what
puts them together.

A finding holds every source's assessment, attributed, and **says nothing about
which is right**. It does not average them, does not privilege NVD -- which
carries a vector for far fewer advisories than GHSA does -- and computes no
single severity of its own. Choosing between disagreeing sources is the
council's job and the council is not built; a precedence order invented here to
tidy the shape would be an unattributable answer wearing a tidy one's clothes.
"""

from dataclasses import dataclass
from itertools import chain
from typing import Iterable, Mapping

from cvss.metrics import METRIC_ORDER
from cvss.vector import differing_metrics
from deps.syft_report import Component, component_order
from deps.trivy_report import Advisory

from findings.assessment import SourceScore, UnreadableSource, read_sources

NO_ADVISORIES: tuple[Advisory, ...] = ()


@dataclass(frozen=True)
class Finding:
    """One CVE affecting one installed component, with every source's assessment kept apart."""

    component: Component
    advisory: Advisory
    scores: tuple[SourceScore, ...]
    unreadable: tuple[UnreadableSource, ...]

    @property
    def is_scored(self) -> bool:
        """Say whether any source's vector could be read, which is not whether the score is zero."""
        return bool(self.scores)

    def disputed_metrics(self) -> tuple[str, ...]:
        """Name the metrics the readable sources disagree on, in specification order."""
        if len(self.scores) < 2:
            return ()
        first, *rest = [score.parsed_vector for score in self.scores]
        # Every metric some source reads differently from the first is a metric
        # not all of them agree on, so comparing against one vector is enough.
        disputed = set(chain.from_iterable(differing_metrics(first, other) for other in rest))
        return tuple(name for name in METRIC_ORDER if name in disputed)


def build_findings(
    components: Iterable[Component],
    advisories_by_purl: Mapping[str, tuple[Advisory, ...]],
) -> tuple[Finding, ...]:
    """Join components to the advisories published against them: one finding per pair."""
    refuse_unjoinable_index(advisories_by_purl)
    per_component = [
        findings_for_component(component, advisories_by_purl) for component in components
    ]
    return tuple(sorted(chain.from_iterable(per_component), key=finding_order))


def findings_for_component(
    component: Component,
    advisories_by_purl: Mapping[str, tuple[Advisory, ...]],
) -> list[Finding]:
    """Give one finding per advisory published against a component's exact version."""
    advisories = advisories_by_purl.get(component.purl, NO_ADVISORIES)
    return [build_finding(component, advisory) for advisory in advisories]


def build_finding(component: Component, advisory: Advisory) -> Finding:
    """Make one finding, splitting the sources into those that scored and those refused."""
    read = read_sources(advisory)
    return Finding(
        component=component,
        advisory=advisory,
        scores=tuple(item for item in read if isinstance(item, SourceScore)),
        unreadable=tuple(item for item in read if isinstance(item, UnreadableSource)),
    )


def unmatched_purls(
    components: Iterable[Component],
    advisories_by_purl: Mapping[str, tuple[Advisory, ...]],
) -> tuple[str, ...]:
    """Name the purls carrying advisories that matched no installed component."""
    # The join drops these, and a dropped advisory is a CVE missing from a report
    # that still looks clean. A caller asks for them rather than being told late.
    refuse_unjoinable_index(advisories_by_purl)
    installed = {component.purl for component in components}
    return tuple(sorted(purl for purl in advisories_by_purl if purl not in installed))


def refuse_unjoinable_index(advisories_by_purl: object) -> None:
    """Refuse an advisory index that is not the purl-keyed mapping the join needs."""
    if isinstance(advisories_by_purl, Mapping):
        return
    given = type(advisories_by_purl).__name__
    raise TypeError(f"Advisories must be a mapping of purl to advisories, not {given}")


def finding_order(finding: Finding) -> tuple[str, str, str, tuple[str, ...], str]:
    """Order findings so two runs over one tree produce identical output."""
    return (*component_order(finding.component), finding.advisory.advisory_id)
