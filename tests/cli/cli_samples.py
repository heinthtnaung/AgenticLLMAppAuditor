"""The scan results and replies the CLI tests drive, without a scanner, a model or a socket.

Named `cli_samples` and not `samples`: pytest puts each test directory on the
path and imports by basename, so a second `samples.py` would be shadowed by
`tests/deps/samples.py`.
"""

import io
import json

from deps.syft_report import Catalogue, Component
from deps.trivy_report import Advisory

BUILT_AT = "2026-09-22T02:00:05Z"
# What `run_command_line` calls the repository it audits and the folder its
# reports go into, both inside the test's own `tmp_path`.
REPOSITORY_NAME = "vulnscout"
REPORTS_FOLDER = "reports"
# Deliberately not shaped like real versions: a fixture that looks real lets a
# version hardcoded in `src/` pass the very test written to forbid one.
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

# Verbatim in `ADVISORY.details`, so a member quoting it offers a quotation that verifies.
QUOTATION = "A remote attacker can inject commands"
# One legal value per metric, so an unremarkable member answers a whole vector.
LEGAL = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}


def advisory_like(advisory_id: str, **overrides) -> Advisory:
    """Build one advisory against lodash, with whichever fields a test needs changed."""
    fields = {
        "advisory_id": advisory_id,
        "purl": LODASH.purl,
        "fixed_version": None,
        "summary": "",
        "details": ADVISORY.details,
        "vectors": {"ghsa": TOTAL_LOSS, "nvd": TOTAL_LOSS},
    }
    return Advisory(**{**fields, **overrides})


def answering(evidence: str = QUOTATION, declining: tuple[str, ...] = ()):
    """A client whose members answer every metric, or decline the ones named."""
    def said(member, prompt):
        """Decline a named metric, and answer any other with its legal value."""
        if prompt.metric in declining:
            return json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
        value = LEGAL[prompt.metric]
        return json.dumps({"value": value, "evidence": evidence, "confidence": "high"})

    return {"ollama": said}


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


def run_command_line(argv, monkeypatch, tmp_path, **scan) -> tuple[int, str, str]:
    """Run the command line with the scanners answered and every report kept in `tmp_path`."""
    from cli import main as entry

    scanners_answering(monkeypatch, **scan)
    monkeypatch.setattr(entry, "refuse_unrunnable", lambda repository: BUILT_AT)
    out, error = io.StringIO(), io.StringIO()
    repository = str(tmp_path / REPOSITORY_NAME)
    code = entry.main([repository, *argv], out=out, error=error, reports=tmp_path / REPORTS_FOLDER)
    return code, out.getvalue(), error.getvalue()
