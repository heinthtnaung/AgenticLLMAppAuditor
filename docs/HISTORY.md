# Build history

What was built, in order. One line each. Full reasoning is in git before
commit `8c3f9f6`.

| Phase | What shipped |
|---|---|
| 1 | LLM surface extractor. Python via `ast`, JS/TS via tree-sitter. `surfaces.json`. |
| 2 | SBOM (Syft), AIBOM, and the surface-to-component mapping. `sbom.json`, `aibom.json`, `mapping.json`. |
| 3 | Static checks under a bounded LangGraph planner. `findings.json`, `report.md`. |
| 4 | Scoring against hand-written grading keys, plus two baselines. `evaluation.json`. |
| 5 | Fetch a repository by URL; export HTML and PDF; emit OpenVEX. |
| 6 | Remediation advice grounded in a pinned OWASP knowledge base (ChromaDB). `remediation.json`. |
| 7 | LLM planner and the semantic prompt-injection probe. `planner.json`. |
| — | Advisory ingestion (Trivy) folded into Phase 2/3. |

## Decisions that still bind

- **The auditor never executes the audited app.** Enforced by
  `test_no_mutation.py` and `test_no_write_commands.py`.
- **The audit opens no socket** except to local Ollama. `model_client.py` is the
  only module that connects.
- **The model never decides what counts as a finding.** It writes advice, may
  order and narrow the plan, and judges prompt templates behind an opt-in flag.
- **No rate is a field in `evaluation.json`.** Counts and denominators only.
- **The pinned corpus was removed 2026-09-04.** Grading keys replace it: a key
  describes a public app this project does not ship.

## Reversals

- **Phase 7 task 7.4** overturned "the planner may never subtract", on the
  proposal's authority. Narrowing is allowed and recorded in
  `checks_narrowed`; five rules stop it becoming a silent claim.
- **VEX filtering** was declared out of scope; only emitting shipped.
- **The sandbox** for `probe_injection` was refused. See `REPORT.md`.
