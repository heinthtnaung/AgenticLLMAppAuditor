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
| `evaluation.json` | 4 | scores against grading keys |

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
| `evaluation.system` | `agentic_auditor` `baseline_static_rules` `baseline_sbom_only` `cloud_auditor` |
| `ground_truth.source` | `ai_drafted` `manual_review` `tool_drafted` `upstream_docs` |

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

**Discovery is non-recursive, and that is a contract.** `discover_graded_apps`
globs one level, so `grading_keys/drafts/` is invisible to it, to
`evaluate.py`, to `fetch_repo.check_not_a_graded_app` and to `emit_vex`. That is
what lets the auditor draft a key without enrolling the app against it. Three
modules depend on it; changing the glob to `rglob` breaks all three silently.

Drafts also carry `expected_surfaces` (what the extractor found, so a miss can
be told from a bad find), a per-entry `code_anchor` read from the source rather
than asked of the model, and entries sorted by `(file, line, id)`. A draft that
lacks any of those is refused by `promote_key.py` rather than moved.

**`source` is validated against the vocabulary**, not merely required: a typo
used to be accepted and earn no qualification at all. `ai_drafted` and
`tool_drafted` both earn `key_ai_drafted`; `tool_drafted` earns
`key_drafted_by_scored_system` as well and may never be `verified: true`, since
a tool cannot verify the key it wrote for itself. That qualification is about
**validity, not quality** — it survives a human checking every entry, because
checking cannot make the tool's own choice of what to include independent.

Schema 3 widened `source`. The check is exact equality, so a version-2 key is
refused rather than read by a scorer whose vocabulary has moved under it.

## Study output, not an audit artifact

`model-comparison.json` and `comparison.html`, written by
`experiments/compare_models.py` beside the audit's artifacts. **Deliberately
absent from the table above**, because it fails all three rules those rows
share: it is not produced by `src/`, it is not byte-identical (the hosted arm
takes no `seed` and `seconds` is wall clock), and it cannot be produced offline
or without a key.

It still carries `schema_version` — 1. Nothing validates it, because nothing
reads the document back: it is written once and rendered from memory, and a
loader with no reader would be dead code. The field is there because the shape
has already changed once silently — two incompatible files sit in the untracked
`experiments/results/` with nothing to tell them apart, and the next reader
should not have to guess.

```
schema_version  repository  subjects_seen  arms
agreements      disagreements
not_put_to_a_model  not_examined_by_every_arm  unmeasurable_exposure
```

- **The four buckets partition `subjects_seen`**, and the producer raises if
  they do not. Only subjects every arm actually put to its model can agree or
  disagree; `not_put_to_a_model` holds the ones the probe settled on the text
  alone, or where no model answered, each with a reason. Counting those as
  agreement is how a run that consulted nobody reported "agree on 1 of 1".
- **`not_examined_by_every_arm` takes precedence**: the planner may narrow the
  probe per arm, and a subject one arm never saw is not comparable whatever the
  others concluded.
- **The one join on `Probe.detail` in the project.** `agreement.py` tells a
  template refuted from its own text apart from one a model called safe. Both
  are `refuted` carrying no reason — `Probe.__post_init__` forbids a reason on a
  concluded outcome — so the sentence is the only marker. It joins on
  `semantic_probe.STATIC_REFUTATION`, a constant `src/` owns rather than model
  prose, and `tests/checks/test_semantic_probe_static_refutation.py` pins the
  two together. A second such join would mean the field is carrying a
  vocabulary and should be given one.
- **`exposure.field_kinds_transmitted` is derived, never asserted.** It comes
  from `prompt_kinds` — the kinds of prompt actually recorded — because the
  planner and the probe share one seam and carry different things.

## evaluation.json

Counts only. `apps[]` carries `true_positives`, `false_negatives`,
`false_positives` (null when the key does not claim completeness),
`matched_key_ids`, `misses` with a reason each, `qualifications`, and
`evidence` — how many findings carry a code, SBOM or VEX link, with the
denominator beside it.

Miss reasons: `no_check_for_risk_class`, `surface_not_extracted`,
`checked_and_silent`, `probe_unresolved`.
