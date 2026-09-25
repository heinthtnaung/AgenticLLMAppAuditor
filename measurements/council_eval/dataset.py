"""The advisories the council is measured on, frozen to a file so scoring never needs a scan again.

An item keeps what the product needs to rebuild the finding it put to the council
-- the component and the advisory as Trivy published it -- and nothing is
re-derived at scoring time from a database snapshot that may have moved.

**The member's input is the product's**: `cli.council_run.advisory_text`, the
advisory's description. `measurements/advisories.py` joins the title to it, so a
harness built on that module would measure an input the council never reads.

The vulnscout items come the audit's own way -- Syft's components joined to
Trivy's advisories by `findings.build_findings` -- and in the order the audit
puts them to the council, which is the order of `gpu-full`.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cli.council_run import to_assess
from deps import syft_runner, trivy_runner
from deps.scanner import run_json_scanner
from deps.syft_report import Component
from deps.trivy_report import ADVISORY_ID, Advisory, advisory_records, read_advisories
from findings.finding import Finding, build_finding, build_findings

VULNSCOUT_SPLIT = "V"
PUBLISHED_DATE = "PublishedDate"
JSON_INDENT = 1


@dataclass(frozen=True)
class Item:
    """One finding as the council is put to it, and when its advisory was published."""

    split: str
    published: str
    finding: Finding

    @property
    def key(self) -> str:
        """Name the item by its advisory's published id."""
        return self.finding.advisory.advisory_id


def vulnscout_items(repository: Path, cache: Path) -> tuple[Item, ...]:
    """Give the repository's findings the way the audit builds them, in the order it asks them."""
    raw = run_json_scanner(trivy_runner.build_command(repository, cache))
    catalogue = syft_runner.scan_directory(repository)
    findings = build_findings(catalogue.components, read_advisories(raw))
    dates = published_dates(raw)
    asked = to_assess(findings, every_finding=True)
    return tuple(Item(VULNSCOUT_SPLIT, published_of(dates, one), one) for one in asked)


def published_dates(raw: Any) -> dict[str, str]:
    """Read each advisory's publication date, which the product's own `Advisory` does not keep."""
    records = advisory_records(raw)
    return {record[ADVISORY_ID]: record.get(PUBLISHED_DATE) or "" for record in records}


def published_of(dates: Mapping[str, str], finding: Finding) -> str:
    """Give a finding's publication date, refusing one the scan did not date."""
    published = dates.get(finding.advisory.advisory_id, "")
    if not published:
        raise ValueError(f"{finding.advisory.advisory_id} carries no {PUBLISHED_DATE} in the scan")
    return published


def write_dataset(items: tuple[Item, ...], built_from: Mapping[str, str], path: Path) -> None:
    """Freeze the items to a file, refusing to replace one already written."""
    if path.exists():
        raise FileExistsError(f"{path} already holds a dataset; a frozen dataset is not rewritten")
    document = {"built_from": dict(built_from), "items": [item_document(one) for one in items]}
    written = json.dumps(document, indent=JSON_INDENT, sort_keys=True)
    path.write_text(written + "\n", encoding="utf-8")


def item_document(item: Item) -> dict[str, Any]:
    """Give one item as plain data: its split, its date, its component and its advisory."""
    advisory = item.finding.advisory
    component = item.finding.component
    return {
        "split": item.split,
        "published": item.published,
        "component": vars(component) | {"locations": list(component.locations)},
        "advisory": vars(advisory) | {"vectors": dict(advisory.vectors)},
    }


def read_dataset(path: Path) -> tuple[Item, ...]:
    """Read a frozen dataset back into items, each finding rebuilt by the product's own join."""
    document = json.loads(path.read_text(encoding="utf-8"))
    items = tuple(item_from(entry) for entry in document["items"])
    refuse_repeated_keys(items)
    return items


def item_from(entry: Mapping[str, Any]) -> Item:
    """Rebuild one item, its finding made by `build_finding` exactly as the audit makes it."""
    written = entry["component"]
    component = Component(**written | {"locations": tuple(written["locations"])})
    finding = build_finding(component, Advisory(**entry["advisory"]))
    return Item(split=entry["split"], published=entry["published"], finding=finding)


def refuse_repeated_keys(items: tuple[Item, ...]) -> None:
    """Refuse a dataset naming one advisory twice, which would count its replies twice."""
    keys = [item.key for item in items]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise ValueError(f"the dataset names {', '.join(repeated)} more than once")
