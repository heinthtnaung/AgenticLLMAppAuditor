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
- **Output is deterministic**, with one named exception: `findings.json`'s
  model-authored blocks, defined in its own section below. Everything else,
  including every other field of that file, obeys this rule. Records are sorted,
  keys are sorted, and no
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
| Phase 1 output | `artifacts/<system>/<app>/surfaces.json` | `src/main.py`, and each baseline for its own run |
| Phase 2 output | `artifacts/<system>/<app>/sbom.json` | `src/main.py` |
| Phase 2 output | `artifacts/<system>/<app>/sbom.cyclonedx.json` | `src/main.py`, the same scan in the standard format |
| Phase 2 output | `artifacts/<system>/<app>/aibom.json` | `src/main.py` |
| Phase 2 output | `artifacts/<system>/<app>/mapping.json` | `src/main.py` |
| Phase 3 output | `artifacts/<system>/<app>/findings.json` | `src/main.py`, and each baseline |
| Phase 3 output | `artifacts/<system>/<app>/report.md` | `src/report.py` — **not JSON and not a contract.** A rendering of the two files above for a person to read; nothing consumes it, and nothing may join on it. It is listed here so a reader of this file does not find an artifact it never mentions. |
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

`src/corpus_paths.py` owns these paths. Import them from there rather than
joining strings, so a later phase cannot guess wrong.

**There is deliberately no `target.json`.** One was proposed, to carry the app
name, the upstream commit and the file count next to the output. All three are
already recoverable — the app name is the artifact directory's, and the rest
are in `corpus/evidence/<app>.manifest.json` — so it would be a second place
to state the same facts, and therefore a second place for them to disagree.

**`corpus/<app>/` is a byte-identical copy of upstream at `upstream_commit`.**
If a file with an evidence name ever appears inside it, that file is upstream's
own and must never be read. A test asserts none does.

These three files moved out of `corpus/<app>/` after Phase 1. No field changed,
and the ground-truth, manifest and baseline files keep their own versions: a
relocation is not a record change, and because
the old paths no longer exist a stale reader fails loudly rather than reading
the wrong file.

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

`corpus/evidence/<app>.baseline.json` has no skip list because the fixture has
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
| `version` | str \| null | yes | Read **only** together with `version_source`. Non-null for `pinned`, `locked`, `inferred` and `unconstrained`; always `null` for `unknown`, the one source meaning a constraint was present and no version was ever established. |
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

The rule is ecosystem-neutral; the Python **path** does not exercise it yet.
`requirements_parser.manifests_present` reports only `requirements.txt`, so
`from_lockfile` is always false there and no Python component reaches `locked`
through the CLI today. That is deliberate rather than pending: `from_lockfile`
is currently a document-wide fact, and the generator's Python range-guessing is
on, so a Python lockfile appearing in `scanned_manifests` would relabel every
guessed version as `locked` at once. Reading Python lockfiles needs
`from_lockfile` derived per component first.

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
the Python corpus app, 4 of 5 on the JavaScript one. The reason field exists so
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
`LINE_TOLERANCE = 3`. Exact line equality is wrong here: a human anchors the construct's first line, while a detector may report a few lines into it --
the call inside a multi-line expression, or the `def` under a decorator the
human anchored. Note the window is **not symmetric**: it opens at the key's
line and runs downward, so a finding above the anchor is a different construct
and is never credited to that entry.

The same rule states the **`findings.json` join**, so Phase 4 never has to guess
or parse an id: a produced finding matches a key entry when `file` and
`owasp_id` are equal, `line` falls in that window, and — where the key names
them — `surface_kind` equals the key's `llm_surface` and `surface_name` equals
the key's `surface_name`. **`detection` is recorded, not matched on**: the key's
`either` describes what could in principle reach a finding, while the produced
value says what did this run, so neither constrains the other.

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

## `artifacts/<system>/<app>/findings.json` — Phase 3 output

What the auditor concluded, and what it could not reach. Read by Phase 4's
scorer, which grades it against `corpus/evidence/<app>.ground_truth.json`.

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
| `schema_version` | int | yes | Currently `2`. Version 1 had neither `risk_classes_checked` nor `unresolved_component_count`: a reader could not tell an unexamined risk class from an examined-and-silent one, nor learn that the supply-chain check had surfaces it could say nothing about. |
| `coverage` | object | yes | What the search covered, so a short list is not read as a clean bill. |
| `model_run` | object | yes | What produced the prose. Model-authored content is confined to here and to `narrative`. |
| `probe_count` | int | yes | `len(probes)`. |
| `probes` | list | yes | Every check that ran **or was planned and did not**. Sorted by `probe_id`. May be empty. |
| `finding_count` | int | yes | `len(findings)`. |
| `findings` | list | yes | Sorted by `(file or "", line or -1, owasp_id, rule_id, surface_id or "", purl or "")`. Four of those are nullable on a component-anchored finding, so the key substitutes rather than comparing `None`. May be empty. |

`finding_count: 0` with the file present means "audited, nothing found" — the
same distinction `surfaces.json` makes, and the clean fixture depends on it.

`coverage`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `surfaces_considered` | int | yes | How many `surfaces.json` records the checks ran over. |
| `checks_run` | list[str] | yes | The checks that had something to examine on this app, sorted. Not derivable from `probes`: a check that examined subjects and concluded nothing about any of them leaves no probe record, and that silence is the dangerous one. A check **absent** here could not look at all — no mapping to read, or no file in a language it understands — so its absence is never a clean result. The taint trace reads `ast`, so it is absent on a JavaScript-only app. |
| `advisory_data` | str | yes | `not_ingested` or `snapshot`. **Today always `not_ingested`** — advisory ingestion is Phase 2's one unfinished item, so an LLM03 finding here cites the SBOM and mapping but nothing about what is known to be wrong with a component. |
| `risk_classes_checked` | list[str] | yes | The OWASP ids the checks in `checks_run` are capable of reporting, sorted. Lets a reader — and the Phase 4 scorer — tell **"no check covers this risk"** from "a check covered it and stayed silent", without importing the auditor and scoring a stale artifact against fresh code. LLM01 comes from the taint trace, LLM03 from the supply-chain check, LLM06 from the permissions check; a class missing here was never looked for. |
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
| `model_settings` | object | yes | Only settings that change the output distribution — temperature, seed, and so on. What was actually sent, not what `.env` holds. |
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
| `finding_id` | str | yes | `"{surface_id or component_name or purl or probe_id}:{rule_id}"` — derived from what the finding is, never a counter, and **unique within the document**, which `model_run.ranking` depends on. The anchor is already unique (a surface id is `file:line:kind:name`), so the rule is all that need be added; two findings sharing both are the same finding twice. Opaque to a reader: every part of it is also its own field. |
| `owasp_id` | str | yes | `LLM01`, `LLM02`, `LLM03`, `LLM06` or `AUDITABILITY`, from the **2025** list. Constant on the rule — never model-chosen, because classification is what Phase 4 scores. |
| `rule_id` | str | yes | Which check produced it. Fixed vocabulary. |
| `title` | str | yes | Constant on the rule. Not model-authored: a title that varies per run makes two runs undiffable. |
| `detection` | str | yes | `static` or `probe` — how it was reached this run. The key's `either` is a property of the finding class; the tool never emits it. |
| `surface_id` | str \| null | yes | The `surfaces.json` record. `null` only for a component-anchored finding. |
| `surface_kind`, `surface_name` | str \| null | yes | Copied from the surface, so Phase 4 never parses `surface_id`. |
| `file` | str \| null | yes | Repo-relative POSIX, copied from the surface. Never derived by the model. |
| `line` | int \| null | yes | Copied from the surface. |
| `purl`, `component_name` | str \| null | yes | The SBOM component, where one is evidence. `component_name` without `purl` is the undeclared case. |
| `mapping_reason` | str \| null | yes | The `mapping.json` reason, where the mapping is evidence — e.g. `used_but_undeclared`. |
| `probe_id` | str \| null | yes | Non-null exactly when `detection` is `probe`. |
| `narrative` | str \| null | yes | The model's explanation of this finding. **The only model-authored field on a record.** `null` unless `model_run.status` is `used`. A plain string rather than a wrapper object: there is no second field planned, and the obvious shape wins until there is. |

**A finding with no evidence is not representable**, and that is enforced in the
constructor rather than reviewed for. At least one of `surface_id`, `purl`,
`component_name` or `probe_id` must be present. `detection: "probe"` requires a
`probe_id` naming a `probes` entry whose outcome is `confirmed`, so a probe
finding cannot exist without the record saying the probe ran and confirmed.

**The tool never emits the grading key's `id`.** `VULN1-06` and its siblings are
hand-authored labels; a tool that emits them hands Phase 4 the answer, and every
precision number after that is worthless.

### What the model may not write

`owasp_id`, `file`, `line`, `severity`, `confidence`, and any suggested fix. The
first three are copied from evidence; severity and confidence have no field in
the grading key, so nothing could check them; and a model-written patch is one
copy-paste from crossing the no-auto-fixing boundary.

---

## `artifacts/<system>/evaluation.json` — Phase 4 output

What the tool scored against the grading keys. One file per system per run, and
never one per app: a comparison across apps is not a per-app fact, and
separating the scorecards from the aggregate is how a per-app number gets quoted
without the aggregate's caveats.

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
| `schema_version` | int | yes | Currently `1`. |
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

### Why F1 is refused today

The completeness flags decide what is reportable, and on this corpus they do not
overlap: the vulnerable app has `findings_complete: false`, so precision is
undefined there; the clean app has no key findings, so recall is `n/a` there.
No app supports both, so an F1 would be a harmonic mean of two disjoint
measurements — a number about no system. `totals` records
`f1_reportable: false` with the reason, rather than omitting the field, because
an absent field reads as unimplemented rather than as declined.

`totals` carries a recall block and a precision block, each with
`apps_included` and raw counts, so the sample size cannot be hidden: each metric
currently rests on one app.

---

## Later phases

Phase 4's baselines reuse this shape, distinguished by `system`.
