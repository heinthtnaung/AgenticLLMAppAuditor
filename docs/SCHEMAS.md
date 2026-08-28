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
| Phase 2 output | `artifacts/<app>/sbom.json` | `src/main.py` |
| Phase 2 output | `artifacts/<app>/sbom.cyclonedx.json` | `src/main.py`, the same scan in the standard format |
| Phase 2 output | `artifacts/<app>/aibom.json` | `src/main.py` |
| Phase 2 output | `artifacts/<app>/mapping.json` | `src/main.py` |

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

## `artifacts/<app>/surfaces.json` — Phase 1 output

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

## `artifacts/<app>/sbom.json` — Phase 2 output

What the app's dependency manifests and the SBOM generator say about its
components.

This is not CycloneDX, and the reason is not determinism -- a valid
deterministic CycloneDX document sits beside it as
`artifacts/<app>/sbom.cyclonedx.json`. It is that CycloneDX has no field for
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
