# Artifact contracts

Every artifact is JSON with a fixed schema and its own `schema_version`. Change
one and you update every reader. Full prior wording is in git before commit
`c10daa0`.

| Artifact | Version | Holds |
|---|---|---|
| `surfaces.json` | 3 | LLM surfaces + files skipped |
| `sbom.json` | 3 | packages, with how each version was established |
| `sbom.cyclonedx.json` | — | the same scan in CycloneDX |
| `aibom.json` | 1 | models, tools, agents, datasets, MCP servers |
| `mapping.json` | 2 | surface → component, and why |
| `findings.json` | 7 | findings, probes, coverage |
| `findings.sarif.json` | — | findings re-emitted as SARIF |
| `findings.openvex.json` | — | OpenVEX, written by `emit_vex.py` |
| `remediation.json` | 2 | per-finding advice + what grounded it |
| `planner.json` | 2 | the check order and what chose it |
| `evaluation.json` | 3 | scores against grading keys |

## Rules that hold across all of them

- **Deterministic.** Same input, same bytes. Records sorted, keys sorted, no
  timestamps, paths repository-relative POSIX.
- **Three exceptions, all model-authored, all inert by default**:
  `findings.json`'s prose fields and its probe records, `remediation.json`'s
  advice, and `planner.json`'s `order`.
- **No rate is ever a field in `evaluation.json`.** Counts and denominators
  only, so no number can be quoted without what it is out of.

## Vocabularies

Closed sets. Adding a value bumps the artifact's `schema_version`.

| Field | Values |
|---|---|
| `Surface.kind` | `PROMPT_TEMPLATE` `AGENT_DEF` `TOOL_CALL` `DATA_SOURCE` |
| `Finding.owasp_id` | `LLM01` `LLM02` `LLM03` `LLM06` `AUDITABILITY` |
| `Finding.detection` | `static` `probe` |
| `Probe.outcome` | `confirmed` `refuted` `inconclusive` `not_run` |
| `Probe.reason` | `trace_left_static_analysis` `app_not_runnable` `step_cap_reached` `model_unavailable` |
| `mapping.reason` | `third_party` `stdlib` `first_party` `used_but_undeclared` `unresolved` |
| `aibom.kind` | `MODEL` `TOOL` `AGENT` `DATASET` `MCP_SERVER` |
| `model_run.status` | `used` `unavailable` `disabled` |

`LLM02` is the **2023** spelling of improper output handling; 2025 numbers it
LLM05. Every other id is 2025.

## findings.json

```
schema_version   coverage        model_run       probe_count
checks_narrowed  probes          finding_count   findings
```

- **`coverage.checks_run`** — checks that had something to examine, sorted.
  Absent means "could not look at all", which the scorer reads as
  `no_check_for_risk_class`. A name here no longer implies *every* surface: see
  `checks_narrowed`.
- **`checks_narrowed`** — `{check, examined_surface_count, eligible_surface_count}`
  per narrowed check, `[]` when none. Top level, not inside `coverage`, because
  `sarif.py` copies `coverage` wholesale into an artifact published as
  byte-identical. `examined` counts surfaces *handed to* the check, not subjects
  found. An entry where examined equals eligible is refused, so `[]` is a
  reliable test.
- **`finding_id`** — `{surface_id|component_name|purl|probe_id}:{rule_id}`, plus
  `:{advisory_id}` when set. Unique within the document.
- **A `probe` finding must cite a `confirmed` probe.** Enforced at build time
  and again at render.
- **`advisory_*` fields are non-null iff `rule_id == known_advisory`.** Severity
  is quoted from a named source, never this tool's own rating.

## Grading keys

`grading_keys/<app>.ground_truth.json` + `.manifest.json`. The manifest must
pin `upstream_commit`; a key without one is refused.

Entry fields: `id` `file` `line` `owasp_id` `llm_surface` `surface_name`
`component` `detection` `title` `description` `code_anchor`.

Two that silently weaken the join if wrong: `llm_surface` is compared against
the finding's `surface_kind`, and **`component` is compared against the
finding's `purl`** — so a bare package name never matches, and an undeclared
package must leave it `null`.

`verified: false` means the scorer attaches `key_unverified` to every figure. A
run against `false` is not thesis-grade and says so.

## evaluation.json

Counts only. `apps[]` carries `true_positives`, `false_negatives`,
`false_positives` (null when the key does not claim completeness),
`matched_key_ids`, `misses` with a reason each, `qualifications`, and
`evidence` — how many findings carry a code, SBOM or VEX link, with the
denominator beside it.

Miss reasons: `no_check_for_risk_class`, `surface_not_extracted`,
`checked_and_silent`, `probe_unresolved`.
