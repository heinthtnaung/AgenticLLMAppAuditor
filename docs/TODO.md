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

- **Inline messages are matched on one key, `content`.** Every mainstream chat
  API spells it that way, but a provider that does not -- or a wrapper building
  `{"text": ...}` -- extracts nothing, and the artifacts cannot tell that from
  an app with no prompts. Same shape as the two blindspots that hid LLM01 on
  `indirect-prompt-injection-poc`: absence of a surface is indistinguishable
  from absence of a defect.

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
- Tests import private helpers where a public path exists; the study's tests add
  `_arm`, `_note` and `_check_partition`, whose only public path opens sockets.
- Many files sit over the ~200-line rule -- 31 under `tests/`, plus
  `src/checks/semantic_probe.py` (284). `tests/semantic_probe_fixtures.py` (240)
  grew here, by sharing the static-refutation app rather than copying it.

- **Objective 5 needs repeating, and one of its figures is withdrawn.**
  - The exposure byte count is gone from `docs/REPORT.md`: it counted the
    planner's prompt as a probe prompt, and "one request per prompt template"
    was never true (3 requests for 5 templates in the saved run). Re-measure it
    over an app that has prompt templates.
  - The agreement counts moved. `agreement.py` now excludes subjects no model
    was asked about, which turned the saved three-arm run from "agree on 5 of 5"
    into "agree 2, no model asked 3". Any figure quoted from the old shape is
    wrong.
  - It is still **one run per app**, and hosted models take no `seed` —
    `glm-5.2` gave different verdicts on the same template across runs.
  - `damn-vulnerable-llm-agent` can no longer serve as the comparison app: its
    one template interpolates nothing, so the probe refutes it statically and
    neither model is ever asked.

- **`--compare-models` narrowed the offline guarantee.** `src/` now holds two
  modules that can open a socket, not one. `cloud_client` is constructed only
  behind the flag and a test proves a default audit still attempts nothing but
  Ollama -- but the sentence a reader remembers is weaker than it was, and that
  was bought deliberately.
- **The `cloud_auditor` arm is not reproducible.** A hosted model takes no seed,
  so `artifacts/cloud_auditor/` breaks the byte-identical rule every other
  artifact keeps. Exempted in `docs/SCHEMAS.md` rather than fixed; it cannot be
  fixed from this side.
- **`--artifacts-dir` half-applies under `--compare-models`**: the local arm
  follows it, the cloud arm is always `artifacts/cloud_auditor/`.
- **One of four model-driven stages stays local under `--compare-models`**: the
  knowledge-base embeddings (`retrieval/retrieve.py`). Threading the ask through
  it would make the cloud arm whole.
- **A drafted key is bounded above by the extractor.** The model is shown the
  extracted surfaces and `draft` drops any entry naming a file, line or risk
  class it was not shown, so such a key can never falsify the extractor. The
  output does not record that ceiling.
- **Drafted keys live under `grading_keys/drafts/`, which is gitignored**, so a
  figure scored against one is unreproducible from a clean checkout until a
  human promotes it. Acceptable only because `tool_drafted` makes the number
  self-describing.
- **A tool-drafted key a human has checked cannot be represented.** Schema 3
  forbids `tool_drafted` with `verified: true`, so promotion cannot clear
  `key_unverified` without also changing `source` -- which clears
  `key_drafted_by_scored_system` too, and that one is meant to survive. The
  vocabulary needs a fourth state or the pairing needs relaxing.

## Blocked on a decision

- **The `pct_*` fields were requested and refused.** `evaluation.json` forbids
  float fields and two tests pin "no rate in stdout". Shipped instead: counts,
  denominators and `apps_included`. To overrule: six documents and two guards
  change, and the guard is weaker permanently.
- **Objective 5 was dropped, then reinstated 2026-09-05** when API access was
  supplied, and is now measured. The original refusal stands in
  `docs/REPORT.md` and is not deleted: what changed is access, not the
  reasoning.
- **The sandbox for `probe_injection` was refused.** Reasons in
  `docs/REPORT.md`; two are about coherence, not cost.
- **The grading key is AI-drafted and unverified.** Every figure carries
  `key_ai_drafted` and `key_unverified` until a human checks its eight entries
  against commit `c0cf9a14`. Cheapest remaining upgrade in the project.
