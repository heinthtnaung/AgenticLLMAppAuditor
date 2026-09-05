# Open work

Ticked history is in git before commit `a78482c`; what shipped is in
`docs/HISTORY.md`. This file is only what is *not* done.

## Known defects

| Where | What |
|---|---|
| `checks/known_advisory.py` | A component whose version the SBOM cannot establish gets a versionless purl, but Trivy indexes advisories by versioned purl. They never join, so the component is published as **unreached** — a positive claim of safety from a version gap. |
| `checks/output_handling.py` | Judges only the argument expression. `q = f"SELECT {x}"` then `execute(q)` is silent, and so is `.format_map`. Pinned by tests. |
| `checks/output_handling.py` | `%` is judged by shape: `execute("SELECT %s" % ("lit",))` is reported, `% "lit"` is not. Arbitrary. |
| `artifacts/aibom.py` | `_kind_of` reads Python's name tables whatever the language, so the import guards cover the Python backend only. |
| `artifacts/aibom.py` | An MCP client given `name=` files as `TOOL`, not `MCP_SERVER`. Shape-versus-membership, same family as the dataset gap. Strict xfail. |
| `artifacts/vex.py` | Subscripts `finding["purl"]` unguarded, then sorts. A future advisory producer omitting it would sort `str` against `None`. |
| `checks/workflow.py` | `act` dispatching `undeclared_dependency` with a null mapping dies as `AttributeError`, not a clear error. Unreachable today. |
| `coverage.checks_run` | Means "was dispatched" for a graph check and "found a subject" for the edge check, so a model can move the probe between them. Strict xfail. |
| `evaluation.json` | `model_disabled` fires on `unavailable` too, collapsing "turned off" and "unreachable". |
| Scoring | Nothing version-gates `findings.json`, so a stale artifact scores silently against fresh code. |

## Open tasks

- Teach `evaluation/scorer.py` about `checks_narrowed`, so a key entry at a
  surface the planner skipped is not scored as an ordinary miss. Phase 4 change;
  needs a re-measure. **Not with per-surface probes** — `scorer.py` keys its
  probe map on `(file, line)` and would attribute one skip to every entry on
  that line.
- Report `executescript` beside `execute` and `executemany`. Needs a detector
  entry first; the import guard refuses a method no detector emits.
- Python lockfiles: `Pipfile.lock` is JSON and ships on the stdlib today;
  `poetry.lock` and `uv.lock` need `tomllib`, which is 3.11+ against a declared
  3.10 floor. **Decide the floor.**
- Grading-key entries for `known_advisory`, and the before/after re-measure that
  advisory ingestion was supposed to produce.
- Score surface extraction as its own precision/recall figure.
- MITRE ATLAS as a second knowledge source (Phase 6 task 6.5).
- Make the two languages agree about `ToolNode` — Python files it as a tool, JS
  as an agent, so one construct extracts as two kinds.
- `owasp_reference.REFERENCES["LLM02"]` describes model output reaching a sink,
  which `output_handling.py` explicitly disclaims. The finding title is honest
  and the advice prompt beside it is not.
- Five tests import a private helper where a public path exists.
- Three test files sit just over the ~200-line rule.

## Blocked on a decision

- **The `pct_*` fields were requested and refused.** `evaluation.json` forbids
  float fields and two tests pin "no rate in stdout". Shipped instead: counts,
  denominators and `apps_included`. To overrule: six documents and two guards
  change, and the guard is weaker permanently.
- **Objective 5 was dropped** — no funded API access, and running it means
  transmitting audited source to a provider, which is the exposure this project
  argues against. Stated in `docs/REPORT.md`.
- **The sandbox for `probe_injection` was refused.** Reasons in
  `docs/REPORT.md`; two are about coherence, not cost.
- **The grading key is AI-drafted and unverified.** Every figure carries
  `key_ai_drafted` and `key_unverified` until a human checks its six entries
  against commit `c0cf9a14`. Cheapest remaining upgrade in the project.
