# Phase 6 — Knowledge-grounded remediation advice (RAG)

**Goal:** stop the remediation advice resting on the model's memory. Ground it
in passages retrieved from a pinned local knowledge base, and attribute every
passage used, so a reader can open the page the advice leaned on.

**Input:** `findings.json`, plus a knowledge base built out-of-band under
`knowledge/`. **Output:** `remediation.json` v2 — the advice as before, with a
`knowledge_base` block saying what grounded the run and a `sources` list on
every entry saying what grounded it — and a `Grounded on` list in
`remediation.md`.

**Scope rule: this phase touches advice and nothing else.** Not
`findings.json`, not `owasp_id`, not `model_run`, not the scorer, not a
detector. Phase 4's numbers must be exactly what they were before this phase
began, and `tests/test_scorer_boundary.py` was widened to hold it: `retrieval`
joins the trees the scorer may not read from, because `checks/advise.py` is fed
by it and an unguarded tree is the one a grading-key read could route through.

## What this is not: the Phase 0 question, answered up front

Phase 0 considered **LLM08 (vector database / retrieval weaknesses)** and
**dropped** it, because no graded app performed retrieval, so its recall would
have been 0 of 0. Adding retrieval here does not revisit that.

- Phase 0 dropped retrieval as a **risk class the auditor detects**.
- Phase 6 adds retrieval as a **mechanism the auditor uses on its own advice**.

Two different things, and the distinction is load-bearing rather than
rhetorical: if it collapsed, the honest move would be to add LLM08 to the
grading keys, and nothing would exercise it. Nothing in this phase makes
the auditor able to find a retrieval weakness in someone else's code.

## The flow this plans

```
knowledge/<source>/  ──chunk──►  passages  ──embed──►  ChromaDB index
   (a pinned clone)                                        │
                                                           │  per finding:
findings.json ──► advise.py ──► prompt ◄──── passages ◄─────┘  embed the
                     │              ▲                          finding's own
                     │              └─ the risk class reference  words
                     ▼                  (a fixed table, not a search)
              remediation.json  ──►  knowledge_base + sources
```

Two things enter the prompt that did not before. The **reference entry** is a
deterministic lookup on `owasp_id` — a table, not a search — and is injected
whether or not an index exists. The **passages** are retrieved, and only when
an index exists and the embedding model answers.

## Before starting: four things settled

**1. ChromaDB is a choice, and the record says so.** It is the fourth exception
to this project's stdlib-first rule and the only one that cannot argue the
standard library was unable to do the job: exact cosine search over a few
thousand vectors is a short loop, and this project would normally write it. It
is here because it was asked for by name. `requirements.txt` records the cost
measured on 2026-09-04 — about sixty transitive packages, including
`onnxruntime`, five `opentelemetry` packages, `huggingface_hub`, `kubernetes`,
`grpcio` and a web server, none of which is used, because the store is opened
as a local file and never as a service.

**2. Two of its defaults would break the offline guarantee.** Both are closed
in `src/retrieval/store.py` with a test on each, and both were measured before
the module was written, not assumed:

- Its **default embedding function downloads a model from the internet** the
  first time it is asked to embed text. So a refusing embedding function is
  always attached, and the module's API accepts precomputed vectors only —
  `src/model_client.py` computes them against local Ollama. Chroma is
  structurally unable to embed anything here.
- Its **client reports usage telemetry** unless told not to, so it is told not
  to, the same way the SBOM generator's update check is.

A third trap is not a default but a behaviour: **opening a client on a missing
path creates the database file.** An audit that merely *looked* for an index
would therefore write one. So `retrieval/manifest.index_present()` checks for
`knowledge/index/chroma.sqlite3` before any client is opened, and it lives in
`manifest.py` rather than `store.py` precisely so asking the question costs no
chromadb import.

**3. The knowledge base is data, and is not committed.** An upstream clone per
source and the index built from it are fetched and built out-of-band and
gitignored — the same policy as any audited tree and the advisory database, for
the same reason: this repository holds no other project's content. Only
`knowledge/manifest.json` and `knowledge/README.md` are committed. The
auditor makes no network call, so nothing under `src/` fetches a clone;
`src/index_knowledge.py` reads one that is already there.

**4. The `LLM02` edition problem is real, and is stated rather than fixed.**
This project uses `LLM02` for insecure output handling, which is the **2023**
numbering; in the 2025 list that risk is **LLM05** and LLM02 is Sensitive
Information Disclosure. Renaming a graded id would move Phase 4's numbers, so
the rename is deferred (`docs/TODO.md`). Until then
`retrieval/owasp_reference.py` states both halves in the entry itself and cites
the 2025 LLM05 page, and the prompt no longer asserts an edition the reference
block would contradict. `AUDITABILITY` is this project's own risk class, not an
OWASP entry: it is sourced to the project and carries no owasp.org URL, because
a fabricated citation is the worst thing a security report can hold.

## Task 6.0 — Split `artifacts/remediation.py` before extending it

224 lines doing two jobs, and about to gain a third. The judging half — `judge`,
`app_identifiers`, the size caps and patch regexes, plus `evidence_line` moved
out of `checks/advise.py` and a new shared `foreign_owasp_ids` — moves to
`artifacts/advice_rules.py`; `remediation.py` keeps the shape and the
vocabulary and never imports the rules. The dependency runs one way: the rules
import the vocabulary, never the reverse.

**Done when** it is verifiable as a pure move: the recorded judging cases give
identical results before and after, and a full audit of the same app is
byte-identical across every artifact.

## Task 6.1 — The knowledge base and its index command

Four modules and one command, none over the 200-line cap.

- `retrieval/chunks.py` — pure. Split markdown on headings, drop fenced code
  and table rows, cut long sections to `CHUNK_CHARS` with
  `CHUNK_OVERLAP_CHARS` of overlap so a sentence spanning a boundary survives
  in one of them. Code is dropped on purpose: a retrieved snippet in another
  language, pasted into advice, is worse than no snippet.
- `retrieval/manifest.py` — pure. The `SOURCES` registry (the one place a
  source's URL, licence and file selection are written), the commit read from
  the clone's own `.git` files without launching a program, and the content
  digest. A clone can be edited without moving `HEAD`, so the commit alone is
  not a pin; the digest is what catches that.
- `retrieval/store.py` — the one chromadb importer, per Task 6.1's second
  settled point above.
- `src/index_knowledge.py` — one command: chunk, embed via Ollama, rebuild the
  index, write `knowledge/manifest.json`. **It raises rather than degrades**,
  unlike everything an audit does: an index half built is worse than none.

The manifest is written **last** but digested **first** — the index records the
digest of the manifest text, so the text has to be final before the index
exists.

**Done when** the index builds from the pinned clone, the manifest pins commit,
content digest, embed model and chromadb version, and the store tests pass
under the blocked-socket fixture.

## Task 6.2 — Embeddings, retrieval, and the OWASP reference

- `model_client.embed` over `/api/embed`, with `ModelNotPulled` raised on the
  404 Ollama answers for a model it does not have. **The network stays in one
  module**: `model_client.py` is the only file under `src/` that opens a
  connection, a test holds that by name, and retrieval asks it for vectors
  rather than opening one of its own.
- `retrieval/passages.py` — the pure half: `query_text`,
  `drop_foreign_owasp`, `stable_order`, `within_budget`, `as_source`,
  `reference_block`. Hits in, hits or text or attributions out; no I/O and
  nothing to stub. *(Split out of `retrieve.py` during Task 6.4, when that file
  reached 232 lines doing two jobs and rule 18 came due.)*
- `retrieval/retrieve.py` — the two edges, and **one `probe()` per run** that
  owns every reason a run is ungrounded. One producer for `KNOWLEDGE_REASONS`
  means a reader of `remediation.json` never meets a reason no code can write.
- `retrieval/owasp_reference.py` — the reference entry per `owasp_id`, by
  lookup, with the edition care described above.

Two decisions inside retrieval worth recording. A passage naming a **different**
risk class is dropped, because a passage about LLM01 attached to an LLM06
finding is an invitation to re-classify, and re-classification is exactly what
Phase 4 scores — which is why `k` is oversampled before the drop. And the
reference block is bounded in characters and placed **before** the
instructions: Ollama silently truncates the *front* of a prompt that overruns
its context, so an overrun must cost passages, never rules.

**Done when** a finding retrieves attributed passages from a built index, and
every reason in `KNOWLEDGE_REASONS` has a test that produces it.

## Task 6.3 — `remediation.json` v2 and the wiring

`knowledge_base` as a top-level sibling of `model_run` — that block records the
model and is shared with `findings.json`; this one records the index. `sources`
on every entry, validated in `advice_entry`, and **stripped with tier (b)**: an
attribution is not model-authored, but it is carried only beside a written
answer, so its presence follows a field that is.

One cross-check in the document builder: an ungrounded run may not have an
entry citing a passage. Its mirror is deliberately **absent** — an `indexed`
run where no entry cites anything is legal, and arises four honest ways (every
per-finding embed failed, every hit was dropped or over budget, every entry was
refused, or there were no findings).

**Done when** the schema-keeper's reader list is exhausted, and an
index-present, model-unreachable run is byte-identical.

## Task 6.4 — Docs, and the measurement

`docs/SCHEMAS.md` (the v2 tables, the three determinism tiers with `sources` in
(b), and a `knowledge/manifest.json` section beside the `vex/manifest.json`
one), `docs/FLOW.md` section 5, the README, and `.claude/AGENTS.md`.

The measurement: **the same findings advised with and without retrieval, with
the refusal counts compared.** It is a comparison of the two configurations, on
the same input, and it is the only quantitative claim this phase makes.

**Taken 2026-09-04.** 25 findings across three fetched apps, everything else
held: `qwen2.5-coder:7b-instruct` at temperature 0 seed 0,
`nomic-embed-text:latest`, the index at manifest `1e37fcd1be24`. Refusals fell
from **13 of 25 to 7 of 25**; `snippet_too_long` fell 6 → 1 and
`names_app_identifier` 7 → 6; all 18 grounded written entries cited three
passages each. **But it is not uniform**: on `RepoAgent`, the one app that
refused nothing ungrounded, grounding introduced two refusals. The per-app
table is in `docs/TODO.md`, and the three caveats it carries belong to any
quotation of these numbers: the counts measure whether an answer survived the
*output contract*, not whether the advice is good; there is no grading key for
advice quality and this phase does not invent one; and the grounded prompt is
longer by construction, so this is not a controlled comparison of wording.

## Task 6.5 — MITRE ATLAS as a second source — deferred

Its data is YAML with custom tags, needing PyYAML: a fifth stdlib exception for
one file, and the very package the fixture's `VULN1-06` flags as used but never
declared. Revival path: the STIX JSON bundles in
`mitre-atlas/atlas-navigator-data`, readable with the standard library.
`KNOWLEDGE_SOURCES` then gains `mitre-atlas` with a schema bump.

## Phase 6 exit checklist

- [x] `knowledge/manifest.json` pins commit, content digest, embed model,
      embed model digest and chromadb version. *(Built for real, not only
      synthetically: 121 files, 3,484 passages, chromadb 1.5.9.)*
- [x] Chroma cannot embed (refusing function asserted) and does not phone home
      (telemetry setting asserted).
- [x] Looking for an absent index writes nothing.
- [x] Every `KNOWLEDGE_REASONS` value has a test that produces it.
- [x] Every `sources` entry a run writes is openable: real path, real URL.
      *(Validated by the producer, and 54 were written in the measurement.)*
- [x] A refused answer carries no sources.
- [x] `src/evaluation/` imports nothing from `retrieval`.
- [x] The with/without-retrieval measurement is taken and recorded with its
      denominators.
- [ ] `findings.json` is byte-identical to its pre-phase bytes on the same app.
      **Not yet checked against a pre-phase artifact**, because the graded
      graded corpus was removed (2026-09-04). What *is* asserted structurally: the
      scorer cannot open `remediation.json`, `src/evaluation/` may not import
      `retrieval`, and `findings.json` is written before any model or index is
      consulted. That is the mechanism; the byte comparison is the evidence, and
      it is still owed.

## Notes and honest cautions

**Attribution is not endorsement, and the report should not imply it is.** A
cited passage says *this is what the advice was grounded on*, not *OWASP
recommends this fix for your code*. The model still wrote the words, and the
`Grounded on` list sits under advice the report has already attributed to a
named model at a named digest.

**Retrieval quality is not measured here, and no key would measure it.**
There is no relevance judgement set for "which cheat sheet passage should
ground this finding", so nothing in this phase claims the retrieved passages
are the *best* ones. What is claimed is narrower and checkable: they are the
nearest by cosine distance in a pinned index, they are recorded, and they can
be opened. Cosine similarity over a general-purpose embedding model retrieves
by surface wording, so a passage about a different technology with similar
vocabulary can outrank a relevant one. Both were observed while building this
phase: a hand-written prompt-injection query retrieved DOM XSS passages (on the
word "untrusted"), while the real audit of `fetched/ai-bom` retrieved the AI
Agent Security, Prompt Injection Prevention and Secure Coding with AI sheets
for its two excessive-agency findings — apt ones. Retrieval is therefore useful
and unreliable in the same breath, which is why the reference table exists
independently of it and is injected whether or not an index is there.

**Rebuilding the index can change the advice, and that is not a bug in the
pins.** Observed 2026-09-04: the same audit of `fetched/ai-bom`, same model at
temperature 0 and seed 0, gave two written entries before the index was rebuilt
and one written plus one `snippet_too_long` after. The manifest was
byte-identical across the rebuild -- same commit, same `content_digest`, same
embed model -- because the *inputs* had not changed. What changed is the
candidate set the store returned: Chroma's HNSW index is an approximate
nearest-neighbour structure and the collection was recreated, so a passage near
the cut-off can swap places. A different passage is a different prompt, and a
different prompt is a different answer.

This is why `sources` is determinism tier (b) rather than (a), and the
qualifier in `SCHEMAS.md` -- "deterministic *given a fixed index*" -- is
load-bearing rather than hedging. It is also the argument for pinning the index
at all: without `manifest_digest` recorded in the artifact, "which passages
grounded this advice" would be unanswerable a month later. Two runs against
*one* index reproduce each other; a rebuild is a new input.

**A licence obligation comes with quoting.** Passages are reproduced verbatim
into `remediation.json` and `remediation.md`, so the source's licence is
recorded in the manifest, named once in the report, and every citation carries
its URL.

**One asymmetry is a deliberate loss.** An ungrounded run may pin nothing, so
`reason: embed_model_missing` ships with `embed_model: null` — the reader is
told a model was missing and not which one, in the one case where the name is
the whole diagnosis. Recording a pin for a run that read nothing would
over-claim, so the loss is accepted and stated in `SCHEMAS.md` rather than left
to be inferred.

## What changed during implementation

Recorded here rather than folded silently into the tasks above.

- **`nomic-embed-text` had to be spelled with its tag.** Ollama lists a pulled
  model as `name:latest` and `model_digest` looks it up by that exact string, so
  the untagged default indexed fine and pinned nothing: `embed_model_digest`
  came out `null` on the first real build. `AUDITOR_EMBED_MODEL` now defaults to
  `nomic-embed-text:latest`, matching how the other two model settings are
  written, and the index was rebuilt.
- **`_read_manifest` validates rather than trusts.** `knowledge_provenance`
  refuses a source count below one, and it *raises* — so a hand-edited manifest
  saying `0` killed the audit that merely looked at it, which is the opposite of
  what that function's own docstring promises. Every field it reads is now
  checked there, and a manifest from a future schema version degrades to
  `index_stale` deliberately rather than by accident.
- **`retrieve.py` had to be split.** At 232 lines it was doing two jobs, and
  rule 18 caps a module at roughly 200. The pure choosing and citing of
  passages moved to `retrieval/passages.py` (74 lines), leaving `retrieve.py`
  at ~190 for the two edges and the degrade decisions. Two files are now close
  to the cap and both are deliberately left alone, with their cuts named so the
  next person does not have to find them: `artifacts/remediation.py` at ~207,
  where the cut is its source-attribution validation; and
  `retrieval/manifest.py` at ~195, doing four jobs since the index pin keys
  moved in, where the cut is `commit_from_git_dir` and its two helpers into a
  module of their own. Whichever gains the next field goes first.
- **The `Grounded on` list was corrupting the HTML and PDF.** It was written as
  indented bullets; `markdown_html.py` reads a bullet only at column zero, so
  the whole run fell through to a paragraph and shipped its `- ` marks as text
  — on *every* written entry, not only grounded ones, since the reference bullet
  is always present. The citations are now flat siblings of a label on its own
  line, and the exporter's tests stage a written entry so the next such break is
  visible.
