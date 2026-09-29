"""The words both pages give a secret: where it is, what matched it, and what none means.

Here once so the two pages cannot drift; how each lays them out stays with it.
None of it is the secret, which the record never holds (`deps.trivy_secrets`).
"""

from deps.trivy_secrets import SecretFinding

# Said under the heading when there is nothing to list, rather than leaving the
# section out. It names the rules, because they are all that looked: no match is
# not the same as no secret.
NONE_MATCHED = "Trivy's built-in secret rules matched nothing in this tree."
RULE_LABEL = "rule"


def location_of(secret: SecretFinding) -> str:
    """Name the file a secret is in and its line, or its first and last line."""
    if secret.start_line == secret.end_line:
        return f"{secret.target}:{secret.start_line}"
    return f"{secret.target}:{secret.start_line}-{secret.end_line}"


def described(secret: SecretFinding) -> list[str]:
    """Say what matched a secret, in the order both pages print it."""
    return [secret.severity, secret.title, secret.category, f"{RULE_LABEL} {secret.rule_id}"]
