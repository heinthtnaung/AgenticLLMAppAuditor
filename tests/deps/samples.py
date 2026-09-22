"""The scanner reports the tests read: saved ones, and ones built by hand.

No test runs Syft or Trivy. What a test feeds the parsers is either a report
captured from the real tool and saved under `fixtures/`, or a record built here
in the shape the tool emits it.

The arguments that are no kind of path are here too: every public entry point
taking a path has to refuse them the same way, and each names the type it was
handed.
"""

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

# What a public entry point may be handed instead of a path, with the type name
# its refusal has to say out loud.
NOT_PATHS = ((None, "NoneType"), (7, "int"), (["fetched/vulnscout"], "list"))

DJANGO_PURL = "pkg:pypi/django@2.2.0"
PYYAML_PURL = "pkg:pypi/pyyaml@5.1"

# CVE-2019-14234, as three sources scored it: Red Hat reads the same flaw as
# low-impact information disclosure where GHSA and NVD read it as total loss.
GHSA_VECTOR = "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
REDHAT_VECTOR = "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"


def load(name: str) -> dict:
    """Read one report captured from the real tool and saved under fixtures."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def syft_artifact(**overrides) -> dict:
    """Build one Syft artifact in the shape Syft emits it, changed where a test needs it."""
    entry = {
        "name": "django",
        "version": "2.2.0",
        "type": "python",
        "purl": DJANGO_PURL,
        "locations": [{"path": "/requirements.txt", "accessPath": "/requirements.txt"}],
    }
    entry.update(overrides)
    return entry


def syft_report_of(*artifacts) -> dict:
    """Wrap artifacts in the envelope a Syft report carries them in."""
    return {
        "artifacts": list(artifacts),
        "artifactRelationships": [],
        "source": {"type": "directory"},
    }


def trivy_record(**overrides) -> dict:
    """Build one Trivy advisory record in the shape Trivy emits it."""
    entry = {
        "VulnerabilityID": "CVE-2019-14234",
        "PkgName": "Django",
        "PkgIdentifier": {"PURL": DJANGO_PURL, "UID": "c94254c37d734085"},
        "InstalledVersion": "2.2.0",
        "FixedVersion": "2.2.4",
        "Status": "fixed",
        "Title": "Django: SQL injection in key and index lookups",
        "Description": "An issue was discovered in Django 1.11.x before 1.11.23.",
        "CVSS": {"ghsa": {"V3Vector": GHSA_VECTOR, "V3Score": 9.8}},
    }
    entry.update(overrides)
    return entry


def trivy_report_of(*records) -> dict:
    """Wrap advisory records in the envelope a Trivy report carries them in."""
    target = {"Target": "requirements.txt", "Type": "pip", "Vulnerabilities": list(records)}
    return {"SchemaVersion": 2, "Results": [target]}
