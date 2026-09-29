"""The components and advisories the finding tests join, built by hand.

No test runs Syft or Trivy. Each builder makes the record the runners produce,
so a test states only the part it is about. The vectors are the ones the real
sources published, including the two versions this calculator refuses.

Named `finding_samples` and not `samples`: pytest puts each test directory on
the path and imports by basename, so a second `samples.py` would be shadowed by
`tests/deps/samples.py` and the import would fail on a name that does exist.
"""

from deps.syft_report import Component
from deps.trivy_report import Advisory

DJANGO_PURL = "pkg:pypi/django@2.2.0"
PYYAML_PURL = "pkg:pypi/pyyaml@5.1"

# CVE-2019-14234, as the sources in the saved Trivy report scored it: Red Hat
# reads the flaw as low-impact information disclosure where GHSA and NVD read it
# as total loss of confidentiality, integrity and availability.
GHSA_VECTOR = "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
GHSA_SCORE = 9.8
REDHAT_VECTOR = "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"
REDHAT_SCORE = 5.3

# CVE-2025-37164: one CVE, two published scorings, one metric apart.
CNA_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
CNA_SCORE = 10.0
TENABLE_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
TENABLE_SCORE = 9.8

# A vector worth 0.0, which is a score and not the absence of one.
HARMLESS_VECTOR = "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:N/I:N/A:N"
HARMLESS_SCORE = 0.0

# Published vectors this calculator refuses: real records, not broken scans.
VERSION_2_VECTOR = "AV:N/AC:L/Au:N/C:P/I:P/A:P"
VERSION_4_VECTOR = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"


def component(**overrides) -> Component:
    """Build one component in the shape the Syft runner gives it."""
    fields = {
        "name": "django",
        "version": "2.2.0",
        "purl": DJANGO_PURL,
        "ecosystem": "python",
        "locations": ("/requirements.txt",),
    }
    fields.update(overrides)
    return Component(**fields)


def advisory(**overrides) -> Advisory:
    """Build one advisory in the shape the Trivy runner gives it."""
    fields = {
        "advisory_id": "CVE-2019-14234",
        "purl": DJANGO_PURL,
        "fixed_version": "2.2.4",
        "summary": "Django: SQL injection in key and index lookups",
        "details": "An issue was discovered in Django 1.11.x before 1.11.23.",
        "vectors": {"ghsa": GHSA_VECTOR},
    }
    fields.update(overrides)
    return Advisory(**fields)


def index(*advisories: Advisory) -> dict[str, tuple[Advisory, ...]]:
    """Index advisories by purl, the way the Trivy runner hands them over."""
    grouped: dict[str, tuple[Advisory, ...]] = {}
    for entry in advisories:
        grouped[entry.purl] = (*grouped.get(entry.purl, ()), entry)
    return grouped
