"""The secrets in the audit artefact: where each one is and which rule matched it.

The record holds no secret to write (`deps.trivy_secrets`), so none of these
fields can carry one. They are in file and line order, as the record keeps them.
"""

from typing import Any

from report.record import Report


def secrets_of(report: Report) -> list[dict[str, Any]]:
    """Give every secret a rule matched, in the record's own order."""
    return [secret_of(one) for one in report.secrets]


def secret_of(secret: Any) -> dict[str, Any]:
    """Give one secret: the file, its lines, and the rule that matched it."""
    return {
        "file": secret.target,
        "start_line": secret.start_line,
        "end_line": secret.end_line,
        "rule_id": secret.rule_id,
        "category": secret.category,
        "severity": secret.severity,
        "title": secret.title,
    }
