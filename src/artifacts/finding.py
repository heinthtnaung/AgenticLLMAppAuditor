"""Data model for one audit finding and one probe result.

A finding must cite the evidence that produced it. That is enforced here rather
than reviewed for: a finding with nothing behind it cannot be constructed, so
it can never reach the artifact Phase 4 grades.
"""

from dataclasses import dataclass

from artifacts.repo_path import is_repo_relative_posix

# Artifact schema version. Bump it whenever a field changes, or one of the
# vocabularies this module *declares* -- OWASP_IDS, DETECTIONS, PROBE_OUTCOMES,
# PROBE_REASONS, SUBJECT_KINDS. A new `rule_id` is not one of them: it is fixed
# per producer, unvalidated here, and adding a check adds no field. Three checks
# shipped together at version 1 without a bump for that reason.
# Version 4 added the four advisory_* finding fields and the four advisory_*
# coverage fields, null everywhere except the known_advisory check. Version 5
# added coverage.advisory_unreached_components, the itemization of the count
# beside it, so the report can name the vulnerable-but-unreached components.
# Version 6 added the finding field advisory_severity -- the severity word
# quoted from the named source beside the CVSS vector -- and evolved each
# advisory_unreached_components item to {purl, advisories:[{id, severity}]}.
# Version 7 added the top-level `checks_narrowed`: which checks examined only
# some of their eligible surfaces, because the planner's model chose so.
SCHEMA_VERSION = 7

# The risks this project reports, from the 2025 OWASP Top 10 for LLM
# Applications. LLM02 is here because a grading key uses it: omit it and that
# finding is unrepresentable and scores as a miss the tool could never fix.
OWASP_IDS = ("LLM01", "LLM02", "LLM03", "LLM06", "AUDITABILITY")

# How a finding was reached *this run*. The grading key's `either` describes
# what could in principle reach it, so the tool never emits that value.
STATIC = "static"
PROBE = "probe"

# The one rule allowed to carry advisory fields; the check module re-exports it.
ADVISORY_RULE = "known_advisory"
DETECTIONS = (STATIC, PROBE)

# What a check concluded. `not_run` and `inconclusive` exist so "we did not
# look" stays distinct from "we looked and found nothing".
CONFIRMED = "confirmed"
REFUTED = "refuted"
INCONCLUSIVE = "inconclusive"
NOT_RUN = "not_run"
PROBE_OUTCOMES = (CONFIRMED, REFUTED, INCONCLUSIVE, NOT_RUN)

# Why a check reached no conclusion. Required whenever it did not.
PROBE_REASONS = (
    "trace_left_static_analysis",
    "app_not_runnable",
    "step_cap_reached",
    "model_unavailable",
)

# What a check ran against.
SURFACE_SUBJECT = "SURFACE"
COMPONENT_SUBJECT = "COMPONENT"
SUBJECT_KINDS = (SURFACE_SUBJECT, COMPONENT_SUBJECT)

# An outcome that leaves nothing concluded, so it must carry a reason.
UNRESOLVED_OUTCOMES = (INCONCLUSIVE, NOT_RUN)


@dataclass(frozen=True)
class Probe:
    """One check that ran, or was planned and did not.

    `detail` is descriptive only, like a surface's: nothing may join on it.
    """

    probe_name: str
    subject_kind: str
    subject_id: str
    outcome: str
    detail: str
    reason: str | None = None

    def __post_init__(self) -> None:
        """Reject a probe record a later phase could not act on."""
        if self.outcome not in PROBE_OUTCOMES:
            raise ValueError(f"unknown probe outcome {self.outcome!r}; expected {PROBE_OUTCOMES}")
        if self.subject_kind not in SUBJECT_KINDS:
            raise ValueError(f"unknown subject kind {self.subject_kind!r}; expected {SUBJECT_KINDS}")
        if not self.subject_id:
            raise ValueError("probe subject_id must not be empty")
        if self.outcome in UNRESOLVED_OUTCOMES and self.reason not in PROBE_REASONS:
            raise ValueError(f"{self.outcome} needs a reason from {PROBE_REASONS}, got {self.reason!r}")
        if self.outcome not in UNRESOLVED_OUTCOMES and self.reason is not None:
            raise ValueError(f"{self.outcome} concluded, so it carries no reason")

    @property
    def id(self) -> str:
        """Stable handle for a finding to cite. Opaque: never parsed."""
        return f"{self.probe_name}:{self.subject_id}"


@dataclass(frozen=True)
class Finding:
    """One conclusion, and the evidence that produced it.

    `owasp_id`, `title`, `file` and `line` are never model-authored: the first
    two are constants on the rule that raised it, and the last two are copied
    from the surface. Classification is what Phase 4 scores, so a model
    choosing it would be grading its own work.
    """

    owasp_id: str
    rule_id: str
    title: str
    detection: str
    surface_id: str | None = None
    surface_kind: str | None = None
    surface_name: str | None = None
    file: str | None = None
    line: int | None = None
    purl: str | None = None
    component_name: str | None = None
    mapping_reason: str | None = None
    probe_id: str | None = None
    narrative: str | None = None
    # Only the known_advisory check sets these: a CVE/GHSA id, the fix the
    # database names, a CVSS vector quoted verbatim, the severity word from the
    # same source, and that source. The severity is a *quotation* ("ghsa rates
    # this HIGH"), carried only beside its source -- never this tool's own pick.
    advisory_id: str | None = None
    advisory_fixed_version: str | None = None
    advisory_cvss_vector: str | None = None
    advisory_severity: str | None = None
    advisory_cvss_source: str | None = None

    def __post_init__(self) -> None:
        """Refuse a finding that cites nothing, or that copies its surface wrongly."""
        if self.owasp_id not in OWASP_IDS:
            raise ValueError(f"unknown owasp id {self.owasp_id!r}; expected one of {OWASP_IDS}")
        if self.detection not in DETECTIONS:
            raise ValueError(f"unknown detection {self.detection!r}; expected one of {DETECTIONS}")
        if not self.rule_id or not self.title:
            raise ValueError("a finding needs a rule_id and a title")
        self._check_evidence()
        self._check_surface_copy()
        self._check_advisory_fields()

    def _check_evidence(self) -> None:
        """A finding with nothing behind it is not constructible."""
        if not any((self.surface_id, self.purl, self.component_name, self.probe_id)):
            raise ValueError("a finding must cite a surface, a component or a probe")
        if self.detection == PROBE and not self.probe_id:
            raise ValueError("a probe finding must name the probe that confirmed it")
        if self.detection == STATIC and self.probe_id:
            raise ValueError("a static finding names no probe")

    def _check_surface_copy(self) -> None:
        """A cited surface is copied whole, so Phase 4 never parses an id."""
        copied = (self.surface_kind, self.surface_name, self.file, self.line)
        if self.surface_id and not all(x is not None for x in copied):
            raise ValueError(f"{self.surface_id} must copy its kind, name, file and line")
        if self.file is not None and not is_repo_relative_posix(self.file):
            raise ValueError(f"finding file must be a repo-relative posix path, got {self.file!r}")
        if self.line is not None and self.line < 1:
            raise ValueError(f"finding line must be 1 or greater, got {self.line}")

    def _check_advisory_fields(self) -> None:
        """Advisory fields belong to the advisory check alone, both directions."""
        if (self.advisory_id is None) != (self.rule_id != ADVISORY_RULE):
            raise ValueError(
                f"advisory_id and rule_id {ADVISORY_RULE!r} come together; got "
                f"advisory_id={self.advisory_id!r} with rule_id={self.rule_id!r}")
        extras = (self.advisory_fixed_version, self.advisory_cvss_vector,
                  self.advisory_severity, self.advisory_cvss_source)
        if self.advisory_id is None and any(x is not None for x in extras):
            raise ValueError("advisory evidence fields need an advisory_id behind them")
        # The severity word is a quotation, so it never appears without the
        # source that attributes it -- otherwise it reads as this tool's rating.
        if self.advisory_severity is not None and self.advisory_cvss_source is None:
            raise ValueError("advisory_severity needs advisory_cvss_source to attribute it")

    @property
    def id(self) -> str:
        """Derived from what the finding is, never a counter, and unique per document.

        The anchor is already unique -- a surface id is file:line:kind:name --
        so the rule is all that need be added. Two findings sharing both are the
        same finding twice.
        """
        anchor = self.surface_id or self.component_name or self.purl or self.probe_id
        if self.advisory_id:
            # One surface reaching one component with three advisories is three
            # findings, so the advisory id is part of what the finding *is*.
            return f"{anchor}:{self.rule_id}:{self.advisory_id}"
        return f"{anchor}:{self.rule_id}"


def sort_key(finding: Finding) -> tuple:
    """Order findings so the same evidence always serialises the same way."""
    return (finding.file or "", finding.line or -1, finding.owasp_id,
            finding.rule_id, finding.surface_id or "", finding.purl or "",
            finding.advisory_id or "")


def is_located(finding: dict) -> bool:
    """Say whether a finding points at a line of the audited source.

    One definition, imported by both `report.py` (which renders "no code
    location") and `evaluation/evidence.py` (which counts code evidence). It
    lived in both as a local expression until the two were noticed disagreeing
    at the boundaries: `line` is checked against `None` rather than for
    truthiness, because line 0 is a location and a falsy one.
    """
    return bool(finding.get("file")) and finding.get("line") is not None

