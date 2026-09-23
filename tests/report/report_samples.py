"""The findings and provenance the report tests render, built by hand.

No test runs a scanner. Every vector here is real and its score is what
`src/cvss/` computes from it, so a test asserting 7.5 is asserting the tool
agrees with the published equations and not with itself.

Named `report_samples` and not `samples`: pytest puts each test directory on the
path and imports by basename, so a second `samples.py` would be shadowed by
`tests/deps/samples.py`.
"""

from deps.syft_report import Catalogue, Component, UnidentifiedArtifact
from deps.trivy_report import Advisory
from findings.finding import build_finding
from report.record import AdvisoryDatabase, RunProvenance

CONFIDENTIALITY_ONLY = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"  # 7.5 High
LOW_CONFIDENTIALITY = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"  # 5.3 Medium
TOTAL_LOSS = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"  # 9.8 Critical
HARMLESS = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"  # 0.0 None

# Two readings that come to the same number and are not the same reading. The
# deceptive shape: measured by score these agree, and they do not.
SAME_SCORE_ONE = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"  # 6.5 Medium
SAME_SCORE_TWO = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:L"  # 6.5 Medium

# A pair at the far ends of one band, and a pair a tenth apart across a
# boundary: 2.9 that changes nothing against 0.1 that changes the response.
WIDE_WITHIN_MEDIUM = "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:L/I:N/A:N"  # 4.0 Medium
TOP_OF_MEDIUM = "CVSS:3.1/AV:N/AC:L/PR:H/UI:R/S:C/C:H/I:L/A:N"  # 6.9 Medium
BOTTOM_OF_HIGH = "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:L/A:L"  # 7.0 High

VERSION_2_VECTOR = "AV:N/AC:L/Au:N/C:P/I:P/A:P"

DATABASE = AdvisoryDatabase(built_at="2026-09-22T02:00:05Z")

# Fixture versions, deliberately not shaped like real ones. The last pair were
# plausible numbers and one of them was wrong for a machine nobody had checked;
# what a run records is what `deps` asks the tools, which `tests/cli` pins.
PROVENANCE = RunProvenance(
    repository="fetched/vulnscout",
    syft_version="syft-under-test",
    trivy_version="trivy-under-test",
    database=DATABASE,
)


def component(name: str = "django", version: str = "2.2.0", **overrides) -> Component:
    """Build one installed component."""
    fields = {
        "name": name,
        "version": version,
        "purl": f"pkg:pypi/{name}@{version}",
        "ecosystem": "python",
        "locations": ("/requirements.txt",),
    }
    fields.update(overrides)
    return Component(**fields)


def advisory(advisory_id: str = "CVE-2019-14234", purl: str = "", **overrides) -> Advisory:
    """Build one advisory, with whichever sources a test needs on it."""
    fields = {
        "advisory_id": advisory_id,
        "purl": purl or component().purl,
        "fixed_version": "2.2.4",
        "summary": "SQL injection in key and index lookups",
        "details": "An issue was discovered.",
        "vectors": {"ghsa": CONFIDENTIALITY_ONLY},
    }
    fields.update(overrides)
    return Advisory(**fields)


def finding(installed: Component | None = None, **advisory_overrides):
    """Build one finding through the real join, so its scores are really computed."""
    installed = installed or component()
    return build_finding(installed, advisory(purl=installed.purl, **advisory_overrides))


def catalogue(*components: Component, unidentified: tuple = ()) -> Catalogue:
    """Wrap components as the catalogue Syft now hands back."""
    return Catalogue(components=tuple(components), unidentified=tuple(unidentified))


def unidentified(name: str = "./local-action", ecosystem: str = "github-action"):
    """Build one artifact nothing could ever be joined to."""
    return UnidentifiedArtifact(name=name, ecosystem=ecosystem, locations=("/.github/",))
