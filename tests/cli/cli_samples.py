"""The scan results the CLI tests drive, without a scanner or a socket in sight.

Named `cli_samples` and not `samples`: pytest puts each test directory on the
path and imports by basename, so a second `samples.py` would be shadowed by
`tests/deps/samples.py`.
"""

import json

from deps.syft_report import Catalogue, Component
from deps.trivy_report import Advisory

BUILT_AT = "2026-09-22T02:00:05Z"
# Deliberately not shaped like real versions. A fixture that looks real lets a
# hardcoded version pass the very test written to forbid one, which is how this
# tool printed trivy 0.58.1 on a 0.74.0 machine in the first place.
SYFT_VERSION = "syft-under-test"
TRIVY_VERSION = "trivy-under-test"

TOTAL_LOSS = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
LOW_CONFIDENTIALITY = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"

LODASH = Component(
    name="lodash",
    version="4.17.20",
    purl="pkg:npm/lodash@4.17.20",
    ecosystem="npm",
    locations=("/package-lock.json",),
)

ADVISORY = Advisory(
    advisory_id="CVE-2021-23337",
    purl=LODASH.purl,
    fixed_version="4.17.21",
    summary="Command injection in lodash",
    details="A remote attacker can inject commands through a template option.",
    vectors={"ghsa": TOTAL_LOSS, "nvd": LOW_CONFIDENTIALITY},
)


def written_metadata(directory) -> object:
    """Write a database metadata file the way Trivy writes one."""
    metadata = directory / "metadata.json"
    metadata.write_text(json.dumps({"UpdatedAt": BUILT_AT}), encoding="utf-8")
    return metadata


def scanners_answering(monkeypatch, components=(LODASH,), advisories=None) -> None:
    """Answer for both scanners, so no test shells out or opens a socket."""
    from cli import audit
    from deps import syft_runner, trivy_runner

    indexed = {ADVISORY.purl: (ADVISORY,)} if advisories is None else advisories
    found = Catalogue(components=tuple(components), unidentified=())
    monkeypatch.setattr(audit.syft_runner, "scan_directory", lambda path: found)
    monkeypatch.setattr(audit.trivy_runner, "scan_directory", lambda path: indexed)
    monkeypatch.setattr(audit.syft_runner, "installed_version", lambda: SYFT_VERSION)
    monkeypatch.setattr(audit.trivy_runner, "installed_version", lambda: TRIVY_VERSION)
    monkeypatch.setattr(syft_runner, "is_available", lambda: True)
    monkeypatch.setattr(trivy_runner, "is_available", lambda: True)
