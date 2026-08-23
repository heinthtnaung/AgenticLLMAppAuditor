# Artifact schemas

Every phase hands data to the next one through JSON files. These are contracts:
a field is never renamed or removed without updating every reader in the same
change. `schema_version` is bumped when that happens.

Two conventions apply to every file here:

- **Paths are repo-relative POSIX** (`chatapp/backend/app/main.py`), never
  absolute and never with backslashes. This is what makes an artifact
  byte-identical on a different machine. `Surface` enforces it.
- **Output is deterministic.** Records are sorted, keys are sorted, and no
  timestamps or absolute paths are written. The same input always produces the
  same bytes.

## Where everything lives

`<app>` is the single join key across every row: the corpus directory name, the
artifact directory name, `ground_truth.app`, and `manifest.name`.

| Kind | Path | Written by |
|---|---|---|
| Audited code | `corpus/<app>/` | upstream, byte-identical, never written to. **Downloaded, not committed** — see the README |
| Grading key | `corpus/evidence/<app>.ground_truth.json` | hand-authored |
| Provenance, fixture | `corpus/evidence/<app>.manifest.json` | hand-authored |
| Regression snapshot | `corpus/evidence/<app>.baseline.json` | tool-derived |
| Phase 1 output | `artifacts/<app>/surfaces.json` | `src/main.py` |

`src/corpus_paths.py` owns these paths. Import them from there rather than
joining strings, so a later phase cannot guess wrong.

**`corpus/<app>/` is a byte-identical copy of upstream at `upstream_commit`.**
If a file with an evidence name ever appears inside it, that file is upstream's
own and must never be read. A test asserts none does.

These three files moved out of `corpus/<app>/` after Phase 1. No field changed
and `schema_version` stays 2: a relocation is not a record change, and because
the old paths no longer exist a stale reader fails loudly rather than reading
the wrong file.

---

## `artifacts/<app>/surfaces.json` — Phase 1 output

Produced by `src/main.py` via `surface.surfaces_to_json`. Read by Phase 2
mapping and Phase 3 auditing. `<app>` is the audited directory's name — see the table above for how
consumers find its grading key.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `2`. |
| `surface_count` | int | yes | `len(surfaces)`, so a reader can sanity-check at a glance. |
| `surfaces` | list | yes | Sorted by `(file, line, kind, name)`. May be empty. |

A repository with no LLM surfaces is a valid result, not an error: the file is
still written with `surface_count: 0` and an empty `surfaces` list, so Phase 4
can tell "audited, nothing found" apart from "never audited".

Each entry in `surfaces`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | str | yes | `"{file}:{line}:{kind}:{name}"`. The handle Phase 2/3 use to point at a surface. Derived from what the surface is, never from a list index, so adding a detector never renumbers anything. |
| `kind` | str | yes | One of `PROMPT_TEMPLATE`, `AGENT_DEF`, `TOOL_CALL`, `DATA_SOURCE`. |
| `name` | str | yes | Symbol, tool, or agent name from the AST. Never empty. |
| `file` | str | yes | Repo-relative POSIX path. |
| `line` | int | yes | `node.lineno`, 1 or greater. |
| `detail` | str | yes | Short human-readable note. **Descriptive only — not part of identity.** |
| `language` | str | yes | `python`, `javascript`, or `typescript`. Says which ecosystem's rules apply to `module`, so a consumer never has to re-derive it from the file extension. |
| `module` | str | yes (may be `""`) | **The import specifier exactly as the source wrote it** — a dotted path in Python (`langchain_experimental.sql`), an npm or builtin specifier in JS/TS (`@langchain/langgraph/prebuilt`, `node:fs/promises`). `""` for a relative import, which is the app's own code and has no SBOM component, and for a construct with no backing import. |

### Joining `module` to a package (Phase 2's job)

Phase 1 stores the specifier verbatim and knows nothing about npm or PyPI —
that is what keeps adding a third language cheap. Phase 2 applies the
ecosystem's package-root rule:

| `language` | Rule | Example |
|---|---|---|
| `javascript`, `typescript` | scoped (`@…`): first **two** segments; otherwise the first | `@langchain/community/tools/tavily_search` → `@langchain/community` |
| `python` | first dotted segment, then a distribution lookup | `langchain_experimental.sql` → `langchain-experimental` |

Truncating in Phase 1 would be lossy and irreversible, and the subpath is
itself a risk signal: `langchain_experimental.sql` is the dangerous submodule,
`langchain` is not.

**Identity is `(file, line, kind, name)`.** Two records matching on those four
are the same surface even if `detail` differs, and are collapsed by
`surface.deduplicate` before serialisation.

---

## `corpus/evidence/<app>.ground_truth.json` — Phase 1 input, Phase 4 grading key

Hand-authored (currently AI-drafted, see `verified`). Read by Task 1.7's tests
and by the Phase 4 scorer. This file is committed: the grading key is evidence.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `2`. |
| `app` | str | yes | Must equal the corpus directory name and the manifest's `name`. |
| `upstream_commit` | str | yes | The commit the line numbers are valid against. Must equal the manifest's `upstream_commit`. |
| `source` | str | yes | `ai_drafted`, `upstream_docs`, or `manual_review`. |
| `verified` | bool | yes | `false` until a human has checked it. **A scorer run against `false` is not thesis-grade and must say so loudly.** |
| `verified_by` | str \| null | yes | Who verified it; `null` while unverified. |
| `verified_date` | str \| null | yes | `YYYY-MM-DD`; `null` while unverified. |
| `finding_count` | int | yes | `len(findings)`. |
| `findings_complete` | bool | yes | `true` = the app is asserted to contain no other findings, so anything else reported is a false positive. `false` = recall only. |
| `expected_surfaces` | list | yes | Surfaces the extractor must find, independent of any finding. May be empty. |
| `expected_surface_count` | int | yes | `len(expected_surfaces)`. |
| `expected_surfaces_complete` | bool | yes | `true` = this is **every** surface in the app, so an extra extracted surface is a false positive. `false` = recall only. |
| `findings` | list | yes | Sorted by `(file, line, id)`. |

Each entry in `findings`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | str | yes | App-scoped label, e.g. `VULN1-02`. Cited in results tables — never renumbered. |
| `owasp_id` | str | yes | `LLM01`, `LLM02`, `LLM05`, `LLM06`, or `AUDITABILITY`. |
| `title` | str | yes | One line. |
| `description` | str | yes | One to three sentences: what is wrong, and why it is that class. |
| `file` | str | yes | Repo-relative POSIX path — **the same convention as `surfaces.json`**, because this is the join key. |
| `line` | int | yes | Anchor line at `upstream_commit`. |
| `line_end` | int \| null | no | End of a multi-line construct; `null` for one line. |
| `code_anchor` | str | yes | The first 60 characters of the trimmed source text at `line`. A test asserts the real line still *starts with* this, so line drift is caught without editing the fixture. |
| `llm_surface` | str \| null | yes | One of the four surface kinds, or `null` when the finding is not tied to a code surface (a dependency, for example). Task 1.7 asserts only over non-null values. |
| `surface_name` | str \| null | no | Expected `Surface.name`, for an exact assertion. |
| `component` | str \| null | no | PURL for supply-chain findings. Phase 2's SBOM join key. |
| `detection` | str | no | `static`, `probe`, or `either` — which class of check can reach it. Phase 4's baselines need this to state an achievable ceiling. |
| `notes` | str \| null | no | Free text, e.g. the upstream README section it came from. |

**Matching rule for Task 1.7 and the Phase 4 scorer:** a finding matches a
surface when the `file` is equal, the `llm_surface` kind is equal, and the
surface's line falls within `[line, (line_end or line) + LINE_TOLERANCE]` with
`LINE_TOLERANCE = 3`. Exact line equality is wrong here: a detector may
legitimately report a decorator line where a human noted the `def`.

Each `expected_surfaces` record mirrors a `Surface`: `id` (`SURF-01`, never
renumbered), `kind`, `name`, `file`, `line`, `line_end`, `code_anchor`, and
`module`. It deliberately carries **no** `owasp_id` or `description` — a
surface is not a vulnerability, and adding risk vocabulary here is exactly what
would poison the grading key.

**A clean app is a real result.** `finding_count: 0` with
`findings_complete: true` means "asserted clean", so recall is *undefined*, not
0% — a scorer must print `n/a`. Every finding reported against such an app is a
false positive. This is the only place the write-up can honestly claim a
false-positive rate.

**Known limitation, to be stated in the write-up:** exhaustiveness is only
claimed where `expected_surfaces_complete` is `true`. Today that is the
TypeScript fixture alone, whose surfaces were enumerated by reading the source
before the extractor was run. The two Python fixtures are recall-only: an
exhaustive list derived from the tool's own output would make precision
trivially 100% and the metric worthless (`TODO.md` B3c).

---

## `<app>.manifest.json` — where the audited code came from

It lives at `corpus/evidence/<app>.manifest.json`, never inside the code,
because the auditor does not write to what it audits — and an upstream
repository may ship a `MANIFEST.json` of its own.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | str | yes | The directory holding the code. |
| `role` | str | yes | `deliberately_vulnerable_demo`, `open_source_reference`, or `downloaded`. |
| `upstream_url` | str | yes | Where it came from. |
| `upstream_commit` | str | yes | The commit the code is at. **Every line number recorded anywhere is only valid against this.** |
| `upstream_commit_date` | str | yes | ISO 8601. |
| `framework`, `language` | str | fixtures only | What a corpus fixture exercises. |
| `note` | str | no | Free text. |

A `ground_truth.json` must agree with its fixture's manifest on `name` and
`upstream_commit`; a test asserts it.

---

## `corpus/<app>/extracted_baseline.json` — regression protection only

A snapshot of what the extractor produces today, generated from its own output.
A test asserts the current run still matches, so a change that silently drops
or adds surfaces fails loudly.

**It is not ground truth and the Phase 4 scorer must never read it.** Because it
is tool-derived, measuring the tool against it would report perfect accuracy by
construction. It carries `"source": "tool_derived"` and a note saying exactly
that, and a test asserts the marker is present.

---

## Later phases

`sbom.json`, `aibom.json`, `mapping.json` (Phase 2) and `findings.json`
(Phase 3) are not defined yet. Define each one here **before** writing the code
that produces it.
