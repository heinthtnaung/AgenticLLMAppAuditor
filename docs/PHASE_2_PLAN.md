# Phase 2 — SBOM/AIBOM, Advisories & Mapping

**Goal:** answer "which dependency does this LLM surface come from, and is
anything known to be wrong with it?" — by building a bill of materials for each
audited app and joining it to the surfaces Phase 1 found.

**Input:** `artifacts/<app>/surfaces.json` from Phase 1.
**Output:** `sbom.json`, `aibom.json`, `mapping.json`.

**Scope rule:** Phase 2 is still deterministic. No LLM reasoning, no probing.
The model client stays unused until Phase 3.

---

## Coding rules

Every task below is held to the binding rules in
[`CODING_RULES.md`](./CODING_RULES.md), and every JSON contract goes through
`schema-keeper` **before** the code that writes it (rule 10).

---

## Before starting: two things to settle

**Sign off the OWASP subset.** Supply chain is the risk this whole phase
reports, and it is `LLM05` in the 2023/24 list but `LLM03` in the 2025 list.
The code currently emits `LLM05`; `TODO.md` Phase 0 proposes `LLM03`. Deciding
after Phase 2 ships means relabelling every finding it produced. See `TODO.md`
B6.

**Know how much of the corpus this phase can actually reach.** On the one
corpus app, **6 of 19 surfaces carry a third-party module**:

| Surfaces | `module` | Joinable? |
|---|---|---|
| 6 | `langchain.agents`, `langchain_litellm`, `streamlit` | yes |
| 2 | `os`, `yaml` | standard library or renamed distribution |
| 11 | `""` | no — `open()`, `cursor.execute()`, methods on local variables |

An unmapped surface is therefore the **normal** case, not a defect. Design for
it: `mapping.json` must be able to say "this surface has no component" without
that reading as a failure. Resolving `cursor.execute` back to `sqlite3` needs
dataflow, which is Phase 3's taint probe.

---

## Task 2.1 — Tooling and the offline question

Phase 2 introduces the first genuine tension with the offline boundary:
advisories live on the internet.

**Do:**
- Install an SBOM generator (Syft is the reference choice; `cyclonedx-py` is a
  lighter alternative for Python-only). Record which, and its version, in
  `requirements.txt` or the README as appropriate.
- Decide and write down the **advisory data policy**. Generating an SBOM is
  local, but fetching CSAF/VEX advisories is not. The auditor must not make
  network calls at runtime, so advisories have to be downloaded ahead of time
  and read from disk, exactly as the corpus is.
- Record where that snapshot lives, how it is pinned, and how it is refreshed.

**Done when:** an SBOM can be produced for the corpus app with no network
access, and the advisory policy is written in `SCHEMAS.md` with the safety
boundary in `AGENTS.md` updated to match if it needs to be.

**Rule reminder:** if the boundary has to move, move it deliberately and say so
— do not let a runtime download appear by accident.

---

## Task 2.2 — Generate the SBOM

**Do:**
- Write `src/sbom.py`, one job: run the chosen generator over an app directory
  and normalise its output into `artifacts/<app>/sbom.json`.
- Store CycloneDX or SPDX as produced; do not invent a third format.
- Components are identified by **PURL** (`pkg:pypi/langchain@0.3.25`), because
  that is the identifier advisories use.
- Keep the output deterministic: sorted components, no timestamps, no absolute
  paths. The Phase 1 artifact rules apply unchanged.

**Done when:** `artifacts/vuln-app-1-support-agent/sbom.json` lists the app's
declared dependencies with PURLs, and two runs produce byte-identical files.

---

## Task 2.3 — Resolve an import name to a package

This is the join, and it is the part most likely to be quietly wrong.

An import name is not a package name. `import yaml` comes from **PyYAML**;
`import sklearn` from **scikit-learn**. Getting this wrong produces a mapping
that looks complete and is not.

**Do:**
- Write `src/component_match.py`, one job: given a surface's `module` and
  `language`, return the PURL of the component it belongs to, or nothing.
- Apply the package-root rule already documented in
  [`SCHEMAS.md`](./SCHEMAS.md): npm scoped names take two path segments,
  unscoped take one; Python takes the first dotted segment.
- Then map that root to a distribution name. Prefer the installed metadata
  (`importlib.metadata.packages_distributions()`) over a hand-written table,
  so the mapping is derived rather than guessed.
- Return nothing for the standard library and for first-party code. Both are
  correct answers, not failures.

**Done when:** `yaml` resolves to PyYAML, `langchain.agents` to `langchain`,
`@langchain/langgraph/prebuilt` to `@langchain/langgraph`, and `os` and `""`
resolve to nothing — each with a test.

---

## Task 2.4 — The AIBOM

An SBOM lists packages. An AIBOM lists the AI-specific pieces: which models the
app uses, which tools it exposes, which agents it defines.

**Do:**
- Define the schema with `schema-keeper` first.
- Write `src/aibom.py`. Most of its content is **already in `surfaces.json`**:
  `AGENT_DEF` surfaces name the model clients and agents, `TOOL_CALL` surfaces
  name the tools. Derive from that artifact rather than re-parsing the source.
- Record the model identifier where the source states it literally
  (`ChatOpenAI(model="gpt-4o")`). Where it comes from configuration, record
  that it is configured rather than inventing a value.

**Done when:** `aibom.json` lists the corpus app's model client, its two tools
and its agents, each traceable to the `surfaces.json` record it came from.

**Rule reminder:** an AIBOM entry that cannot be traced back to a surface `id`
is an entry nobody can check.

---

## Task 2.5 — Map surfaces to components

**Do:**
- Write `src/mapping.py` producing `artifacts/<app>/mapping.json`: each entry
  joins a surface `id` to a component PURL, or records that there is none.
- Say **why** there is none — standard library, first-party, or unresolved.
  Those three are different facts and a reader should not have to guess.
- Report coverage: how many surfaces mapped, how many did not, and why. A
  mapping that silently covers a third of the surfaces looks the same as one
  that covers all of them.

**Done when:** every surface in the corpus app appears in `mapping.json`
exactly once, the six third-party surfaces carry a PURL that exists in
`sbom.json`, and the coverage figure is printed rather than buried.

---

## Task 2.6 — Advisory ingestion

**Do:**
- Write `src/advisories.py`, one job: read the local advisory snapshot and
  return what is known about a PURL.
- Match on PURL and version range. A component with no advisory is the common
  case and must not read as an error.
- Keep matching conservative. Claiming a dependency is vulnerable when it is
  not is worse than saying nothing, because it is the claim a reader will check
  first.

**Done when:** a component with a known advisory reports it with its
identifier and severity, a component without one reports nothing, and no
network call is made.

---

## Task 2.7 — Validation

**Do:**
- Extend the grading key: record which findings are supply-chain findings and
  which component each names.
- Write the tests as usual, through `test-writer`, against the corpus app.
- Cross-check the SBOM by hand against the app's `requirements.txt`. A
  generator can miss transitive dependencies or misread a pin, and this is the
  phase where that would go unnoticed.

**Done when:** the tests pass, and a manual review confirms the SBOM matches
what the app actually declares.

---

## Phase 2 exit checklist

- [ ] OWASP subset signed off, so supply-chain findings carry the right id.
- [ ] SBOM generated offline, deterministic, PURL-identified.
- [ ] Import-to-package resolution correct for the renamed cases.
- [ ] AIBOM derived from `surfaces.json`, every entry traceable to a surface.
- [ ] `mapping.json` covers every surface, with a stated reason where no
      component applies.
- [ ] Coverage reported, not implied.
- [ ] Advisories read from a pinned local snapshot; no runtime network call.
- [ ] All three schemas defined by `schema-keeper` before their writers.
- [ ] Tests pass; `project-guard` clean on the finished code.
- [ ] `TODO.md` ticked in the same change as the work.

**Artifacts produced this phase:** `artifacts/<app>/sbom.json`,
`aibom.json`, `mapping.json` — consumed by Phase 3's findings and Phase 4's
scorer. Field lists go in [`SCHEMAS.md`](./SCHEMAS.md).

---

## Notes and honest cautions

**The corpus is one app with six joinable surfaces.** That is a thin base on
which to claim a mapping works. Consider bringing a second app back at the
*start* of this phase rather than the end — the JavaScript fixture in
particular, since npm package-root rules differ from Python's and are currently
untested against real code.

**A generated SBOM is evidence, not truth.** Syft reports what it can see. A
dependency installed but undeclared, or declared but unused, will be wrong in
opposite directions. Say which the tool did in the write-up.

**Advisory data ages.** A pinned snapshot is reproducible, which is what the
evaluation needs, but it is also out of date the day after it is taken. That
trade-off is worth a sentence in the report rather than a footnote.

**Do not start Phase 3 here.** Reachability — whether a surface's component is
actually exercised — is a probe, not a mapping. Phase 2 says what is connected
to what.
