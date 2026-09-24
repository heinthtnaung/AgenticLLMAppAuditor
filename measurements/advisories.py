"""The advisory corpus: seven offline Trivy scans, read into one set of texts.

Every number in `measurements/README.md` comes from this corpus, so the scans
are built here once and the measuring scripts import them. Nothing reaches the
network: the scans carry `deps.trivy_runner`'s offline flags and read the
database snapshot already on this machine.

The text of an advisory is its title and its description, which is what a
council member would be shown. Advisories are keyed by their published id, so
the same CVE reached through two ecosystems counts once.
"""

import sys
from itertools import chain
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from deps.scanner import run_json_scanner  # noqa: E402
from deps.trivy_runner import (  # noqa: E402
    REQUIRED_OFFLINE_FLAGS,
    TRIVY_EXECUTABLE,
    Advisory,
    read_advisories,
)

HERE = Path(__file__).resolve().parent

JSON_FORMAT = ("--format", "json")
VULNERABILITIES_ONLY = ("--scanners", "vuln")

FILESYSTEM_SUBCOMMAND = "fs"
ROOTFS_SUBCOMMAND = "rootfs"

# Four handwritten manifests of deliberately out-of-date packages, two synthetic
# package databases, and the repository the project audits. Seven scans, chosen
# to reach different advisory feeds rather than to be a realistic deployment.
SCANS: tuple[tuple[str, str, Path], ...] = (
    ("pypi", FILESYSTEM_SUBCOMMAND, HERE / "corpus" / "pypi"),
    ("npm", FILESYSTEM_SUBCOMMAND, HERE / "corpus" / "npm"),
    ("golang", FILESYSTEM_SUBCOMMAND, HERE / "corpus" / "golang"),
    ("rust", FILESYSTEM_SUBCOMMAND, HERE / "corpus" / "rust"),
    ("debian", ROOTFS_SUBCOMMAND, HERE / "rootfs" / "debian"),
    ("alpine", ROOTFS_SUBCOMMAND, HERE / "rootfs" / "alpine"),
    ("vulnscout", FILESYSTEM_SUBCOMMAND, REPOSITORY_ROOT / "fetched" / "vulnscout"),
)


def build_command(subcommand: str, target: Path) -> list[str]:
    """Build one offline Trivy command, for a directory of manifests or for a root filesystem."""
    return [
        TRIVY_EXECUTABLE,
        subcommand,
        *JSON_FORMAT,
        *VULNERABILITIES_ONLY,
        *REQUIRED_OFFLINE_FLAGS,
        str(target),
    ]


def scan(subcommand: str, target: Path) -> tuple[Advisory, ...]:
    """Run one scan and give back its advisories, flattened out of the per-purl index."""
    if not target.exists():
        raise FileNotFoundError(f"{target} is not on this machine; nothing to scan")
    indexed = read_advisories(run_json_scanner(build_command(subcommand, target)))
    return tuple(chain.from_iterable(indexed.values()))


def advisory_texts() -> dict[str, str]:
    """Give every distinct advisory of the corpus as the text a member would read."""
    texts: dict[str, str] = {}
    for _, subcommand, target in SCANS:
        texts.update(text_by_id(scan(subcommand, target)))
    return texts


def text_by_id(advisories: tuple[Advisory, ...]) -> dict[str, str]:
    """Key one scan's advisories by their published id, title and description joined."""
    return {
        advisory.advisory_id: f"{advisory.summary}\n\n{advisory.details}".strip()
        for advisory in advisories
    }


def scan_sizes() -> dict[str, int]:
    """Say how many advisories each scan found, for the table in the README."""
    return {name: len(scan(subcommand, target)) for name, subcommand, target in SCANS}
