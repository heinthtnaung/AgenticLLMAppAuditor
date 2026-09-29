"""Reading the secrets in a Trivy report: where each one is and which rule matched it.

The same offline run that finds the advisories finds these, so they are read
from the same document; `deps.trivy_report` reads the advisories out of it.

**The secret itself is never read.** Trivy masks it in `Match` and in the code
lines it quotes, but a mask is Trivy's promise and not this tool's, and the rest
of a quoted line can hold a second secret no rule matched. So neither field is
read: a `SecretFinding` has nowhere to carry a secret, and nothing downstream
can print one by accident.
"""

from dataclasses import dataclass
from itertools import chain
from typing import Any, Mapping

from deps.scanner import ScannerFailed
from deps.trivy_report import report_results

# Trivy's own field names, spelled out once here and nowhere else in the project.
TARGET = "Target"
SECRETS = "Secrets"
RULE_ID = "RuleID"
CATEGORY = "Category"
SEVERITY = "Severity"
TITLE = "Title"
START_LINE = "StartLine"
END_LINE = "EndLine"

NAMED_FIELDS = (RULE_ID, CATEGORY, SEVERITY, TITLE)


@dataclass(frozen=True)
class SecretFinding:
    """One secret a Trivy rule matched: the file, the lines, the rule and its severity."""

    target: str
    start_line: int
    end_line: int
    rule_id: str
    category: str
    severity: str
    title: str


def read_secrets(report: Any) -> tuple[SecretFinding, ...]:
    """Read every secret a Trivy report names, in file and line order."""
    found = chain.from_iterable(target_secrets(result) for result in report_results(report))
    return tuple(sorted(found, key=secret_order))


def target_secrets(result: Mapping[str, Any]) -> list[SecretFinding]:
    """Give one target's secrets, which Trivy omits when its rules matched nothing."""
    entries = result.get(SECRETS) or []
    if not entries:
        return []
    target = result.get(TARGET)
    if not isinstance(target, str) or not target:
        raise ScannerFailed(f"A Trivy result carrying {SECRETS!r} names no {TARGET!r}")
    if not isinstance(entries, list):
        raise ScannerFailed(f"The {SECRETS!r} of {target!r} must be a list")
    return [read_secret(target, entry) for entry in entries]


def read_secret(target: str, entry: Any) -> SecretFinding:
    """Translate one Trivy secret into where it is and what matched it, and nothing more."""
    if not isinstance(entry, Mapping):
        raise ScannerFailed(f"A Trivy secret in {target!r} must be a JSON object")
    start, end = read_line(target, entry, START_LINE), read_line(target, entry, END_LINE)
    if end < start:
        raise ScannerFailed(f"A Trivy secret in {target!r} ends before it starts")
    named = {name: read_name(target, entry, name) for name in NAMED_FIELDS}
    return SecretFinding(
        target=target,
        start_line=start,
        end_line=end,
        rule_id=named[RULE_ID],
        category=named[CATEGORY],
        severity=named[SEVERITY],
        title=named[TITLE],
    )


def read_line(target: str, entry: Mapping[str, Any], field: str) -> int:
    """Give one line number of a secret, refusing anything that is not a line."""
    # The value is not quoted back: a field of the wrong shape is no place to
    # guess what it holds.
    value = entry.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ScannerFailed(f"A Trivy secret in {target!r} has no line number in {field!r}")
    return value


def read_name(target: str, entry: Mapping[str, Any], field: str) -> str:
    """Give one of the rule's names for a secret, refusing a rule that gives none."""
    value = entry.get(field)
    if not isinstance(value, str) or not value:
        raise ScannerFailed(f"A Trivy secret in {target!r} carries no {field!r}")
    return value


def secret_order(secret: SecretFinding) -> tuple[str, int, int, str]:
    """Order secrets so two scans over one tree produce identical output."""
    return (secret.target, secret.start_line, secret.end_line, secret.rule_id)
