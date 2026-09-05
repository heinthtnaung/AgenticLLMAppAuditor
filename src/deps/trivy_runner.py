"""Runs Trivy over an app directory and returns its vulnerability report.

The advisory half of the supply-chain evidence: Syft answers what is installed,
Trivy answers what is known to be wrong with it. Both are standard external
tools run offline, because a version matcher is a spec this project does not
own -- the same argument that made Syft the right producer for the SBOM.

Offline by flags rather than by trust: the database update, the Java index
update, the rego check update, the version check and the telemetry are each
disabled explicitly on every run. The database itself is fetched out-of-band
(see the README) into Trivy's own cache, and is pinned by its `UpdatedAt` --
a property of the database build. `DownloadedAt` is the local clock and is
never read, for the same reason a fetch timestamp is never recorded.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

GENERATOR_NAME = "trivy"
TIMEOUT_SECONDS = 300

# Everything that would reach the network, off by name. A flag Trivy drops in
# a later release fails the run loudly, which is the correct failure mode for
# a guarantee -- silence would mean "maybe it phoned home".
SCAN_ARGUMENTS = (
    "fs", "--scanners", "vuln",
    "--skip-db-update", "--skip-java-db-update", "--skip-check-update",
    "--offline-scan", "--disable-telemetry", "--skip-version-check",
    "--quiet", "--format", "json",
)


def default_cache_dir() -> Path:
    """Where Trivy keeps its database: its own cache, not this project's tree."""
    return Path.home() / ".cache" / GENERATOR_NAME


def is_available() -> bool:
    """Say whether Trivy is installed, so a caller can skip rather than crash."""
    return shutil.which(GENERATOR_NAME) is not None


def db_snapshot_date(cache_dir: Path | None = None) -> str | None:
    """Return the database's own build date, or None when no database is cached.

    None is a normal answer that degrades the audit, exactly as a missing Syft
    does: the check does not run, and coverage says so.
    """
    metadata = (cache_dir or default_cache_dir()) / "db" / "metadata.json"
    if not metadata.is_file():
        return None
    return json.loads(metadata.read_text(encoding="utf-8")).get("UpdatedAt")


def scan(app_dir: Path, cache_dir: Path | None = None) -> dict:
    """Return Trivy's vulnerability report for an app directory."""
    if not app_dir.is_dir():
        raise NotADirectoryError(f"cannot scan {app_dir}: not a directory")
    directory = str(cache_dir or default_cache_dir())
    output = _run([*SCAN_ARGUMENTS, "--cache-dir", directory, str(app_dir)])
    return json.loads(output)


def advisory_index(report: dict) -> dict[str, list[dict]]:
    """Index a report by versioned purl, each record renamed into this project's terms.

    Trivy's field names stop here, so the check that joins this to the mapping
    never learns whose report it was. Records are ordered by advisory id, so
    output never depends on scan order. The CVSS vector is quoted from the one
    source Trivy itself names -- never its Severity word, which is a judgement
    among disagreeing sources rather than a quotation.
    """
    index: dict[str, list[dict]] = {}
    for result in report.get("Results", []):
        for record in result.get("Vulnerabilities", []):
            purl = record.get("PkgIdentifier", {}).get("PURL")
            if purl:
                index.setdefault(purl, []).append(_record(record))
    return {purl: sorted(records, key=lambda one: one["advisory_id"])
            for purl, records in index.items()}


def _record(record: dict) -> dict:
    """One advisory in this project's vocabulary, verbatim values only."""
    source = record.get("SeveritySource")
    vector = record.get("CVSS", {}).get(source, {}).get("V3Vector") if source else None
    # The severity WORD, kept only when the SAME source also carries the vector
    # that attributes it -- so the word never appears without `advisory_cvss_source`
    # beside it. Otherwise it would read as this tool's own unattributed pick.
    severity = record.get("Severity") if vector else None
    return {
        "advisory_id": record["VulnerabilityID"],
        # Trivy writes "" for "no fix", so null has one spelling here.
        "advisory_fixed_version": record.get("FixedVersion") or None,
        "advisory_severity": severity or None,
        "advisory_cvss_vector": vector,
        "advisory_cvss_source": source if vector else None,
    }


def pin(report: dict, db_updated_at: str) -> dict:
    """Name what matched: the generator, its version, and the database's own date."""
    return {
        "advisory_generator_name": GENERATOR_NAME,
        "advisory_generator_version": report["Trivy"]["Version"],
        "advisory_db_updated_at": db_updated_at,
    }


def _run(arguments: list[str]) -> str:
    """Run one Trivy command, raising with its own message if it fails."""
    if not is_available():
        raise RuntimeError(
            f"{GENERATOR_NAME} is not installed - see the README prerequisites")
    try:
        done = subprocess.run(
            [GENERATOR_NAME, *arguments], capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS, check=False, env={"PATH": _path()},
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{GENERATOR_NAME} timed out after {TIMEOUT_SECONDS}s") from error
    if done.returncode != 0:
        raise RuntimeError(f"{GENERATOR_NAME} {arguments[0]} failed: {done.stderr.strip()}")
    return done.stdout


def _path() -> str:
    """Return a PATH that can find Trivy, without inheriting the rest of the environment."""
    return os.environ.get("PATH", "/usr/bin:/bin")
