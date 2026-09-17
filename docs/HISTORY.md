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
| — | One grading key shipped from 2026-09-05, AI-drafted and unverified, eight entries after review; **removed 2026-09-06**, recoverable at `f9bd9ff`. |
| — | Objective 5: `experiments/` compares the local model against hosted ones. |
| — | `reproduce.sh` regenerated every figure in one command; replaced by `main.py --compare-models`, which audits with both models and scores both. |
| — | The comparison's exposure ledger was measuring nothing: `surfaces_described` held a constant label, not a measurement, and the field list was asserted rather than derived. |
| — | The comparison counted templates no model was asked about as agreement; `experiments/agreement.py` partitions them into four buckets that must sum. |
| — | `src/` may not import `experiments/`, and a test now asserts it rather than the README claiming it. |
| — | `--draft-key`: the local model drafts a grading key into `grading_keys/drafts/`, which nothing discovers and git ignores. `promote_key.py` accepts one after a human corrects it. |
| — | `--compare-models` audits a tree twice, local against hosted, and scores both. `cloud_client` moved into `src/`, so two modules there open a socket, not one. |
| — | `cloud_client` counts what leaves the machine; the total prints at the end of a comparison. |
| — | The AI-formatted report was deleted: model prose restating a report that was already authoritative. |
| — | Two parsing blindspots closed: a prompt held on `self`, and a chat-message dict written inline. Each made class-based and framework-free apps invisible to the prompt detector. |
| — | The taint trace follows a chain of any length, sees the module's names from inside a function, and looks through literal containers. Two of those were silent misses, not gaps. |
| — | `src/keys/`, `artifacts/names.py`, and `outputs.py` split by job: 177 lines doing four things became 57 doing one. |
| — | A web UI, in `web/` and `frontend/`, outside `src/` and imported by nothing in it. One FastAPI process serves both the built page and the API, so there is no CORS at all; the built page is committed, so running it needs Python and no Node. It renders `findings.json` and `surfaces.json` unmodified — a view, not a twelfth artifact. |
| — | The audit became a background job the page polls, so a run shows its stages advancing. `src/reporting/progress.py` gained `stage()` and a listener **handed in as an argument** — the CLI passes none and only gained stderr lines. |
| — | The web layer gained durable state of its own: `runs/history.sqlite3`, stdlib `sqlite3`, versioned by `PRAGMA user_version`, refusing rather than migrating. A History page lists past runs and reopens any one; a finished run stays readable after `artifacts/` is cleaned. `src/` does not know it exists, so a CLI audit writes no row. |
| — | Every file a run writes is downloadable, individually or as one archive, by allowlist only and always as an attachment. `artifacts/names.py` grew from the audit's eleven to all sixteen names, and `emit_vex.py` and `export_reports.py` now import theirs from it instead of keeping their own. |
| — | Light and dark, plus the machine's own preference, with every colour routed through a token so no palette can reach a value the other cannot. |
| — | A drafted grading key can be corrected in the browser, and a human check recorded on it. `source` is frozen and `verified` moves through a route of its own, so the pair can never travel together into a key that reads as human-authored. |

## Decisions that still bind

- **The auditor never executes the audited app.** Enforced by
  `test_no_mutation.py` and `test_no_write_commands.py`.
- **An audit opens no socket** except to local Ollama. Two modules in `src/`
  can connect, as an exact set: `model_client.py` to Ollama, and
  `cloud_client.py` to a hosted model, constructed only under
  `--compare-models`. That used to be one module, and the difference is a real
  reduction in what the tool guarantees. `experiments/` is the study, not the
  tool, and is barred from `src/` in both directions.
- **The model never decides what counts as a finding.** It writes advice, may
  order and narrow the plan, and judges prompt templates behind an opt-in flag.
  Behind `--draft-key` it drafts *ground truth*, which is the one place it
  decides what an audit is marked against -- so that is a flag, the draft lands
  where nothing discovers it, and every figure such a key produces is qualified.
- **No rate is a field in `evaluation.json`.** Counts and denominators only.
- **The pinned corpus was removed 2026-09-04.** Grading keys replace it: a key
  describes a public app this project does not ship.
- **No key ships now either.** `docs/REPORT.md`'s figures were measured against
  the one that did, so none of them is reproducible from a clean checkout, and
  `evaluate.py` refuses rather than scoring zero. Restoring or writing a key is
  what makes the measurement claim true again.

## Reversals

- **Phase 7 task 7.4** overturned "the planner may never subtract", on the
  proposal's authority. Narrowing is allowed and recorded in
  `checks_narrowed`; five rules stop it becoming a silent claim.
- **VEX filtering** was declared out of scope; only emitting shipped.
- **The sandbox** for `probe_injection` was refused. See `REPORT.md`.
- **`reproduce.sh`** was the single entry point for an examiner; deleted in
  favour of `main.py --compare-models`.
- **Key drafting ran on every URL audit** for one commit, then went behind
  `--draft-key`: a default run should be fast and produce the same artifacts
  whether a model was running or not.
- **"A tool-drafted key may never be verified"** was overturned on 2026-09-16.
  `harness.check_key` refused `tool_drafted` + `verified: true` outright, which
  conflated who *chose* the entries with whether a human had *read* them. The
  cost was concrete: a person who had checked every entry could say so only by
  editing `source`, which erases `key_drafted_by_scored_system` -- dropping the
  warning that matters to record a weaker one. The pairing is now legal, no
  schema version bumped (the valid set only widened, and an old reader refuses
  by name), and the scorer needed no change: verifying clears `key_unverified`
  alone, so a verified drafted key still carries both drafting qualifications
  and can never read as an independent measurement. Recorded through
  `POST /api/keys/{app}/verify` in the web editor; `promote_key.py` will not
  publish such a draft without `--accept-verification`, because that claim is
  made through an endpoint with no authentication.
