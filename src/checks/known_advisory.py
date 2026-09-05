"""Reports a known advisory against a component an LLM surface actually reaches.

Distinct from `undeclared_dependency`, which is hygiene: a package can be
declared, pinned and honestly recorded and still be dangerous. This check says
which of those dangers are *reachable* -- one finding per (surface, component,
advisory), anchored on the surface so the finding has a file and a line a
grading key can score.

Everything nothing reaches is counted, never silently dropped: an advisory in
a component no surface touches is exactly what a maintainer's
`vulnerable_code_not_in_execute_path` statement asserts, and the count is the
evidence such a statement needs.

The advisory data arrives already in this project's vocabulary
(`deps/trivy_runner.py:advisory_index`), so this module never learns whose
report it was. It runs nothing: it joins two documents.
"""

from artifacts.finding import ADVISORY_RULE, STATIC, Finding

CHECK_NAME = ADVISORY_RULE
OWASP_ID = "LLM03"
TITLE = "Known vulnerability in a component an LLM surface reaches"

def _reached(mapping_document: dict) -> list[dict]:
    """The mapping entries a surface joined to a component: purl is the proof."""
    return [entry for entry in mapping_document["entries"] if entry.get("purl")]


def find_known_advisories(mapping_document: dict | None,
                          advisories: dict[str, list[dict]] | None,
                          fields_by_surface: dict[str, dict]) -> list[Finding]:
    """One finding per (surface, component, advisory), anchored on the surface."""
    if mapping_document is None or advisories is None:
        return []
    found = []
    for entry in _reached(mapping_document):
        for record in advisories.get(entry["purl"], []):
            found.append(_finding(entry, record, fields_by_surface[entry["surface_id"]]))
    return found


def _finding(entry: dict, record: dict, surface: dict) -> Finding:
    """Cite everything a reader needs to check the claim themselves.

    `record` is already in Finding's own field names, `surface` likewise, so
    the join contributes only what the join itself established.
    """
    return Finding(
        owasp_id=OWASP_ID, rule_id=CHECK_NAME, title=TITLE, detection=STATIC,
        surface_id=entry["surface_id"], purl=entry["purl"],
        component_name=entry["component_name"], mapping_reason=entry["reason"],
        **record, **surface,
    )


def unreached_components(mapping_document: dict | None,
                        advisories: dict[str, list[dict]] | None) -> list[dict] | None:
    """The advisory-carrying components no surface reaches, each with its advisory ids.

    Real vulnerabilities, deliberately *not* scored findings: a finding is a
    reachability claim, and nothing reaches these. But the reader still gets to
    see them -- a report that only counted them read as clean. Each item is the
    component purl and its advisories, each `{id, severity}` -- the severity
    quoted from Trivy's named source, never one of ours. None when there is no
    mapping or no advisory data to compute reach from.
    """
    if mapping_document is None or advisories is None:
        return None
    reached = {entry["purl"] for entry in _reached(mapping_document)}
    return [
        {"purl": purl,
         "advisories": sorted(
             ({"id": r["advisory_id"], "severity": r.get("advisory_severity")}
              for r in advisories[purl]), key=lambda a: a["id"])}
        for purl in sorted(set(advisories) - reached)
    ]


def unreached_component_count(mapping_document: dict | None,
                              advisories: dict[str, list[dict]] | None) -> int | None:
    """How many advisory-carrying components no surface reaches. None = no data."""
    unreached = unreached_components(mapping_document, advisories)
    return None if unreached is None else len(unreached)
