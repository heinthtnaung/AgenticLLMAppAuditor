# Artifact schemas

Every phase hands data to the next one through JSON files. These are contracts:
a field is never renamed or removed without updating every reader in the same
change. `schema_version` is bumped when that happens — and also when a fixed
vocabulary gains a value, or a documented invariant changes. Both alter what a
reader is entitled to conclude, even though no field is renamed or removed.

Two conventions apply to every file here:

- **Paths are repo-relative POSIX** (`chatapp/backend/app/main.py`), never
  absolute and never with backslashes. This is what makes an artifact
  byte-identical on a different machine. `artifacts/repo_path.py` defines the
  rule; `Surface` and `SkippedFile` both enforce it.
- **Output is deterministic**, with three named exceptions, all model-authored
  and all defined in their own sections below: `findings.json`'s prose fields
  and -- under the opt-in `--semantic-probe` -- its probe records, whose detail
  is a model's rationale; `remediation.json`'s advice; and `planner.json`'s
  `order`, which a model may choose. **All three are inert by default**: no
  scored run has ever enabled the probe, and without it `findings.json` and
  `planner.json` are byte-identical run to run. Everything else obeys this rule,
  including every other field of all three files. Records are sorted, keys are sorted, and no
  timestamps or absolute paths are written. The same input always produces the
  same bytes.
- **One list is deliberately not sorted**: an advice entry's `sources` in
  `remediation.json`, kept in the order the prompt cited them so a reader can
  match the model's own `[1]`, `[2]`, `[3]`. Still deterministic -- the
  retriever orders hits by `(distance, id)` -- just not sorted by any field of
  the record, which is why it is called out here rather than left to surprise
  someone diffing two runs.
- **One artifact is not byte-identical at all, by design**: `report.ai.html`,
  an optional AI-formatted view a local model writes from the deterministic
  `report.md`. The model re-renders, so identical input yields varying bytes --
  a different kind of exception from the two prose carve-outs (whole model-
  written *fields*) and from `report.html` (a deterministic conversion of a
  fixed `.md`). The authoritative `report.html` is unchanged and stays
  byte-identical; `report.ai.html` is gitignored under `artifacts/`, never
  enters the audit's artifact count, and is refused whole if it invents an
  advisory the audit never found. See its row in the table below.
- **One artifact carries a timestamp and sorts neither its keys nor its
  records, and is byte-identical anyway**: `findings.openvex.json`, defined
  below. OpenVEX makes `timestamp` mandatory and the document is written by
  `vexctl` rather than by this project, so the key order is the tool's and the
  instant is **pinned** -- taken from `findings.json`'s
  `coverage.advisory_db_updated_at`, never from a clock. The ban is on values
  that change between runs, not on the word "timestamp": a pinned instant is a
  fact about when the data was taken.

## Where everything lives

`<app>` is the single join key across every row keyed by an audited fixture:
the artifact directory name, `ground_truth.app`, and
`manifest.name`. A fetched tree's `<name>` is deliberately **not** an `<app>`:
it names a directory under `fetched/` and joins to nothing, because nothing has
graded it. It becomes an `<app>` only when a human adopts it as a fixture,
which is a hand-authored manifest and a hand-written grading key, not a
download.

| Kind | Path | Written by |
|---|---|---|
| Grading key | `grading_keys/<app>.ground_truth.json` | hand-authored. Committed; **one is shipped** as of 2026-09-05 — `damn-vulnerable-llm-agent`, AI-drafted and unverified, so every score it produces carries `key_ai_drafted` and `key_unverified` — see `docs/REPORT.md` Appendix A |
| Provenance, graded app | `grading_keys/<app>.manifest.json` | hand-authored. A key without one is refused: its line numbers mean nothing without the commit |
| Regression snapshot | `grading_keys/<app>.baseline.json` | tool-derived |
| Audited code, fetched | `fetched/<name>/` | `src/fetch_repo.py` — a shallow clone with its history removed. Its own root, so a fetch never lands on a tree someone is grading -- that would rot every line number in its key. Gitignored |
| Phase 2 output | `artifacts/<system>/<app>/findings.openvex.json` | `src/emit_vex.py` via `vexctl` -- the advisory findings as OpenVEX statements, the same relationship `findings.sarif.json` has to `findings.json`. **A command of its own, never `outputs.write_all`**, so an audit needs no vexctl installed and the artifact count keeps meaning what it meant |
| Phase 5 output, optional | `artifacts/<system>/<app>/report.ai.html` | `src/ai_report.py` via a local model (gemma) -- an AI-formatted view of `report.md`, **non-deterministic and not authoritative** (`report.html` is). A command of its own, never in the count; refused whole if it invents an advisory, banner says so if it omits one. Degrades when the model is absent |
| Provenance, fetched | `fetched/<name>.manifest.json` | `src/fetch_repo.py`. The same shape as the fixture row above, tool-written instead of hand-authored — see that section for why one shape has two producers. Gitignored |
| Provenance, knowledge | `knowledge/manifest.json` | `src/index_knowledge.py` via `src/retrieval/manifest.py`. The second row not keyed by `<app>`, for the same reason as the VEX one below: a knowledge source is about *security guidance*, not about any audited app, so one index serves every audit. The clones and the index beside it are gitignored; this file is the committed pin |
| Provenance, VEX | `vex/manifest.json` | hand-authored, and about the documents this project **consumes**. The one row not keyed by `<app>`: a consumed VEX document is about a *component*, and a component is shared across apps. The document this project *emits* is app-keyed and lives under `artifacts/` -- see the last row -- because its evidence is one app's surface reachability |
| Phase 1 output | `artifacts/<system>/<app>/surfaces.json` | `src/main.py`, and each baseline for its own run |
| Phase 2 output | `artifacts/<system>/<app>/sbom.json` | `src/main.py` |
| Phase 2 output | `artifacts/<system>/<app>/sbom.cyclonedx.json` | `src/main.py`, the same scan in the standard format |
| Phase 2 output | `artifacts/<system>/<app>/aibom.json` | `src/main.py` |
| Phase 2 output | `artifacts/<system>/<app>/mapping.json` | `src/main.py` |
| Phase 3 output | `artifacts/<system>/<app>/findings.json` | `src/main.py`, and each baseline |
| Phase 3 output | `artifacts/<system>/<app>/findings.sarif.json` | `src/main.py`, the same findings in the standard format. **Not written by a baseline** |
| Phase 3 output | `artifacts/<system>/<app>/report.md` | `src/report.py` — **not JSON and not a contract.** A rendering of the two files above for a person to read; nothing consumes it, and nothing may join on it. It is listed here so a reader of this file does not find an artifact it never mentions. |
| Phase 3 output | `artifacts/<system>/<app>/remediation.json` | `src/checks/advise.py` via `src/outputs.py` — the only artifact a model writes into. Two producers, one file: the advice is the model's, and `src/retrieval/retrieve.py` writes the `knowledge_base` block beside it, which no model touches |
| Phase 3 output | `artifacts/<system>/<app>/remediation.md` | `src/remediation_report.py` — **not JSON and not a contract**, a rendering of the two files above |
| Phase 4 output | `artifacts/<system>/evaluation.json` | `src/evaluate.py`, via `src/evaluation/harness.py` — one file per system per run, never one per app |

`<system>` is the second join key, added in Phase 4: which of the three scored
systems produced the file. Its vocabulary is `evaluation.json`'s `system` field
— `agentic_auditor`, `baseline_static_rules`, `baseline_sbom_only` — and
deliberately not a second list, so the directory a file sits in and the label
inside its scorecard cannot disagree. Rows written by `src/main.py` are the
auditor's, so `<system>` there is always `agentic_auditor`; a baseline writes
`findings.json` and `surfaces.json`, and nothing else.

**The system comes before the app, and the reason is `evaluation.json`.** That
artifact spans every app for one system, so it needs a directory of that exact
scope, and only this order has one. It is also what keeps the harness
unmodified: `load_app` and `write_evaluation` join `<app>` and the filename onto
the directory they are handed, so the system segment is a directory the caller
names rather than a rule the loader has to learn.

**A system's `surfaces.json` is its own, never shared.** The scorer reads it
only to attribute misses — `surface_not_extracted`, `file_skipped` — so pointing
a baseline at the auditor's copy would not move a single count, but it would
make the baseline's miss reasons change whenever the auditor's extractor
changes, and it would attribute one system's misses to another system's
behaviour. Absent is still an error: the file is how "no inventory" is told
from "never run".

**What a baseline's `surfaces.json` contains depends on whether it names any
surface.** `surface_count: 0` is not a neutral absence -- it is the falsifiable
claim "audited, nothing found" -- so a system may only make it if it is true.
A baseline that matches raw text and names what it matched (a `DATA_SOURCE`
called `st.chat_input` at `main.py:60`, say) *did* identify that surface, and
its findings say so; an empty `surfaces.json` beside those findings is a
self-contradiction a reader meets by opening both files. Such a baseline writes
exactly the distinct surface tuples its own findings name, deduplicated and
sorted -- derived findings-first, never by inventorying the repository, because
it still performs no inventory. A baseline that names no surface at all, such
as one reporting whole components with no file or line, writes `surface_count:
0` truthfully.

**`schema_version` is per file.** Each artifact versions independently; that
`surfaces.json` and `sbom.json` are at 3 and `mapping.json` at 2, while a new
file starts at 1, is not a mistake.

**External tools are normalised, never stored raw.** Syft's output carries a
random UUID and a wall-clock timestamp, so two runs differ. Any artifact
derived from an external tool drops those, along with absolute paths,
tool-internal identifiers and values the tool guessed, so the result is
byte-identical every run.

All of those fields are *optional* in CycloneDX, so dropping them leaves a
valid document. That is what `sbom.cyclonedx.json` is: the same scan in the
standard format, reproducible, for feeding to other tooling.

`src/grading_keys.py` owns these paths. Import them from there rather than
joining strings, so a later phase cannot guess wrong.

**There is deliberately no `target.json`.** One was proposed, to carry the app
name, the upstream commit and the file count next to the output. All three are
already recoverable — the app name is the artifact directory's, and the rest
are in `grading_keys/<app>.manifest.json` — so it would be a second place
to state the same facts, and therefore a second place for them to disagree.

**No audited code lives in this repository at all.** The auditor is pointed at
a repository by path or URL, and a fetched tree lands under the gitignored
`fetched/`. So a grading key can never be confused with something the audited
project itself shipped: the two are not merely in different folders, one of
them is not here.

These three files have moved twice. They came out of the audited tree after
Phase 1, into `corpus/evidence/`; on 2026-09-04 the pinned corpus was removed
with the tool becoming URL-driven, and they moved to `grading_keys/`. No field
changed either time, and each file keeps its own `schema_version`: a relocation
is not a record change, and because the old paths no longer exist a stale
reader fails loudly rather than reading the wrong file.

---

## `artifacts/<system>/<app>/surfaces.json` — Phase 1 output

Produced by `src/main.py` via `surface.surfaces_to_json`. Read by Phase 2
mapping and Phase 3 auditing. `<app>` is the audited directory's name — see the table above for how
consumers find its grading key.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `3`. |
| `surface_count` | int | yes | `len(surfaces)`, so a reader can sanity-check at a glance. |
| `surfaces` | list | yes | Sorted by `(file, line, kind, name)`. May be empty. |
| `skipped_file_count` | int | yes | `len(skipped_files)`. |
| `skipped_files` | list | yes | Files the scan could not analyse, sorted by `(file, reason)`. May be empty. |

A repository with no LLM surfaces is a valid result, not an error: the file is
still written with `surface_count: 0` and an empty `surfaces` list, so Phase 4
can tell "audited, nothing found" apart from "never audited".

### `skipped_files` — the caveat attached to the claim

A scan that could not read every file is still a valid scan and still exits 0:
refusing would turn one unparseable vendored file into a total audit failure.
But then "these are all the surfaces" needs the caveat "except in these files"
travelling with it, which is why this lives here and not in a file of its own.
A sidecar can be absent, stale, or simply never opened, and the moment it is,
an unqualified recall number gets computed off a partial scan.

Required rather than optional for the same reason as `scanned_manifests` in
`sbom.json`: `skipped_files: []` is a falsifiable claim that nothing was
skipped, while an absent key would force every reader to guess between that and
"written by a producer too old to report skips".

Each entry in `skipped_files`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `file` | str | yes | Repo-relative POSIX path, same rule as a surface's `file`. |
| `reason` | str | yes | One of `unparseable_syntax`, `undecodable_bytes`, `too_large`. |
| `line` | int or null | yes | Where the parser gave up; `null` when unknown. **Descriptive only — never a join key.** |

The reasons all mean *this file could not be analysed*. A file that parses and
yields nothing is not recorded here, and no reason may ever be added for it.

**The parser's own error message is deliberately not stored.** Two reasons, both
verified on this repo: `SyntaxError.msg` wording changes between CPython
versions this project supports, so two graders on two interpreters would get
different bytes from identical input; and for a non-UTF-8 file with no PEP 263
cookie the message contains an absolute path — `invalid or missing encoding
declaration for '/home/…'`. `line` carries the one machine-stable part; the
interpreter's own wording is discarded with the exception, and what is printed
is the same `file`, `reason` and `line` the artifact records.

`reason` comes from the raise site, never from the exception type: a non-UTF-8
file with no cookie raises `SyntaxError` from `tokenize.open`, while one with a
utf-8 cookie raises `UnicodeDecodeError`. Both are `undecodable_bytes`.

**`skipped_files: []` does not claim every byte was read.** It covers only files
the scan would otherwise have analysed. Skip-dirs (`node_modules`, `.venv`) and
ignored suffixes are dropped before this point and are not app code.

Two limits are known and deliberate:

- **Undecodable bytes are recorded for Python only.** `tokenize.open` refuses
  the file, so Python records `undecodable_bytes`. tree-sitter reads bytes and
  `ts_utils.node_text` decodes with `errors="replace"`, so a `.ts` file never
  reaches that reason — and where the bad bytes sit decides what happens
  instead. In an identifier, the grammar errors and the file is recorded as
  `unparseable_syntax`. In a string literal it parses, and the surface is
  reported with a U+FFFD in its `name` only if the name derives from that
  string; bytes in a value that never becomes a name produce a surface that
  looks entirely clean. `tests/parsing/test_extractor_skip_limits.py` pins it.
- **An unreadable file is not a skip reason.** A permission error still stops
  the scan. `SKIP_REASONS` covers files that could not be *analysed*, not files
  that could not be *opened*, and the second needs its own decision.

### What a Phase 4 scorer must do with it

Alongside the `finding_count: 0` → `n/a` rule:

1. Read `skipped_files` before computing anything.
2. Intersect its `file` values with the grading key's files.
3. **No overlap:** recall is reportable as normal — a skip there could not have
   hidden a graded surface. Still print "scan partial, n files skipped".
4. **Any overlap:** that is not reportable as the app's recall. A graded surface
   in a skipped file is a third outcome beside true and false negative — it was
   never scanned. Exclude the app, or report recall over the scanned subset with
   the excluded count stated. A miss caused by the loader measures the loader,
   not the detector; averaging the two makes the detector's number
   unfalsifiable, the same argument that forbids scoring against the
   tool-derived baseline.
5. Precision is unaffected: a skipped file emits no surfaces, so it cannot
   produce a false positive.

The ratio is the wrong test — one skipped 2000-line file can hide forty
surfaces while `skipped_file_count: 1` reads as trivial. Use the intersection.

`grading_keys/<app>.baseline.json` has no skip list because the graded app has
no unreadable file. It must gain one the day a fixture legitimately does,
otherwise a regression that *starts* skipping a file shows up only as
"surfaces disappeared", with no reason attached.

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

## `artifacts/<system>/<app>/sbom.json` — Phase 2 output

What the app's dependency manifests and the SBOM generator say about its
components.

This is not CycloneDX, and the reason is not determinism -- a valid
deterministic CycloneDX document sits beside it as
`artifacts/<system>/<app>/sbom.cyclonedx.json`. It is that CycloneDX has no field for
**how much a version can be trusted**: one guessed from `~=0.3.25` looks
exactly like an exact pin, and that distinction is what stops an advisory
lookup claiming a vulnerability the app may not have. CycloneDX also lists only
what the generator found, omitting the two dependencies the app declares and
Syft misses.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `3`. |
| `generator_name` | str | yes | The external tool, e.g. `syft`. |
| `generator_version` | str | yes | Pinned. If it changes, the artifact *should* change. |
| `version_guessing_enabled` | bool | yes | Whether the generator was allowed to infer a version from a range constraint. **Scoped to PyPI** — it is the generator's Python-only setting, so on an npm document it reads `true` while nothing was guessed. |
| `scanned_manifests` | list[str] | yes | The dependency manifests **and lockfiles** that exist and were read, sorted. Empty when the app declares none. This is what makes "streamlit is missing" a checkable claim rather than an accusation — and what makes `locked` falsifiable, since a component claiming it must have a lockfile named here. The manifest is read by this project; the lockfile is read by the generator. |
| `component_count` | int | yes | `len(components)`. |
| `components` | list | yes | Sorted by `(ecosystem, name, version or "")`. |

Each component:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | str | yes | Normalised by the **ecosystem's own rule**: PEP 503 for `pypi` (lowercase, runs of `-_.` collapsed to `-`); lowercase only for `npm`, where `lodash.merge` and `lodash-merge` are two different real packages and collapsing them would rename one into the other. Never an import name. |
| `ecosystem` | str | yes | `pypi` or `npm`. **One ecosystem per document**, and required — there is no default, because guessing PyPI for an npm component would break every join downstream. A repository declaring both is refused rather than half-read. |
| `version` | str \| null | yes | Read **only** together with `version_source`. Non-null for `pinned`, `locked` and `inferred`; may be null for `unconstrained`, and is null for two of the Python fixture's components; always `null` for `unknown`, the one source meaning a constraint was present and no version was ever established. |
| `version_source` | str | yes | `pinned`, `locked`, `inferred`, `unconstrained`, or `unknown`. `locked` means resolved by a lockfile the generator read: exact and reproducible, but not a version the author's manifest named. `unconstrained` means the manifest named no version; its `version` carries whatever the generator resolved, if anything. Like `inferred`, that version is evidence and not an assertion, so it never reaches the PURL. |
| `version_constraint` | str \| null | yes | Exactly as the manifest wrote it, e.g. `~=0.3.25`. Without it, `inferred` is an unfalsifiable claim. |
| `purl` | str | yes | The join key. **Carries a version only when `version_source` is `pinned` or `locked`.** Percent-encoded per the PURL spec, so an npm scope appears as `pkg:npm/%40langchain/core@0.3.3` and is byte-comparable with `sbom.cyclonedx.json`. |
| `declared` | bool | yes | Named in a dependency manifest. |
| `tool_reported` | bool | yes | The generator emitted it. |
| `declared_in` | str \| null | yes | Which manifest declared it. |

**A versioned PURL is a fact, never a guess.** `~=0.3.25` admits `0.3.99`, so
recording `pkg:pypi/langchain@0.3.25` would let any purl-keyed advisory lookup
manufacture a false positive. Inferred versions live in `version` and
`version_source` only, where a consumer has to look at them deliberately.

**A lockfile-resolved version is a fact of the same kind.** It is the version
that will actually be installed, so `locked` reaching an advisory matcher is
sound. `inferred` remains structurally incapable of it: `~=0.3.25` and `^0.3.2`
admit versions the app may never install. Both halves matter — the policy has
been widened by one provenance, not relaxed.

`locked` is assigned from **"a lockfile was read"**, never from the ecosystem
and never from "the generator reported a version". Keying it on the ecosystem
would mislabel a Python app shipping a `poetry.lock`, whose versions are just
as resolved. Keying it on the generator having reported something would relabel
every guessed version as a fact and put it straight into a PURL, which is the
one outcome this vocabulary exists to prevent.

**`locked` is decided per component, from the generator's own record of which
file it read that component from** -- a `syft:location:<n>:path` property whose
basename is a lockfile. Not from the directory listing.

That distinction was a live defect until 2026-09-05, and the paragraph here
described it as prevented. It reasoned that the Python path was safe because
`requirements_parser.manifests_present` reports no lockfile -- true -- while
missing that the **npm** path does report one (`npm_manifest.manifests_present`
returns `yarn.lock`, `package-lock.json`, `pnpm-lock.yaml`). So for any JS app
with a lockfile, the mere presence of the file relabelled every component that
had a version -- including versions the generator merely guessed -- as
`locked`. `LOCKED` is in `EXACT_SOURCES`, so each of those gained a **versioned
purl**, and that purl is the key `known_advisory` joins advisories on. A guessed
version could therefore attract a CVE attributed to a version the app may not
use.

Reading Python lockfiles is what the old rule was waiting on, and this is the
prerequisite it named. It is now met: the flag is evidence-driven, so a Python
lockfile can be parsed without relabelling anything the generator guessed.

An exact pin is read from the **manifest**, not from the generator. The
manifest is what the app declares; a generator reporting a different version is
reporting a different fact, and preferring it would let the PURL assert a
version the app never asked for. A lockfile is not a counter-example: it is
also a file the app committed, which is why it ranks above the generator's own
inference but below an explicit pin.

The invariant is one-directional: a versioned PURL implies `pinned` or
`locked`, but neither implies a versioned PURL — a pin the generator never saw
and whose constraint could not be read yields a bare PURL rather than a guess.

The two booleans are more useful than one enum: `declared and not
tool_reported` is a dependency the generator dropped, and `tool_reported and
not declared` is one the manifest never named. With a lockfile that second case
is the **normal** one, not a finding: most of an npm tree is transitive, so
`declared` distinguishes direct from transitive there, and "undeclared
dependency" is only a finding where the generator's own evidence was the
manifest. At least one must be true.

### One record per installed version

A component's identity is `(ecosystem, name, version)`, not the name. A lockfile
legitimately holds one package several times — this project's JS fixture has
`langsmith` at 0.1.48, 0.1.55 and 0.1.61 — and each installed copy is its own
supply-chain fact. So `component_count` **counts records, not distinct
packages**: 82 records for 75 distinct names on that fixture.

When several records share a name, `declared`, `declared_in` and
`version_constraint` are facts about the **name**, not about that record's
version. The fixture shows why this has to be said out loud: `langsmith` is
declared `^0.1.55`, which does not admit the 0.1.48 the lockfile also holds, so
that record carries a constraint its own version fails. Deciding which record a
constraint selected needs the lockfile's resolution tree and semver
satisfaction, which this project does not do.

---

## `artifacts/<system>/<app>/aibom.json` — Phase 2 output

The AI-specific pieces: which models, tools, agents, datasets and MCP servers the app defines. Derived
from `surfaces.json`, never by re-parsing source, so every entry is traceable.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `1`. |
| `component_count` | int | yes | `len(components)`. |
| `components` | list | yes | Sorted by `(kind, file, line, name)`. |

Each component:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `kind` | str | yes | `MODEL`, `TOOL`, `AGENT`, `DATASET` or `MCP_SERVER`. The last two were added 2026-09-05: the proposal names datasets and MCP servers among the AI components a bill of materials should hold. `DATASET` comes from a data-source surface that loads a named corpus, never from a database query; `MCP_SERVER` from a tool surface whose root is an MCP client class. |
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

## `artifacts/<system>/<app>/mapping.json` — Phase 2 output

Joins each surface to the component it comes from, or records why there is
none. Exactly one entry per surface.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `2`. |
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
| `purl` | str \| null | yes | The matching component's purl, or — when `component_version_count > 1` — a version-less purl built for the join. **Non-null only when `third_party`**, so `purl != null` means exactly "joined". |
| `component_version_count` | int | yes | How many installed versions of that component the SBOM holds. `0` when unjoined, `1` normally, more when a lockfile holds several. |
| `reason` | str | yes | One of the five below. |
| `resolved_by` | str | yes | `normalised_name`, `alias_table`, or `none` — how the import name became a distribution name. |

The five reasons:

| Reason | Meaning |
|---|---|
| `third_party` | Joined to a component in `sbom.json` **in the same ecosystem**. |
| `stdlib` | Part of the language runtime, or a builtin. No distribution exists. |
| `first_party` | The app's own code. |
| `used_but_undeclared` | Names something that is neither the language runtime, nor the app's own code, nor a component in the SBOM. **A supply-chain finding, not a mapping gap.** |
| `unresolved` | The owning distribution could not be determined; needs the dataflow analysis in Phase 3. |

An unmapped surface is the normal case, not a defect: 6 of 19 surfaces join on
the Python graded app, 4 of 5 on the JavaScript one. The reason field exists so
a reader never has to work out which kind of "no" they are looking at.

**The join must agree on ecosystem.** A surface's language decides which one it
resolves in — `python` to `pypi`, `javascript` and `typescript` to `npm` — and
a component in the other one is not a match however well the names line up,
because a PyPI and an npm package can share a name and be unrelated software.

**An ambiguous join drops the version rather than picking one.** When a name
holds several installed versions, `component_version_count` says so and `purl`
carries no version. A surface's import cannot say which copy it loads, so
naming one by sort order would put a guess in the advisory join key — the same
failure `version_source` guards, reached by another route.

Three checks run before that conclusion is reached, and each exists because
skipping it produced a false finding: the language's own runtime (Node's
builtins are not Python's), the app's own top-level modules, and then the SBOM.
Without the second, `from myapp.loaders import x` reads as a missing
dependency.

**`undeclared_components` is not exhaustive.** It can only report a package
that some surface points at. That graded app also imports `dotenv` without
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

The policy, as built: advisory data comes from **Trivy**, run offline as a
second external generator exactly the way Syft is (`src/deps/trivy_runner.py`
mirrors `syft_runner.py`, flag for flag on the network switches). Its database
is fetched out-of-band as a documented manual step — `trivy fs
--download-db-only`, in the README — into Trivy's own cache, and every scan
passes `--skip-db-update`, so an audit never reaches the network. A matcher was
deliberately **not** written here: version-range semantics are a spec this
project does not own, the same argument that made Syft the right producer for
the SBOM.

**No raw Trivy artifact is written.** Only findings derived from the report
land on disk, pinned by three coverage fields: `advisory_generator_name`,
`advisory_generator_version` and `advisory_db_updated_at` — the database
build's own `UpdatedAt`, never its `DownloadedAt`, which is the local clock.
`UpdatedAt` identifies a build but is not a content digest, and old database
builds are not re-downloadable, so byte-identical reproduction of an advisory
run means retaining the cache. The data is out of date the day after it is
taken; that trade-off belongs in the write-up rather than in a footnote.

Matching keys on exact versions only, and that rule survives the Trivy
decision unchanged: Trivy matches lockfile-resolved and `==`-pinned versions,
so on the Python fixture — one `pinned` component of five, the rest ranged or
unconstrained — it reports nothing, rather than guessing what `~=0.3.25`
installs. Asserting a match against a range would claim a vulnerability the app
may not have, which is the one failure this layer must not produce. The
JavaScript fixture's lockfile gave **80 `locked` versions out of 82
components**, which was the tree the check worked against. That figure was
measured before `from_lockfile` became per component (2026-09-05) and while the
fixture that produced it was still shipped; it has not been re-measured, and the
corpus it came from is gone. Read it as the historical shape of the tree, not as
a current count -- a component now reaches `locked` only where the generator
recorded a lockfile as the file it read the version from.

---

## `knowledge/manifest.json` — what the advice was grounded on

The pin for the knowledge base `remediation.json`'s advice is retrieved from.
Written by `src/index_knowledge.py`, shaped by `src/retrieval/manifest.py`, and
read back by `src/retrieval/retrieve.py` on every audit. It is the **only**
committed part of `knowledge/`: the upstream clones and the ChromaDB index built
from them are fetched and built out-of-band and gitignored, the same policy as
any audited tree and the advisory database.

It mirrors `vex/manifest.json` below and inherits that file's rule about `note`
— required, not optional, so a reader meeting an unfamiliar folder learns what
it is for rather than guessing.

**A commit alone is not a pin.** A clone can be edited without moving its
`HEAD`, so `content_digest` is what catches that: one sha256 over each indexed
file's path, a NUL, its bytes and a NUL, in sorted path order. The path is fed
in too, so renaming a file changes the digest exactly as editing one does.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `1`. A mismatch is treated as `index_stale` by the reader rather than as an error, because an index this code cannot read is an index it must not query. |
| `embed_model` | str | yes | The Ollama model every passage was embedded with. Load-bearing, not descriptive: vectors from two models are not comparable, so an index built with one is unreadable by another and the audit degrades when they differ. **Spell the tag** — Ollama lists a pulled model as `name:latest`, and the digest below is looked up by that exact string. |
| `embed_model_digest` | str \| null | yes | The model's content digest, `null` when the server's listing could not be read. A tag names a different build after the next pull; this is what makes "the same model" checkable. |
| `chromadb_version` | str | yes | The library that built the index. Also stored *inside* the index, and the two are compared on every audit. |
| `chunk_chars` | int | yes | The passage size the prose was cut to. |
| `chunk_overlap_chars` | int | yes | How much consecutive passages of one long section share, so a sentence split across a boundary survives in one of them. |
| `source_count` | int | yes | `len(sources)`. Restated so `remediation.json`'s `knowledge_base.source_count` has something to equal. |
| `sources` | list | yes | Sorted by `name`, and a repeated name is refused. |
| `note` | str | yes | Required. With the folder otherwise empty in a fresh checkout, this is the only field telling a reader what is missing and how to build it. |

Each source:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | str | yes | The sort key, unique, and the **join key**: the same value appears as `source` on every `sources` entry in `remediation.json` and on every passage in the index. Its vocabulary is `remediation.py`'s `KNOWLEDGE_SOURCES`, and a mismatch between that and the registry raises at import. |
| `upstream_url` | str | yes | Where the clone came from. |
| `upstream_commit` | str | yes | The 40-character commit, read from the clone's own `.git` files without launching a program. |
| `license` | str | yes | The licence the passages are reproduced under. Not bookkeeping: passages are quoted verbatim into `remediation.json` and `remediation.md`, so the report names this once and each citation carries its URL. |
| `include` | list | yes | The glob patterns selecting what to index, sorted. A source's own README and index pages are deliberately left out. |
| `file_count` | int | yes | How many files those globs matched. |
| `content_digest` | str | yes | `sha256:<hex>`, as defined above. |
| `indexed_passage_count` | int | yes | How many passages those files were cut into. |

**How the two files join.** `remediation.json`'s
`knowledge_base.manifest_digest` is `sha256` over this file's text *as written*
— not over a re-serialisation of its content — and the index stores the same
value about itself. An audit compares three things before it retrieves
anything — the manifest text against the digest the index recorded of it, the
installed chromadb version against the one the index was built by, and the
configured embed model against the one the manifest names. Any disagreement is
`index_stale` and the advice is written ungrounded. **`content_digest` is not
among them**: nothing re-reads the clone at audit time, so a clone edited after
indexing is invisible to an audit -- the manifest and the index still agree
about each other. The digest is what a rebuild checks, and what a reader
comparing two manifests checks. That is why the manifest is written *last* but digested *first*: the
text has to be final before the index can record it.

**What the index must never do.** Two of ChromaDB's defaults would break this
project's offline guarantee, and `src/retrieval/store.py` closes both with a
test on each. Its default embedding function downloads a model from the
internet the first time it embeds text, so a refusing function is always
attached and the store's API accepts precomputed vectors only — `model_client`
computes them against local Ollama. And its client reports usage telemetry
unless told not to. Separately, opening a client on a missing path *creates* a
database file, so an audit checks `knowledge/index/chroma.sqlite3` exists before
opening anything: a run that merely looked for an index must not leave one.

## `vex/manifest.json` — where each VEX document came from

`vex/` holds OpenVEX documents about an audited app's dependencies, and this
manifest records where each came from. It is committed and hand-authored, and it
**has no reader**: nothing under `src/` opens it, for the reason at the end of
this section.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `1`. |
| `document_count` | int | yes | `len(documents)`. |
| `documents` | list | yes | Sorted by `path`. Empty today. |
| `note` | str | yes | Required, not optional: with `document_count: 0` it is the only field telling a reader the folder is empty on purpose. |

Each entry:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `path` | str | yes | Repo-relative POSIX path. The sort key, and unique. |
| `source` | str | yes | `upstream_published` or `project_authored`. The one fact not recoverable from the document itself: OpenVEX's own `author` says who signed the statements, not whether anyone but this project published them. |
| `upstream_url` | str \| null | yes | Where it was fetched. `null` exactly when `source` is `project_authored`. |
| `snapshot_date` | str | yes | `YYYY-MM-DD`, the day the data was taken — the same word the advisory policy above uses. |
| `document_digest` | str | yes | `sha256:<hex>` over the file's bytes. A loose JSON file has no commit of its own, so this is what makes "pinned" checkable rather than hoped for. |
| `note` | str | no | Free text. |

**Recoverable facts are not restated here.** The document's own `author`,
`products`, `vulnerabilities` and statement list are deliberately not copied
into the manifest, for the reason `target.json` was declined: a second place to
state the same fact is a second place for them to disagree, and the document is
authoritative. An index across many documents would be *derived* output
belonging under `artifacts/`, not a hand-maintained field.

**Why the folder holds no document.** Two blockers, both properties of the data
rather than of missing code:

1. **No upstream VEX document exists for any dependency of any fixture.**
   `langchain`, `langchain-community`, `langchain-litellm`, `openai`,
   `streamlit` and `pyyaml` were each checked at conventional locations and in
   PyPI metadata; none publishes one, and none declares a security or VEX URL.
   Recorded rather than left implicit, because "none was found" and "nobody
   looked" are different claims and only the first is evidence.
2. **The Python fixture has almost nothing to key on.** A VEX statement
   identifies its product by PURL, and a versioned PURL is a fact rather than a
   guess. Of that app's five components exactly one carries an exact version.
   The npm fixture is not blocked by this: 80 of its 82 are `locked`.

So the folder and its provenance discipline exist, and the tool makes no claim
the data cannot support.

**That is about documents *consumed*.** Since Phase 5 this project also
**emits** one, from its own findings, and it lives under `artifacts/` rather
than here -- see `findings.openvex.json` above. Consuming and emitting are
different claims: emitting needs only this project's own evidence and no
upstream publisher to exist, which is why the emitted document shipped while
the two blockers above still stand. `vex/manifest.json` is untouched by that
change, and its `document_count: 0` stays true -- which is itself the argument
that an emitted document does not belong in this folder.

**Determinism does not bite here.** The rule at the top of this file governs
output a run produces; `vex/` is committed input, so there is no run for "the
same input produces the same bytes" to be about. That matters because **OpenVEX
requires a `timestamp`**, and a VEX document therefore cannot be normalised the
way `sbom.cyclonedx.json` is: every field `cyclonedx.py` strips is *optional* in
CycloneDX, and this one is not.

The rule bites the moment anything writes — and it proved satisfiable, which is
what let the emitter ship. **Measured: `vexctl` is byte-identical under
`SOURCE_DATE_EPOCH` provided `TZ=UTC` is also set**, since one field otherwise
renders in the local offset. The emitted document's `timestamp` is the pinned
advisory date rather than a wall clock, so the value says when the *data* was
taken.

**One correction to an earlier claim here**, because it was wrong and something
was nearly built on it: vexctl's `@id` is **not** a content hash of the
document. It is a canonicalization hash of the document *as created*, and
appending statements with `vexctl add` leaves it unchanged — so it identifies
the first statement, not the bytes. `findings.openvex.json` therefore sets its
own `@id`, and anything needing a digest takes sha256 over the file, which is
the rule this manifest already sets for `document_digest`.

**Nothing reads it yet, and that is still asserted.** A half-wired reader could
make a supply-chain claim the two blockers above do not support.
`tests/test_vex_unread.py` now permits exactly **one** module to name the token
as a value -- `emit_vex.py`, which runs the tool and writes the document;
`artifacts/vex.py` decides what to claim from field names alone and needs no
exemption. A separate assertion in the same file allows two module *names* to
be imported, since the command imports its own statement builder. And a third,
sharper than either, holds the invariant this section is actually about: **no
module under `src/` names a path into this folder.**

All three check across **all** of `src/`, not just the scored trees:
`src/deps/`, the planned home of a reader, sits outside them, so an assertion
added to `test_scorer_boundary.py` would have passed while the reader quietly
read the folder.

## `grading_keys/<app>.ground_truth.json` — the hand-written answer key

Hand-authored (currently AI-drafted, see `verified`). Read by Task 1.7's tests
and by the Phase 4 scorer. This file is committed: the grading key is evidence.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `2`. |
| `app` | str | yes | Must equal the artifact directory name and the manifest's `name`. |
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
| `code_anchor` | str | yes | The first 60 characters of the trimmed source text at `line`. **Recorded but no longer enforced**: the test that read the real file and checked the line still started with this text lived in `tests/corpus/`, deleted with the pinned corpus on 2026-09-04. Nothing under `tests/` reads the field today. It is still required, and still worth writing, because it is what lets a *human* tell an anchor that drifted from one that never matched — but a key whose lines have moved is no longer caught automatically, and a scorer cannot tell. Re-enforcing it means reading the audited tree at score time, which the scorer deliberately does not do. |
| `llm_surface` | str \| null | yes | One of the four surface kinds, or `null` when the finding is not tied to a code surface (a dependency, for example). Task 1.7 asserts only over non-null values. |
| `surface_name` | str \| null | no | Expected `Surface.name`, for an exact assertion. |
| `component` | str \| null | no | PURL for supply-chain findings, spelled byte-for-byte as the SBOM writes it, percent-encoding included (`pkg:npm/%40langchain/community@0.3.3`). Where named, a produced finding's `purl` must equal it; `null` means the join ignores it. |
| `detection` | str | no | `static`, `probe`, or `either` — which class of check can reach it. Phase 4's baselines need this to state an achievable ceiling. |
| `notes` | str \| null | no | Free text, e.g. the upstream README section it came from. |

**Matching rule for Task 1.7 and the Phase 4 scorer:** a finding matches a
surface when the `file` is equal, the `llm_surface` kind is equal, and the
surface's line falls within `[line, (line_end or line) + LINE_TOLERANCE]` with
`LINE_TOLERANCE = 3`. Exact line equality is wrong here: a human anchors the construct's first line, while a detector may report a few lines into it --
the call inside a multi-line expression, or the `def` under a decorator the
human anchored. Note the window is **not symmetric**: it opens at the key's
line and runs downward, so a finding above the anchor is a different construct
and is never credited to that entry.

The same rule states the **`findings.json` join**, so Phase 4 never has to guess
or parse an id: a produced finding matches a key entry when `file` and
`owasp_id` are equal, `line` falls in that window, and — where the key names
them — `surface_kind` equals the key's `llm_surface`, `surface_name` equals the
key's `surface_name`, and `purl` equals the key's `component`, compared as
strings, byte-for-byte. **`detection` is recorded, not matched on**: the key's
`either` describes what could in principle reach a finding, while the produced
value says what did this run, so neither constrains the other.

**A component-anchored entry grades the reachability claim, not the advisory
identity.** One entry per (surface, component), naming no CVE: a CVE-named
entry rots when the advisory database updates, while this one holds as long as
the pinned version carries at least one advisory in whatever snapshot the run
read. Several produced findings — one per advisory on that component — may
answer the one entry; `true_positives` counts key entries, so they credit it
once and none of them is a false positive.

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

**When AUDITABILITY is graded, and when it is not.** The class is not "the app
keeps no audit log" -- almost no template does, and a rule that broad would
grade every fixture and measure nothing. It is graded when the app **captures**
a record of what the agent did and then **discards it**, because that is a
decision the app made rather than a facility it never reached for.
`vuln-app-1-support-agent`'s `VULN1-05` qualifies: `AgentExecutor` is built with
`return_intermediate_steps=True`, so the tool trace exists, and it is then put
only in Streamlit session state and lost with the session.
`oss-app-react-agent` does not, and the reason is stronger than "it configures
no logging": **this repository never runs the graph.** `langgraph.json` exports
`./src/react_agent/graph.py:graph` for a deployment to invoke, and `src/`
contains no `invoke` or `stream` of it, so there is no point at which the app
could retain or discard a record of anything. (Its `State.messages` is
append-only and does accumulate tool calls during a run, so "it captures
nothing" would be falsifiable from `state.py`. What is true is that no run
happens here, and what a deployment does with that state is not a property of
this repository.) The distinction
is recorded here because the two keys would otherwise read as contradicting
each other on the same construct.

**Known limitation, to be stated in the write-up:** exhaustiveness is only
claimed where `expected_surfaces_complete` is `true`, and an exhaustive list
derived from the tool's own output would make precision trivially 100% and the
metric worthless. Of the three keys, `oss-app-langgraphjs-starter` claims a
complete surface list; the other two do not. `vuln-app-1-support-agent` is
recall-only on both counts, so its `false_positives` is `null` rather than `0`.
`oss-app-react-agent` claims complete *findings* -- it is a clean upstream
template, so a reported finding there is a false positive -- but **not** a
complete surface list, because a reading of that app finds LLM surfaces the
Python detector vocabulary does not name. Claiming completeness there would
assert the extractor saw everything when it did not; the gap is an open task in
`TODO.md`.

---

## `<name>.manifest.json` — where the audited code came from

**One shape, two paths, two producers.** A pin is the same fact wherever the
code came from, so the record is the same record:

| Path | Producer | What it pins |
|---|---|---|
| `grading_keys/<app>.manifest.json` | hand-authored, committed | a graded app whose key cites line numbers valid only at `upstream_commit` |
| `fetched/<name>.manifest.json` | `src/fetch_repo.py`, generated, gitignored | a tree fetched for a one-off audit |

Neither lives inside the code it describes: the auditor does not write to what
it audits, and an upstream repository may ship a `MANIFEST.json` of its own.

**Why a second path is not a second source of truth.** `target.json` was
declined because every field it carried was recoverable elsewhere. The opposite
holds here: `fetch_repo` deletes the history after reading the commit, so this
file is the *only* surviving evidence of what was fetched. Two producers of one
shape is a duplicated *format*, which is the point — a reader learns the record
once.

**And the fetched copy is not committed**, which is what stops it becoming a
duplicated *fact*. Adopting a fetched tree as a fixture means a human
transcribing its pin into `grading_keys/`, so exactly one committed pin per
app exists and two copies can never disagree.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | str | yes | The artifact directory name the key joins on; for a fetched tree, `fetched/<name>/`. |
| `role` | str | yes | `deliberately_vulnerable_demo`, `open_source_reference`, or `fetched_for_audit`. **This is also the tool-derived marker**: `fetched_for_audit` is the only value a tool ever writes, and the other two are only ever hand-authored. There is deliberately no second field saying "generated" — that would be one fact in two places. |
| `upstream_url` | str | yes | Where it came from. `https://` only; `fetch_repo` refuses anything else. |
| `upstream_commit` | str | yes | The commit the code is at. **Every line number recorded anywhere is only valid against this.** Read by `rev-parse HEAD` *before* the history is deleted, since nothing afterwards knows it. |
| `upstream_commit_date` | str | yes | ISO 8601, git's `%cI`. A property of the commit, so it is byte-stable across fetches. |
| `framework`, `language` | str | graded apps only | What a graded app exercises. **Absent from a fetched manifest**, because a fetcher cannot know either and a guess in a provenance record is worse than a gap. No reader reads them. |
| `note` | str | no | Free text. On a fetched manifest it records that the history was removed, so a reader knows why the commit cannot be re-derived from the tree. |

**No fetch timestamp, in either file.** A commit is byte-stable; the time of day
a download happened is not, and recording it would make two fetches of one
commit produce different bytes for the same fact.

**Key order differs between the two paths, and nothing may join on it.** The
hand-authored files are in narrative order; `fetch_repo` writes with
`sort_keys=True` like every other producer under `src/`. Both are byte-identical
run to run, which is what the determinism rule at the top of this file asks for.

**Known gap: this file carries no `schema_version`,** unlike `ground_truth.json`
and `vex/manifest.json`, so the versioning mechanism described at the top of
this document cannot be exercised on it — and the `role` vocabulary changed on
the edit that added the fetched producer (`downloaded` became
`fetched_for_audit`, a value no manifest carried and no code read). That change
is recorded here in prose because there was no field to bump. Adding one means
editing every hand-authored manifest in the same change; it is not done yet.

A `ground_truth.json` must agree with its fixture's manifest on `name` and
`upstream_commit`; a test asserts it. Nothing asserts anything about a fetched
manifest, because nothing grades a fetched tree.

---

## `grading_keys/<app>.baseline.json` — regression protection only

A snapshot of what the extractor produces today, generated from its own output.
A test asserts the current run still matches, so a change that silently drops
or adds surfaces fails loudly.

**It is not ground truth and the Phase 4 scorer must never read it.** Because it
is tool-derived, measuring the tool against it would report perfect accuracy by
construction. It carries `"source": "tool_derived"` and a note saying exactly
that, and a test asserts the marker is present.

---

## `artifacts/<system>/<app>/findings.json` — Phase 3 output

What the auditor concluded, and what it could not reach. Read by Phase 4's
scorer, which grades it against `grading_keys/<app>.ground_truth.json`.

**This is the one artifact a language model writes part of.** The determinism
rule at the top of this file still governs everything else in it. Exactly two
fields are exempt: `model_run.ranking` and each finding's `narrative`. Those are
the model's actual output; the rest of `model_run` — its status, the model
identifier, the settings sent — is byte-identical by construction and stays
under the comparison. Drawing the exception around the whole block would be
self-undermining, since the case for reproducible prose rests on recording the
very settings that would then be free to vary.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `7`. Version 2 added `risk_classes_checked` and `unresolved_component_count`, without which a reader could not tell an unexamined risk class from an examined-and-silent one. Version 3 added `model_run.model_digest` and tightened one invariant: a `used` run must record the settings it sent, because a run that cannot be repeated is not evidence of anything. Version 4 added the four `advisory_*` finding fields and the four `advisory_*` coverage fields, null everywhere except the `known_advisory` check. Version 5 added `coverage.advisory_unreached_components`, the itemization of the count beside it, so a report can name the vulnerable-but-unreached components and their advisory ids rather than only how many there are — while they stay out of the scored `findings` list. Version 6 added the finding field `advisory_severity` — the severity word quoted from the named source beside the CVSS vector — and evolved each `advisory_unreached_components` item to `{purl, advisories:[{id, severity}]}` so a report shows each unreached CVE with its rating.. Version 7 added the top-level `checks_narrowed`, so a check that examined only some of its surfaces can be told from one that examined all of them. |
| `coverage` | object | yes | What the search covered, so a short list is not read as a clean bill. |
| `model_run` | object | yes | What produced the prose. Model-authored content is confined to here and to `narrative`. |
| `probe_count` | int | yes | `len(probes)`. |
| `probes` | list | yes | Every check that ran **or was planned and did not**. Sorted by `probe_id`. May be empty. |
| `finding_count` | int | yes | `len(findings)`. |
| `findings` | list | yes | Sorted by `(file or "", line or -1, owasp_id, rule_id, surface_id or "", purl or "", advisory_id or "")`. Several of those are nullable, so the key substitutes rather than comparing `None`. May be empty. |

`finding_count: 0` with the file present means "audited, nothing found" — the
same distinction `surfaces.json` makes, and the clean fixture depends on it.

`coverage`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `surfaces_considered` | int | yes | How many `surfaces.json` records the checks ran over. |
| `checks_run` | list[str] | yes | The checks that had something to examine on this app, sorted. Not derivable from `probes`: a check that examined subjects and concluded nothing about any of them leaves no probe record, and that silence is the dangerous one. A check **absent** here could not look at all — no mapping to read, or no file in a language it understands — so its absence is never a clean result. **A name here no longer implies every eligible surface**: since task 7.4 the planner may narrow a check, and the document's top-level `checks_narrowed` says how many it examined. Three states, then — present and complete, present and narrowed, absent. Three things cause an absence: no mapping to read, no file in a language the check understands, and — for a check scoped to LLM applications — no LLM surface in the repo at all. The taint trace reads `ast`, so it is absent on a JavaScript-only app; `unsafe_query_construction` is additionally absent on a repo with no `AGENT_DEF` or `TOOL_CALL` surface, because a query built by interpolation in a repo with no model is CWE-89 rather than an LLM finding; `agent_defined_without_callback_handler` is absent on a repo that constructs no agent, which has nothing whose auditability could be judged. The scorer reads that absence as `no_check_for_risk_class`, so it is a claim, not a detail. |
#### `checks_narrowed` — which checks examined only some of their surfaces

**Top level, not inside `coverage`, and that placement is deliberate.**
`artifacts/sarif.py` copies `coverage` wholesale into `findings.sarif.json`,
which is published as byte-identical every run; `checks_narrowed` is the one
field a model can move, so nesting it in `coverage` would push model-determined
bytes into an artifact documented as deterministic.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `checks_narrowed` | list | yes | One entry per check the planner narrowed, sorted by `check`. **Never null**; `[]` when nothing was narrowed — whether a narrowing happened is always knowable, so there is no state `null` would honestly represent. |
| `[].check` | str | yes | The check's name. Must also appear in `coverage.checks_run`: a narrowed check that never ran is a contradiction, and the pairing is validated. |
| `[].examined_surface_count` | int | yes | How many surfaces the check was **handed**, not how many subjects it found among them. The denominator settles it: `eligible_surface_count` is the whole surface list for every check, whatever kinds that check acts on, so a subject count would put the two in different units. A probe handed two surfaces of which one is a prompt template publishes `2`. |
| `[].eligible_surface_count` | int | yes | How many it could have. Counts, never a rate — the denominator travels with the numerator. |

An entry where `examined == eligible` is **refused**, so `[]` is a reliable test
for "nothing was narrowed" and a reader can branch on exactly that.

**What this field does not do.** `src/evaluation/scorer.py` does not read it, so
`evaluation.json` scores a narrowed run exactly as it scores a full one. The
field makes the narrowing visible to a reader; it does not make the score
account for it. A stated limit, not an oversight — teaching the scorer about
narrowing means a Phase 4 change and a re-measure, and is its own task.

| `advisory_data` | str | yes | `not_ingested` or `snapshot`. `snapshot` means Trivy ran offline against the database the three fields below pin; `not_ingested` means no Trivy or no cached database, so an LLM03 finding cites the SBOM and mapping but nothing about what is known to be wrong with a component. |
| `advisory_generator_name` | str \| null | yes | `trivy`. Null exactly when `advisory_data` is `not_ingested` — the pairing is validated in both directions, because a snapshot with a null pin is an undated claim. Mirrors `sbom.json`'s `generator_name`. |
| `advisory_generator_version` | str \| null | yes | From the scan output's own `Trivy.Version`. Same null pairing. |
| `advisory_db_updated_at` | str \| null | yes | The database build's `UpdatedAt`, a property of the build — never `DownloadedAt`, which is the local clock. Same null pairing. |
| `advisory_unreached_component_count` | int \| null | yes | Advisory-carrying components reached by **no** surface — real, counted, and outside the *scored* claim, the same honesty rule as `unresolved_component_count`. The report now names these components and their advisory ids from `advisory_unreached_components` below; they stay out of the scored `findings` list, so this remains the count the scorer sees. `0` means every one was reached; null when `advisory_data` is `not_ingested` or there was no mapping to compute reach against. |
| `advisory_unreached_components` | list \| null | yes | The itemization of the count above: one item per unreached advisory-carrying component, `{"purl": str, "advisories": [{"id": str, "severity": str \| null}, ...]}`, sorted by purl with each advisory list sorted by `id`. `severity` is the word quoted from Trivy's named source, `null` when none named it — the same quotation rule as the finding's `advisory_severity`, never this tool's own rating. Carries no CVSS vector — it is supply-chain context for the report, not a scored finding, so it never enters the scored `findings` list or `evaluation.json`. `null` exactly when the count is null; `[]` when the count is `0`; `len` equals the count otherwise. |
| `risk_classes_checked` | list[str] | yes | The OWASP ids the checks in `checks_run` are capable of reporting, sorted. Lets a reader — and the Phase 4 scorer — tell **"no check covers this risk"** from "a check covered it and stayed silent", without importing the auditor and scoring a stale artifact against fresh code. LLM01 comes from the taint trace, LLM02 from the output-handling check, LLM03 from the supply-chain and known-advisory checks, LLM06 from the permissions check, AUDITABILITY from the callback-handler check; a class missing here was never looked for. |
| `unresolved_component_count` | int \| null | yes | How many of `surfaces_considered` the mapping could not name an owning component for — `mapping.json`'s `unresolved` reason, and only that one. `stdlib` and `first_party` are answers rather than gaps and `used_but_undeclared` is already a finding, so `unmapped_count` is the wrong number to read here: 8 of the vulnerable fixture's 19 surfaces, not 13. `null` means there was no mapping to resolve against — no manifest, so no bill of materials — and a `0` there would claim a reach the check never had. |

There is deliberately no `skipped_file_count`: that is `surfaces.json`'s fact,
and a second copy is a second place for it to disagree. A reader opens both.

`unresolved_component_count` is the copy that *is* made, and the difference is
reachability: a reader of `findings.json` already has `surfaces.json` in front
of them, but the report takes only those two files and the Phase 4 scorer only
this one and the grading key, so nothing downstream can open `mapping.json`.
`surfaces_considered` is the same trade, and both are held to the same defence
— a test asserting the copy still agrees with its source.

`model_run`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `status` | str | yes | `used`, `unavailable`, or `disabled`. |
| `model_identifier` | str \| null | yes | Which model wrote the prose. `null` unless `used`. |
| `model_digest` | str \| null | yes | The model's content digest. A tag is mutable — one of the models compared is literally `:latest` — so a run recorded by tag alone is repeatable only until someone re-pulls. `null` is an honest "not recorded". |
| `model_settings` | object | yes | Only settings that change the output distribution — temperature, seed, and so on. What was actually sent, not what `.env` holds. **Must be non-empty when `status` is `used`**: the whole case for exempting model prose from the byte-identical rule is that the run can be repeated. |
| `ranking` | list[str] \| null | yes | The model's ordering, as a permutation of every `finding_id`. `findings` itself is never reordered by it. |

The server URL and timeout are **excluded**: they are transport, they describe
this machine, and an artifact does not carry machine layout.

Each `probes` entry:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `probe_id` | str | yes | `"{probe_name}:{subject_id}"`. An opaque handle; never parsed. |
| `probe_name` | str | yes | Fixed vocabulary. |
| `subject_kind` | str | yes | `SURFACE` or `COMPONENT`. |
| `subject_id` | str | yes | A surface id, or a purl or component name. |
| `outcome` | str | yes | `confirmed`, `refuted`, `inconclusive`, `not_run`. |
| `reason` | str \| null | yes | Required when `inconclusive` or `not_run`; `null` otherwise. Fixed vocabulary. |
| `detail` | str | yes | Short human note. **Descriptive only — never a join key.** |

Each `findings` entry:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `finding_id` | str | yes | `"{surface_id or component_name or purl or probe_id}:{rule_id}"`, gaining `":{advisory_id}"` when `advisory_id` is set — one surface reaching one component with three advisories is three findings, so the advisory id is part of what the finding *is*. Derived, never a counter, and **unique within the document**, which `model_run.ranking` depends on. Opaque to a reader: every part of it is also its own field. |
| `owasp_id` | str | yes | `LLM01`, `LLM02`, `LLM03`, `LLM06` or `AUDITABILITY`, from the **2025** list -- except `LLM02`, which is the **2023** spelling of improper output handling (2025 numbers it LLM05). Kept because it is the spelling the grading keys and the baselines were written in; `retrieval/owasp_reference.py` carries the note. Constant on the rule — never model-chosen, because classification is what Phase 4 scores. |
| `rule_id` | str | yes | Which check produced it. Fixed **per producer**, and nothing validates it across producers: the auditor's set is the keys of `run_checks.RISK_CLASS_BY_CHECK`, and each baseline writes its own disjoint set (`baselines/rules.py`'s `grep_*` names, `baselines/sbom_only.py`). Look the vocabulary up there rather than expecting a list here. |
| `title` | str | yes | Constant on the rule. Not model-authored: a title that varies per run makes two runs undiffable. |
| `detection` | str | yes | `static` or `probe` — how it was reached this run. The key's `either` is a property of the finding class; the tool never emits it. |
| `surface_id` | str \| null | yes | The `surfaces.json` record. `null` only for a component-anchored finding. |
| `surface_kind`, `surface_name` | str \| null | yes | Copied from the surface, so Phase 4 never parses `surface_id`. |
| `file` | str \| null | yes | Repo-relative POSIX, copied from the surface. Never derived by the model. |
| `line` | int \| null | yes | Copied from the surface. |
| `purl`, `component_name` | str \| null | yes | The SBOM component, where one is evidence. `component_name` without `purl` is the undeclared case. |
| `mapping_reason` | str \| null | yes | The `mapping.json` reason, where the mapping is evidence — e.g. `used_but_undeclared`. |
| `probe_id` | str \| null | yes | Non-null exactly when `detection` is `probe`. |
| `advisory_id` | str \| null | yes | CVE-/GHSA-scheme id, verbatim from the pinned database. Non-null **iff** `rule_id` is `known_advisory`, validated in both directions. |
| `advisory_fixed_version` | str \| null | yes | Verbatim; null when the database lists no fix (Trivy's empty string maps to null so "no fix" has one spelling). May name several versions at once, verbatim. |
| `advisory_cvss_vector` | str \| null | yes | The CVSS v3 vector, quoted verbatim from the one source the generator itself names. A quotation, never a judgement: it is not sorted on, not ranked on, and never becomes a SARIF `level`. |
| `advisory_cvss_source` | str \| null | yes | Which database the vector above is quoted from, so the attribution is specific. Null whenever the vector is. |
| `advisory_severity` | str \| null | yes | The severity word — `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` or `UNKNOWN` — quoted verbatim from the source Trivy names, attributed by `advisory_cvss_source` beside it. A quotation of one database's rating ("ghsa rates this HIGH"), never this tool forming its own: not sorted on, not ranked on, never a SARIF `level`. Null whenever no source is named to carry it. |
| `narrative` | str \| null | yes | The model's explanation of this finding. **The only model-authored field on a record.** `null` unless `model_run.status` is `used`. A plain string rather than a wrapper object: there is no second field planned, and the obvious shape wins until there is. |

**A finding with no evidence is not representable**, and that is enforced in the
constructor rather than reviewed for. At least one of `surface_id`, `purl`,
`component_name` or `probe_id` must be present. `detection: "probe"` requires a
`probe_id` naming a `probes` entry whose outcome is `confirmed`, so a probe
finding cannot exist without the record saying the probe ran and confirmed.

**The tool never emits the grading key's `id`.** `VULN1-06` and its siblings are
hand-authored labels; a tool that emits them hands Phase 4 the answer, and every
precision number after that is worthless.

### What the model may write

The model writes **exactly four fields, in two files**: `findings.json`'s
`narrative` and `model_run.ranking`, and `remediation.json`'s `guidance` and
`snippets`. Every other field in every artifact is written by deterministic
code. This is an allow-list rather than a deny-list on purpose: a deny-list
fails silently the moment a field is added.

Why each excluded field is excluded. `owasp_id` is what Phase 4 scores, so a
model choosing it would be grading its own work. `file` and `line` are copied
from evidence and are what `matches_key` joins on, so a model that could move a
line could move a score. `severity` and `confidence` have no field in the
grading key, so nothing could check them -- an unfalsifiable number that would
nonetheless be quoted. (`advisory_severity` is not this: it is a database's
rating quoted verbatim with its source named, not a classification the model
assigns.) `title`, `rule_id` and `detection` are constants on the
rule that raised the finding, and a title that varied per run would make two
runs undiffable.

`advisory_cvss_vector` and `advisory_severity` are both quotations, not
judgements: each is written by deterministic code, quoted verbatim from the one
source Trivy names, and carried only beside that source in `advisory_cvss_source`
-- so the record reads "ghsa rates this HIGH", falsifiable by opening the
advisory, never "this tool rates this HIGH". Trivy's `Severity` becomes an
unattributed precedence pick only when shown *without* its source, which is why
the word is emitted solely when a source is named to carry it. What stays
refused is the tool forming its *own* per-result severity: the SARIF `level`
remains the constant `warning`, and neither the word nor the vector is ever
sorted or ranked on.

**The advice may not re-classify the finding**, and there are two mechanisms
rather than a promise: `remediation.json` has no classification field, so it is
structurally unrepresentable; and `guidance` may not name an OWASP id other than
the finding's own. The second is a blunt string check and is described here as
one.

#### ~~And never a suggested fix~~ — reversed, deliberately

This section previously read:

> `owasp_id`, `file`, `line`, `severity`, `confidence`, and **any suggested
> fix**. [...] a model-written patch is one copy-paste from crossing the
> no-auto-fixing boundary.

The first five stand. **The last was reversed**: `remediation.json` now carries
model-written remediation advice -- prose plus illustrative snippets, one entry
per finding. The original concern was correct and has not gone away. It has been
given a mechanism instead of a prohibition.

**Prompt wording is not that mechanism, and was measured not to be.** Told in
general terms not to reference the audited app's identifiers,
`qwen2.5-coder:7b-instruct` returned a snippet containing `st.chat_input` --
that app's own identifier -- in the same answer. Told the exact forbidden
tokens, two consecutive runs leaked nothing. A property that turns on how a
sentence is phrased is not a safety property. The prompt does enumerate the
tokens, because it measurably lowers the refusal rate, but no test rests on it
and the contract does not mention it.

The guard runs on the answer. Advice is refused **whole**, never edited, if it
names any identifier from the finding's own evidence or from the app's own
modules, arrives in patch form, exceeds the volume caps, smuggles a code fence
through prose, or names a foreign OWASP id. A sanitised snippet would have two
authors and be testable as neither, and one identifier stripped can still leave
it applicable.

**What was given up, stated plainly.** The tool no longer guarantees that its
artifacts contain no text a reader could act on -- describing a fix well enough
for a person to apply it by hand is the feature. It still guarantees that no
artifact contains *directly applicable* text, and that nothing in `src/` can
apply it. `tests/test_no_write_commands.py` and `tests/test_no_mutation.py`
assert both rather than trusting them. The boundary narrowed from "produces
nothing fix-shaped" to "produces nothing applicable, and cannot apply anything".

---

## `artifacts/<system>/<app>/findings.sarif.json` — Phase 3 output

The same findings in SARIF 2.1.0, the interchange format for static-analysis
results. What `sbom.cyclonedx.json` is to `sbom.json`: a standard-format copy
for other tooling, derived from the contract and never the contract itself.
`findings.json` is what Phase 4 scores and what `report.md` renders from.

**It carries no `schema_version` of ours.** The SARIF schema forbids unknown
top-level keys, so the document carries the standard's version and records the
contract it came from in `runs[].properties.findings_schema_version` — what
invalidates the file, in place of a timestamp that would break byte-identity,
the same device `remediation.json` uses.

**There is no `tool.driver.version`, and that is a decision.** This project has
no version number: no `pyproject.toml`, no `__version__`. A literal would be a
fact-shaped guess pinned to nothing, and a commit hash would move the artifact
when nothing about the input moved. The field is optional in SARIF, so it is
absent rather than invented. `sbom.json`'s `generator_version` is not a
counter-example: Syft's version can be asked of Syft.

**What is deliberately absent**, all optional in SARIF and all volatile or
machine-describing: `invocations` (wall-clock times, command line, working
directory, machine, process id), `automationDetails.guid`, per-result `guid`,
`originalUriBaseIds` and `artifactLocation.uriBaseId` — where an absolute path
would enter — the `artifacts` array with its hashes and modification times,
`rank`, and `suppressions`. Locations are the repo-relative POSIX paths the
findings already carry. The file is byte-identical every run with **no exempt
field**: `narrative` is dropped, so the one model-authored field a finding can
carry never reaches this document.

**`level` is the constant `warning` on every result.** SARIF resolves an absent
level to `warning` anyway, so this is the value that adds no claim. This project
reports no severity — nothing in a grading key could check one — and a
per-result level would be a new, unfalsifiable judgement made in a file that is
only a copy. That constant survives advisory ingestion: a finding's CVSS vector
travels as evidence in the property bag, never converted into a `level`.

**`tool.driver.rules[]` lists only the rules that produced a result here.** An
unfired rule has no defined meaning in SARIF, and a reader would take it for
"ran and found nothing" — the claim `coverage.checks_run` is careful to make
only when it is true.

**`coverage` is carried, and that is the point.** SARIF has no native place for
"this check ran and stayed silent" as against "this check could not look", and a
findings list without that distinction reads as a clean bill — the misreading
`report.md` exists to prevent. So the whole `coverage` block travels in
`runs[].properties`, along with `probe_count`. Every field of it is
deterministic, so carrying it costs nothing the byte-identity rule protects.

**What still does not survive**, and the write-up must not claim otherwise: the
`probes` array itself — only its count crosses — and `surfaces.json`'s
`skipped_files`, which lives in a different artifact.
`runs[].properties.findings_artifact` names the file that has them.

Each result maps one finding: `ruleId` is **the `advisory_id` when one is
set, else `rule_id`** — the one deliberate departure in this derived copy,
because `vexctl filter` joins on `ruleId` being a CVE-/GHSA-scheme identifier
and nothing else, and this is what makes a finding addressable by a VEX
statement at all. A `ruleId` is required in practice regardless: `vexctl`
segfaults on a result without one. `rules[]` is keyed the same way, one rule
per advisory id. `message.text` and the rule's `shortDescription.text` come
from `title`, the location from `file` and `line`, and `finding_id`,
`surface_id`, `surface_kind`, `surface_name`, `purl`, `component_name`,
`mapping_reason`, `detection`, `probe_id`, **`rule_id`** (kept in the bag so
the check name is never lost from a result whose `ruleId` is a CVE) and the
four `advisory_*` fields in the result's property bag. `owasp_id` sits on the
**rule**, not the result: it is constant on the rule, so one fact has one
home.

---

## `artifacts/<system>/<app>/findings.openvex.json` — Phase 2 output

The advisory findings as OpenVEX 0.2.0 statements. What `findings.sarif.json`
is to a SARIF reader, this is to a VEX reader: a standard-format copy derived
from the contract and never the contract itself. `findings.json` is what Phase
4 scores and what `report.md` renders from, and **nothing under `src/` reads
this file** -- it is output for other tools.

**It carries no `schema_version` of ours**, the same problem the SARIF section
solves: the vocabulary is OpenVEX's, announced by `@context`. Unlike SARIF
there is no property bag to record the contract it came from, so the link is
the `timestamp`, copied from `findings.json`'s advisory pin.

**Written by `vexctl`, not by this project's `json.dumps`.**
`src/artifacts/vex.py` decides what to say; `vexctl create` and
`vexctl add --in-place` say it. The reason is the one that made `vexctl` the
right *consumer* for `filter`: OpenVEX is a spec this project does not own, and
a standard tool belongs between a claim and its reader. So the field names, the
key order, `version` and `@id` below are all vexctl's.

**A command of its own**, run after an audit exactly as `src/export_reports.py`
is. An audit therefore needs no vexctl installed, opens no extra process, and
`outputs.write_all`'s artifact count is untouched.

**It is Phase 2's work, not Phase 5's**, though it ships alongside Phase 5's
commands: the emitter is downstream of advisory ingestion, which is what gave a
finding a CVE id to name, and `TODO.md` ticks it under Phase 2 for that reason.
Phase 5's Task 5.3 is the *filter*, which consumes someone else's statements
and stays blocked.

### The audited app is the product; the component is a subcomponent

This is the whole difference between a document worth publishing and one that
restates its input. Putting the component purl in the product slot would say
"this component is affected by this CVE" -- the advisory's own claim, the
component publisher's to make, with the audited app absent from its own
document. So `products[0]["@id"]` is the **app**, named by where it came from
and the commit it was at, and the vulnerable component is a `subcomponent` of
it. The statement then reads "this app is affected by this CVE via this
component, and here is the surface that reaches it", which is what this project
measured and what nothing else asserts.

### Two statuses, and `not_affected` is refused

Measured, not assumed. `mapping.json` holds one entry per LLM **surface**, so
"no surface reaches this component" is not "the vulnerable code is not in the
execute path": on the TypeScript fixture `@langchain/core/messages` is imported
by the app's own source with no surface reaching it. Emitting
`vulnerable_code_not_in_execute_path` from surface reachability alone would
suppress a real vulnerability in code the app runs, which is the worst failure
a security tool has. The reachability this tool computes is evidence that a
component **is** reached; it is never evidence that one is unreached. So a
reached component is `affected`, an unreached one is `under_investigation`
(present, exploitability not assessed by this tool), and `not_affected` is
never emitted -- it would suppress a real vulnerability. The count still lives
in `coverage.advisory_unreached_component_count`, itemized for the report in
`advisory_unreached_components` and still no
claim -- and `tests/test_vexctl_launch.py` asserts that no module under `src/`
passes `not_affected`, `--justification` or `--impact-statement` as a value.

### Document

| Field | Type | Required | Meaning |
|---|---|---|---|
| `@context` | str | yes | `https://openvex.dev/ns/v0.2.0`. vexctl's, and what tells a reader whose vocabulary this is. |
| `@id` | str | yes | Set by this project, not left to vexctl. Measured: vexctl's own `@id` is a canonicalization hash of the document *as created*, and appending statements with `add` leaves it unchanged -- so it would identify the first statement rather than the document. This one is a sha256 over the product and the pinned instant, which is stable per app and per snapshot. **Not a digest of the file**; anything needing one takes sha256 over the bytes, the rule `vex/manifest.json` sets. |
| `author` | str | yes | `agentic-llm-app-auditor`, the constant `sarif.py` already defines, so the project's name has one home. vexctl's default is `Unknown Author`, which would ship as a fact. |
| `version` | int | yes | vexctl's, and **it counts statements rather than revisions**: `create` writes 1 and each `add` increments, so three statements read `version: 3`. Deterministic; named here so no reader takes it for a third revision. |
| `timestamp` | str | yes | RFC 3339, UTC. Mandatory in OpenVEX, **pinned** from `coverage.advisory_db_updated_at` and passed to vexctl as `SOURCE_DATE_EPOCH`. It says when the *advisory data* was taken, the only instant this document has a fact about. |
| `last_updated` | str | conditional | vexctl adds it as soon as `add` runs: **present with two or more statements, absent with one.** The same pinned instant. Recorded because the field set varies with the finding count, which is otherwise a surprise. |
| `statements` | list | yes | In the order `emit_vex` passes them, since vexctl preserves insertion order, sorted by `(advisory_id, purl)`. |

### Each statement

| Field | Type | Required | Meaning |
|---|---|---|---|
| `vulnerability.name` | str | yes | The finding's `advisory_id`, verbatim. CVE- or GHSA-scheme, which is what a VEX consumer joins on. |
| `products[0]["@id"]` | str | yes | The audited app: `<upstream_url>@<upstream_commit>` from its pin. `--product` on the command line when an app has no pin on disk; refused rather than guessed. |
| `products[0].subcomponents[0]["@id"]` | str | yes | The finding's `purl`, verbatim. **Always versioned**, by construction rather than by care: the advisory index is keyed by versioned purl, so a version-less mapping purl never produces an advisory finding at all. |
| `status` | str | yes | `affected` (a component an LLM surface reaches) or `under_investigation` (a component that carries an advisory but no surface reaches, so exploitability is not assessed). Those two only; `not_affected` is never emitted -- see above. |
| `status_notes` | str | yes | How the status was determined: every surface that reaches the component, sorted by `(file, line)`, e.g. `Reached by TavilySearchResults at src/agent.ts:9`. This is the evidence most VEX tooling has to guess at. |
| `action_statement` | str | yes | The `advisory_fixed_version` verbatim, or a fixed constant saying the database records no fix. **Set explicitly**: vexctl's default is the placeholder `No action statement provided`, which would ship as though it were a finding. It is a quotation of the database, not advice -- remediation advice is model-authored and lives in `remediation.json`. |
| `action_statement_timestamp` | str | yes | vexctl derives it from the same pinned instant. **`TZ=UTC` must be in the child's environment**: measured, this is the one field rendered in the local offset, so without it two machines produce different bytes from identical input. |
| `timestamp` | str | yes | Per statement, the same pinned instant. |

### One statement per (advisory, component), not per finding

`known_advisory` emits one finding per **(surface, component, advisory)**, so
two surfaces reaching one vulnerable component are two findings. Two statements
with the same product, vulnerability, status and timestamp are not a richer
document -- OpenVEX resolves competing statements about one product and
vulnerability by timestamp, and identical timestamps leave no defined
precedence. So statements are deduplicated on `(advisory_id, purl)` and
`status_notes` names every reaching surface. **Statement identity is not
finding identity**, and `findings.json` stays the place where one surface's
reach is one record.

### Absence is not a claim, and that is a real limit

`vexctl create` requires a product and a vulnerability, so a zero-statement
OpenVEX document is not something the standard tool can author -- and authoring
one here with `json.dumps` would make this project a second producer of a
format it deliberately does not own. So **the file is written only when the app
has at least one advisory component**, reached or unreached, and its absence means either that or that
the command was never run. Every other artifact refuses that ambiguity
(`surface_count: 0`, `finding_count: 0`); this one cannot, and the distinction
lives in `findings.json`, whose `coverage.advisory_data` and `finding_count`
answer it exactly.

### Determinism

Byte-identical run to run **for a fixed vexctl version**, which the README pins.
The document records that version nowhere, the same trade `sbom.cyclonedx.json`
makes by dropping CycloneDX's `metadata`: a derived copy does not carry its
renderer's provenance, and vexctl's version can be asked of vexctl -- the
argument `findings.sarif.json` uses for its absent `tool.driver.version`. What
*is* recorded is the advisory pin, because it bounds the claim: it is the
`timestamp`.

---

## `artifacts/<system>/<app>/remediation.json` — Phase 3 output

Model-written advice on how to fix what was found. One entry per finding,
always, including the ones no advice survived for.

**It is a separate file from `findings.json`, and that is the mechanism rather
than a preference.** The scorer opens exactly three files -- the grading key,
`findings.json` and `surfaces.json` -- so model prose is *structurally* unable
to reach `matches_key`. Nobody has to remember a rule. It also means
`findings.json` is untouched by the model: its `model_run.status` stays
`disabled`, it stays byte-identical whole-file, and every number Phase 4
reports still rests on static analysis alone.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `2`. Version 2 added `knowledge_base` and each entry's `sources`. |
| `findings_schema_version` | int | yes | The `findings.json` this was written from. What invalidates the file, in place of a timestamp that would break byte-identity. |
| `model_run` | object | yes | `status`, `model_identifier`, `model_digest`, `model_settings`. The same provenance block `findings.json` carries, so two files cannot grow two shapes for one fact. No `ranking`: that is a findings-document idea. |
| `knowledge_base` | object | yes | What grounded the advice, or why nothing did. A **sibling** of `model_run`, not part of it: that block records the model and is shared with `findings.json`, this one records the index. `status`, `reason`, `embed_model`, `embed_model_digest`, `manifest_digest`, `source_count`. Two-way, like the advisory snapshot: `indexed` names its `embed_model` and `manifest_digest`, counts at least one source and gives no `reason`; `not_indexed` gives a `reason` from `no_index`, `index_stale`, `embed_unavailable`, `embed_model_missing` and pins nothing at all — including, deliberately, the model it tried, so `embed_model_missing` says a model was missing without saying which. `manifest_digest` is `sha256` over `knowledge/manifest.json`'s text **as written**, which is how the two files join. |
| `advice_count` | int | yes | `len(advice)`. Always equals `findings.json`'s `finding_count`. |
| `status_counts` | object | yes | `written`, `rejected`, `unavailable`, all three always present, so a reader never subtracts to find a zero. |
| `advice` | list | yes | One entry per finding, sorted by `finding_id`. |

Each `advice` entry:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `finding_id` | str | yes | The join key into `findings.json`. |
| `status` | str | yes | `written`, `rejected`, or `unavailable`. |
| `reason` | str \| null | yes | Required when not `written`, `null` when `written`. Fixed vocabulary, mirroring `Probe`'s outcome/reason pair. |
| `rejected_on` | str \| null | yes | Which *evidence field* the offending token came from — the field name, never its value. The value is already in `findings.json`, and copying it here would put the leaked identifier back into an artifact. |
| `guidance` | str \| null | yes | **Model-authored.** `null` unless `written`. Holds only what to do: what is wrong already lives in the finding's title and evidence. |
| `snippets` | list | yes | **Model-authored.** `[]` unless `written`, and may be `[]` then. At most two. |
| `sources` | list | yes | The passages this entry's advice was grounded on, at most three, each exactly `{source, path, heading, url}`. `[]` unless `written`, and may be `[]` then — a refusal discards its retrieval, because refusal is whole. **The one list in this file that is not sorted**: it is kept in the order the prompt cited it, so a reader can match `[1]`, `[2]`, `[3]` in the model's own words. Under an `indexed` run, `[]` does not distinguish "retrieval returned nothing applicable" from "this finding's embedding call failed" — the second is reported on stderr and reaches no artifact. Fielding that difference would be a v3. |

Each snippet carries `label` — a one-value vocabulary,
`illustration_of_a_safer_pattern`, which deliberately does not read as "apply
this" and is refused if forged — `language` from the parser vocabulary, and
`code` of at most twenty lines.

Each source carries `source` from a one-value vocabulary, `owasp-cheatsheets`
— the same name `knowledge/manifest.json` and the index itself use, so the
three files join on it — `path`, POSIX and relative to that source's clone,
`heading` (the section the passage was cut from, or `null`), and `url`, the
upstream page it is published at, so a reader can open what the advice leaned
on. A source a reader could not follow is a producer bug and raises.

**`remediation.md` names the model that wrote it**, its short content digest and
the decode settings sent, in its third line. A tag alone is not provenance --
one of the models compared is literally `:latest`, which names a different build
after the next pull -- so the digest is what lets a reader six months on know
whose words they are reading. The line is absent when no model ran, because the
"no advice was written" block says that more usefully.

**Three statuses, distinguishable by field rather than by inference.** This is
the point of the shape: a reader can tell *the model wrote nothing* from *the
model wrote something and it was refused*.

| Situation | `status` | `reason` | `guidance` | `sources` |
|---|---|---|---|---|
| Wrote something, it passed | `written` | `null` | text | the passages cited, or `[]` |
| Wrote something, it was refused | `rejected` | `names_app_identifier`, … | `null` | `[]` |
| Wrote nothing | `unavailable` | `model_unavailable` | `null` | `[]` |

**Determinism, in three tiers.** The skeleton is byte-identical; the words are
not, and no test pretends otherwise. `strip_advice_text()` removes tiers (b)
and (c), and what is left is asserted byte-identical across runs and across
model families.

- **(a) byte-identical by construction:** `schema_version`,
  `findings_schema_version`, every `model_run` field, **every `knowledge_base`
  field**, `advice_count`, and the set and order of `finding_id`s.
  `knowledge_base` is here because an index is an *input*, like a reachable
  server: a run must reproduce whether one was present, so
  `strip_advice_text()` keeps it.
- **(b) derived from model output, exempt but constrained:** each entry's
  `status`, `reason`, `rejected_on`, `sources`, and `status_counts`. Stable
  under a fixed seed and a reachable server — not stable *by construction*.
  `sources` is (b) rather than (a) for a reason worth stating: its *contents
  and order* are deterministic given a fixed index, because `stable_order`
  sorts hits by `(distance, id)`; its *presence* follows `status`, which the
  model decides. **"Given a fixed index" is load-bearing.** Chroma's index is
  an approximate nearest-neighbour structure, so rebuilding it from unchanged
  inputs -- same commit, same `content_digest` -- can still swap a passage near
  the cut-off, which changes the prompt and so the answer. Measured: one entry
  moved from `written` to `rejected` across a rebuild at temperature 0 and seed
  0. Two runs against one index reproduce each other; a rebuild is a new input,
  which is why `knowledge_base.manifest_digest` is recorded.
- **(c) model-authored, wholly exempt:** `guidance` and `snippets`.

One degraded case is fully deterministic: with no model reachable, tier (b)
collapses to a constant and the whole file is byte-identical. That still holds
with an index present, and only because a refusal drops its sources — every
entry is `unavailable`, so every `sources` is `[]`, whatever was retrieved.

**When the model cannot be reached, the audit does not fail.** Producing less is
a normal outcome here, exactly as a missing Syft yields no bill of materials.
The file is still written, with `status: "unavailable"` on every entry, because
omitting it would make "the server was down" indistinguishable from "never run".
Two scopes can disagree and a reader needs to know it: a run that reached the
server and then timed out partway records a document-level `used` beside an
entry-level `unavailable`.


## `artifacts/<system>/<app>/planner.json` — Phase 7 output

Which order the checks ran in, and what chose it. **Written by
`src/artifacts/planner_document.py`; read by nothing.** Not the scorer, not the
report, not SARIF, not VEX.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | `2`. Its own version, independent of `findings.json`'s. Version 2 added `surface_selection` and `refused_narrowing`. |
| `surface_selection` | object | yes | What the planner asked each check to examine: check name to a **sorted** list of `surfaces.json` ids. `{}` when no model ran or none was asked for. Sorted, unlike `order`, because here membership is the fact and the sequence means nothing — two adjacent lists with opposite rules, said out loud so neither is tidied into the other. |
| `refused_narrowing` | list | yes | Narrowings the guard rejected, each `{check, surface_ids, reason}`, sorted by `(check, reason)`. `reason` is one of `unknown_check`, `not_narrowable`, `unknown_surface_id`, `empty_selection`. The only evidence the guard ever fired: without it, a model that asked to narrow everything and was refused is indistinguishable from one that asked for nothing. |
| `status` | str | yes | `used`, `unavailable` or `disabled` — the same vocabulary as `model_run`, imported from `artifacts/findings_document.py` rather than redeclared. `disabled` means no model was offered; `unavailable` means one was and could not be reached. |
| `identifier` | str \| null | yes | The model that chose the order. Non-null **exactly when** `status` is `used`, validated in both directions: an unnamed `used` cannot be reproduced, and a named `disabled` is a claim about a model that never ran. |
| `order` | list[str] | yes | The check order actually used: always a permutation of the **graph** checks that were planned. Not of `coverage.checks_run`, which also names the edge checks — `semantic_probe` runs outside the graph and so appears there and never here. **Never sorted** — the order is the fact this file records. |
| `findings_schema_version` | int | yes | The `findings.json` this describes. What invalidates the file, in place of a timestamp — the same device `remediation.json` uses. |

**Why this is a file and not a block in `findings.json`.** The order provably
changes nothing else: `checks/planner.py`'s merge returns a permutation of the
eligible checks, `coverage.checks_run` is sorted, findings and probes are
sorted, and `MAX_STEPS` cannot bind on six checks. So a `planner_run` block
inside `findings.json` would carry the only order-dependent bytes in the file —
and cost the byte-identical claim in `README.md`, a `SCHEMA_VERSION` bump that
makes every artifact on disk unreadable to `report.py` and `vex.py` until
regenerated, and a fabricated record in `run_baseline.py`, which has no planner
to record. Inside `coverage` it would be worse still: `artifacts/sarif.py`
copies `coverage` wholesale into `findings.sarif.json`, so model-chosen bytes
would propagate into an artifact documented as deterministic.

The trade, stated plainly: **nothing reads this file, so the planner's decision
never reaches a score.** That is the price of not making the audit's scored
output depend on a model, and it is the right one.

---

## `artifacts/<system>/evaluation.json` — Phase 4 output

What the tool scored against the grading keys. One file per system per run, and
never one per app: a comparison across apps is not a per-app fact, and
separating the scorecards from the aggregate is how a per-app number gets quoted
without the aggregate's caveats.

#### `apps[].evidence` and `totals.evidence` — evidence-link coverage

Added in schema 3. How many of the findings a system produced carry each kind of
evidence link. **Counts only**, like everything else here.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `findings_considered` | int | yes | The denominator: how many findings the system produced for that app. Equal to `produced_finding_count`, and carried anyway, so no count in this block travels without the number it is out of. |
| `with_code_evidence` | int | yes | Findings with a non-empty `file` **and** a non-null `line` — they point at a line of the audited source. |
| `with_sbom_evidence` | int | yes | Findings that **cite** a component: `component_name` or `purl`. A citation, not a resolved link — nothing here joins against `sbom.json`. `undeclared_dependency` is the case to keep in mind: it sets `component_name` and no `purl`, and its whole point is that the manifest does not declare the package. |
| `with_vex_evidence` | int | yes | Findings carrying a non-empty `advisory_id` — the exact predicate `artifacts/vex.py` branches on, so the two cannot drift. Counts **findings that become** `affected` statements, not statements: `vex.py` groups by (advisory, component), so two surfaces reaching one vulnerable component are two findings and one statement. `findings.openvex.json` need not exist; `src/emit_vex.py` writes it as a command of its own. |
| `apps_included` | list[str] | `totals` only | The apps pooled, sorted. Every pooled block in this file names its apps, so a sample size can never be implicit. |

**Unconditional, unlike `recall` and `precision`.** Those gate on what a grading
key claims; this is measured over the produced findings alone and never touches
the key, so no app is ever excluded and no value is ever null.

**The baselines read as zero by construction, and that is the useful part.**
`baseline_sbom_only` findings carry a component and no file or line;
`baseline_static_rules` findings carry file and line and no component. So one
shows `with_code_evidence: 0` and the other `with_sbom_evidence: 0`. Neither is
a bug, and the contrast is arguably what this block is for.

**No field in this file is a float.** Precision, recall and F1 are absent as
fields, and that is the point: a reader cannot copy a percentage out of it. They
have to divide, and to divide they must hold the denominator. The rates are for
a reader to compute from these counts, beside the `qualifications` that bound
them; no score is printed as a rate anywhere in the tool. (`main.py` prints a
mapping-coverage percentage during a scan. That is a statistic about what the
scan reached, not a result measured against a grading key, and nothing in this
file is derived from it.)

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Currently `3`. Version 2 added `answered_finding_count` to each app score and to the precision pool; version 3 added `evidence` to each app score and to `totals`. |
| `system` | str | yes | `agentic_auditor`, `baseline_static_rules` or `baseline_sbom_only`. Inside the record, not only in the filename, so a table row copied into a write-up carries its own label. |
| `app_count` | int | yes | `len(apps)`. |
| `apps` | list | yes | Sorted by `app`. |
| `totals` | object | yes | Pooled counts, never a mean. |

Each `apps` entry:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `app` | str | yes | The directory name, which is the join key. |
| `upstream_commit` | str | yes | Copied from the key. The join is line-based, and every line is valid only against this commit. |
| `key_source`, `key_verified`, `key_verified_by`, `key_verified_date` | | yes | Copied from the key. A score whose provenance is not in the same file is a score quoted without it. |
| `ground_truth_schema_version`, `findings_schema_version` | int | yes | The versions actually read — what invalidates the score, in place of a timestamp that would break byte-identity. |
| `key_finding_count`, `produced_finding_count` | int | yes | The denominators. |
| `findings_complete`, `expected_surfaces_complete` | bool | yes | Copied from the key, so the gating below is checkable from this file alone. |
| `graded_files_skipped` | list[str] | yes | Skipped files that intersect the key's files, sorted. `[]` is a falsifiable claim; absence would not be. |
| `true_positives`, `false_negatives` | int | yes | Key entries matched, and not. |
| `answered_finding_count` | int | yes | Produced findings that matched *some* entry — findings, where `true_positives` counts entries. They differ exactly when several findings answer one entry (one per advisory on a reached component), and the precision pool reads this count so entry-counts are never printed beside finding-counts. Version 2 added it. |
| `false_positives` | int \| null | yes | **`null` when `findings_complete` is false** — the count is undefined there, and `0` would be a lie. |
| `matched_key_ids` | list[str] | yes | Sorted. |
| `unmatched_finding_ids` | list[str] | yes | Sorted. Deliberately not called false positives: the name must not assert what `findings_complete: false` forbids. |
| `misses` | list | yes | One per unmatched key entry: `key_id`, `owasp_id`, `reason`, and `probe_reason` when a probe gave up on it. |
| `recall_reportable`, `precision_reportable` | bool | yes | Gated by the completeness flags, not qualified by them. |
| `qualifications` | list[str] | yes | Sorted, fixed vocabulary, listed in full below. `unresolved_components` is present when `findings.json`'s `coverage.unresolved_component_count` is non-zero: surfaces the supply-chain check had no component to examine bound an LLM03 number the same way `advisory_data_not_ingested` does. |

The ten `qualifications`, each of which bounds a number rather than describing
a fault: `advisory_data_not_ingested`, `expected_surfaces_not_complete`,
`findings_not_complete`, `key_ai_drafted`, `key_unverified`, `model_disabled`,
`no_key_findings`, `scan_partial`, `small_sample`, `unresolved_components`.
A number quoted without the ones attached to it is quoted too widely.

A miss `reason` is one of `no_check_for_risk_class`, `checked_and_silent`,
`probe_unresolved`, `surface_not_extracted`, `file_skipped` — every one derived
from the artifacts, never from a list of app-specific exceptions. That is what
stops the scorer becoming a place to tune the tool against its own answer key.

### What the scorer refuses

It never reads a `baseline.json`, never matches on `detection`, never widens the
line window when a match fails, never falls back to title or narrative text, and
never asks a model to adjudicate. A missing `findings.json` is an error, not
zero findings. And `evaluation.json` is never an input to anything under
`src/checks/`, `src/detectors/` or `src/artifacts/` — the scorer is the first
component allowed to read the key's ids, and that permission must not flow back
into the tool being scored.

### F1: refused while no app supported both, reportable since one does

The completeness flags decide what is reportable, and for most of this
project's life they did not overlap: the vulnerable app has
`findings_complete: false` (precision undefined) and the clean apps had no key
findings (recall `n/a`), so an F1 would have been a harmonic mean of two
disjoint measurements — a number about no system. `totals` recorded
`f1_reportable: false` with that reason, because an absent field reads as
unimplemented rather than as declined.

**That changed when the TypeScript fixture's key gained `STARTER-01`**: a
complete key with a finding supports both, so `f1_reportable` is now `true`
there. The refusal's *form* survives the flip: F1 is still never a stored
field — the artifact stores the counts and the flag, and the division stays
the reader's, beside the qualifications that bound it.

`totals` carries a recall block and a precision block, each with
`apps_included` and raw counts, so the sample size cannot be hidden: each metric
currently rests on one app.

---

## Later phases

Phase 4's baselines reuse this shape, distinguished by `system`.
