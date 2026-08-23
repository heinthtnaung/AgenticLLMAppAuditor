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

**`schema_version` is per file.** Each artifact versions independently; that
`surfaces.json` is at 2 while a new file starts at 1 is not a mistake.

**External tools are normalised, never stored raw.** Syft's output carries a
random UUID, a wall-clock timestamp, and absolute paths, so two runs differ. Any
artifact derived from an external tool drops timestamps, UUIDs, absolute paths,
tool-internal identifiers, and synthesised values the tool guessed. What is
stored is this project's own shape, using the standard's field names where they
fit so the lineage stays obvious.

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

## `artifacts/<app>/sbom.json` — Phase 2 output

What the app's dependency manifests and the SBOM generator say about its
components. Not raw CycloneDX: the determinism rule above makes storing Syft's
output as produced impossible, and a rewritten document wearing a standard's
name would invite a reader to feed it to a CycloneDX tool that would then choke.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `1`. |
| `generator_name` | str | yes | The external tool, e.g. `syft`. |
| `generator_version` | str | yes | Pinned. If it changes, the artifact *should* change. |
| `version_guessing_enabled` | bool | yes | Whether the generator was allowed to infer a version from a range constraint. |
| `scanned_manifests` | list[str] | yes | The dependency manifests that exist and were read, sorted. Empty when the app declares none. This is what makes "streamlit is missing" a checkable claim rather than an accusation. |
| `component_count` | int | yes | `len(components)`. |
| `components` | list | yes | Sorted by `(ecosystem, name, version or "")`. |

Each component:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | str | yes | PEP 503-normalised distribution name — lowercase, runs of `-_.` collapsed to `-`. Never an import name. |
| `ecosystem` | str | yes | `pypi` or `npm`. One ecosystem per document: only Python manifests are read today, and an npm app needs its own manifest reader before its components could be labelled correctly. |
| `version` | str \| null | yes | Read **only** together with `version_source`. |
| `version_source` | str | yes | `pinned`, `inferred`, `unconstrained`, or `unknown`. |
| `version_constraint` | str \| null | yes | Exactly as the manifest wrote it, e.g. `~=0.3.25`. Without it, `inferred` is an unfalsifiable claim. |
| `purl` | str | yes | The join key. **Carries a version only when `version_source` is `pinned`.** |
| `declared` | bool | yes | Named in a dependency manifest. |
| `tool_reported` | bool | yes | The generator emitted it. |
| `declared_in` | str \| null | yes | Which manifest declared it. |

**A versioned PURL is a fact, never a guess.** `~=0.3.25` admits `0.3.99`, so
recording `pkg:pypi/langchain@0.3.25` would let any purl-keyed advisory lookup
manufacture a false positive. Inferred versions live in `version` and
`version_source` only, where a consumer has to look at them deliberately.

An exact pin is read from the **manifest**, not from the generator. The
manifest is what the app declares; a generator reporting a different version is
reporting a different fact, and preferring it would let the PURL assert a
version the app never asked for.

The invariant is one-directional: a versioned PURL implies `pinned`, but
`pinned` does not imply a versioned PURL — a pin the generator never saw and
whose constraint could not be read yields a bare PURL rather than a guess.

The two booleans are more useful than one enum: `declared and not
tool_reported` is a dependency the generator dropped, and `tool_reported and
not declared` is an undeclared one. At least one must be true.

---

## `artifacts/<app>/aibom.json` — Phase 2 output

The AI-specific pieces: which models, tools and agents the app defines. Derived
from `surfaces.json`, never by re-parsing source, so every entry is traceable.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `1`. |
| `component_count` | int | yes | `len(components)`. |
| `components` | list | yes | Sorted by `(kind, file, line, name)`. |

Each component:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `kind` | str | yes | `MODEL`, `TOOL`, or `AGENT`. |
| `name` | str | yes | Copied from the surface. |
| `surface_id` | str | yes | The `surfaces.json` record it came from. An entry that cannot be traced back is an entry nobody can check. |
| `file`, `line` | str, int | yes | Copied from the surface, so the file reads on its own. |
| `module` | str | yes (may be `""`) | Copied from the surface. |
| `model_source` | str | yes | `unstated` for a model client whose model is chosen at runtime, `not_applicable` for tools and agents. |

One list with a `kind`, rather than three lists, so a reader who understands
`surfaces.json` understands this immediately and a fourth kind is additive.

**Why there is no `model_identifier` yet.** `surfaces.json` records no model
name, so the field would always be null. Capturing
`ChatOpenAI(model="gpt-4o")` needs a new field on `Surface`; until a fixture
exercises it, an always-null field would be worse than its absence. Adding it
later is additive.

The MODEL/AGENT split is decided by checking the surface name against
`MODEL_CLASSES`, **not** by reading `detail` — `detail` is documented as
descriptive only, so parsing it would make a reworded string break this file.

---

## `artifacts/<app>/mapping.json` — Phase 2 output

Joins each surface to the component it comes from, or records why there is
none. Exactly one entry per surface.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `1`. |
| `surface_count` | int | yes | One entry per surface extracted in the same run. Phase 2 does not re-read `surfaces.json`, so this is an in-process invariant, asserted by tests rather than checkable from disk alone. |
| `mapped_count` | int | yes | Entries with reason `third_party`. |
| `unmapped_count` | int | yes | The rest. |
| `reason_counts` | object | yes | All five reasons always present, including zeros. |
| `undeclared_components` | list[str] | yes | Distinct names used but not declared, sorted. **Not exhaustive — see below.** |
| `entries` | list | yes | Sorted by `surface_id`. |

Each entry:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `surface_id` | str | yes | Verbatim from `surfaces.json`. |
| `module` | str | yes (may be `""`) | Copied from the surface; not derivable from `surface_id`, and without it this file cannot be read alone. |
| `package_root` | str \| null | yes | The package-root of `module`. Shows the working, so the join is checkable. |
| `component_name` | str \| null | yes | Resolved distribution name. |
| `ecosystem` | str \| null | yes | `pypi` or `npm`. |
| `purl` | str \| null | yes | Copied from the matching component. **Non-null only when `third_party`**, so `purl != null` means exactly "joined". |
| `reason` | str | yes | One of the five below. |
| `resolved_by` | str | yes | `normalised_name`, `alias_table`, or `none` — how the import name became a distribution name. |

The five reasons:

| Reason | Meaning |
|---|---|
| `third_party` | Joined to a component in `sbom.json`. |
| `stdlib` | Part of the language runtime, or a builtin. No distribution exists. |
| `first_party` | The app's own code. |
| `used_but_undeclared` | Names something that is neither the language runtime, nor the app's own code, nor a component in the SBOM. **A supply-chain finding, not a mapping gap.** |
| `unresolved` | The owning distribution could not be determined; needs the dataflow analysis in Phase 3. |

An unmapped surface is the normal case, not a defect: on the corpus app, 6 of
19 surfaces join to a component. The reason field exists so a reader never has
to work out which kind of "no" they are looking at.

Three checks run before that conclusion is reached, and each exists because
skipping it produced a false finding: the language's own runtime (Node's
builtins are not Python's), the app's own top-level modules, and then the SBOM.
Without the second, `from myapp.loaders import x` reads as a missing
dependency.

**`undeclared_components` is not exhaustive.** It can only report a package
that some surface points at. The corpus app also imports `dotenv` without
declaring it, but nothing in the application creates a surface for
`load_dotenv()`, so a surface-keyed artifact has nowhere to record it. A
complete answer needs a repository-wide import inventory, which is not part of
this phase.

**Coverage is printed, not stored.** A percentage is derived from the counts,
and a float in the artifact would break byte-identical output for no gain.

---

## Advisory data policy

Generating an SBOM is local. Fetching advisories is not, and the auditor makes
no network calls — so advisories are **not** fetched at runtime.

The policy, when advisory matching is built: a snapshot is downloaded
out-of-band as a documented manual step, committed or pinned like the corpus
is, and read from disk. A snapshot is reproducible, which is what an
evaluation needs, and it is out of date the day after it is taken — that
trade-off belongs in the write-up rather than in a footnote.

Matching is **deferred** for now, and the reason is a property of the data
rather than of the code: of the corpus app's five components, two have no
version at all and three have one inferred from a range constraint. There is
nothing an honest matcher could key on. Asserting a match against `~=0.3.25`
would claim a vulnerability the app may not have, which is the one failure this
phase must not produce.

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
| `owasp_id` | str | yes | `LLM01`, `LLM02`, `LLM03`, `LLM06`, or `AUDITABILITY`, from the **2025** OWASP list. |
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
claimed where `expected_surfaces_complete` is `true`. The one committed
fixture is recall-only: an exhaustive list derived from the tool's own output
would make precision trivially 100% and the metric worthless (`TODO.md` B3).

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

## `corpus/evidence/<app>.baseline.json` — regression protection only

A snapshot of what the extractor produces today, generated from its own output.
A test asserts the current run still matches, so a change that silently drops
or adds surfaces fails loudly.

**It is not ground truth and the Phase 4 scorer must never read it.** Because it
is tool-derived, measuring the tool against it would report perfect accuracy by
construction. It carries `"source": "tool_derived"` and a note saying exactly
that, and a test asserts the marker is present.

---

## Later phases

`findings.json` (Phase 3) is not defined yet. Define it here **before** writing
the code that produces it.
