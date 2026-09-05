# How a run works

```
repo (path or URL)
  └─ extract surfaces ............ surfaces.json
  └─ Syft → SBOM, AIBOM .......... sbom.json, aibom.json, sbom.cyclonedx.json
  └─ map surface → component ..... mapping.json
  └─ Trivy → advisories
  └─ plan, then run the checks ... findings.json, planner.json
  └─ render ...................... report.md, findings.sarif.json
  └─ advise (local model + RAG) .. remediation.json, remediation.md
```

Separate commands, by design — the audit path opens no socket and needs no
renderer: `emit_vex.py` (OpenVEX), `export_reports.py` (HTML/PDF),
`ai_report.py` (model-styled view), `evaluate.py` (scoring).

## The checks

Run inside a bounded LangGraph loop, one check per step, capped at
`MAX_STEPS = 20`.

| Check | Risk | Subject |
|---|---|---|
| `permissions` | LLM06 | tool surfaces |
| `taint` | LLM01 | data source → model |
| `output_handling` | LLM02 | `execute` calls |
| `auditability` | AUDITABILITY | agent constructors |
| `supply_chain` | LLM03 | the mapping |
| `known_advisory` | LLM03 | the mapping + advisories |
| `semantic_probe` | LLM01 | prompt templates (edge, opt-in) |

A check is named in `coverage.checks_run` only if it had something to look at.
Absent means "could not look", which the scorer reads as
`no_check_for_risk_class` — so absence is a claim, not a detail.

## The planner

Chooses the **order** checks run in, and since task 7.4 **which surfaces** each
examines. It never chooses which checks run, and never what counts as a finding.

Five rules stop a narrowing becoming a silent claim: a check the model does not
name examines everything; an empty selection is refused; a narrowing never takes
a check below one surface; surfaces the prompt never described always run; and
the two component-anchored checks are not narrowable at all. What each check
actually examined is in `findings.json`'s `checks_narrowed`.

The model is consulted at the **edge**, in `build_findings` — never inside a
graph node, because `tests/parsing/test_offline.py` asserts the graph *attempts*
no socket, counting attempts rather than successes.

## Boundaries

- **Four modules start a process**: `syft_runner`, `trivy_runner`, `fetch_repo`,
  and the vexctl launcher. Nothing else shells out.
- **One module opens a connection**: `model_client.py`, to local Ollama.
- **The audited tree is never written to.** `test_no_mutation.py` hashes it
  before and after.
