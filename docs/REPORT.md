# An Agentic LLM-Application Security Auditor

## Interim Project Report

**Hein Thet Naung · Neo Jia Wei · Tan Bing Hong**

*Master's degree project. This report covers Phases 1 to 5, including the
evaluation and its baselines. Every number is labelled with the run that
produced it, because the detector set and the grading key both changed during
the work and an unlabelled number would be quotable without its context.*

---

## Abstract

Applications built on large language models introduce failure modes that
conventional static analysis does not look for: instructions smuggled in
through data, agents given more capability than their task requires, and no
durable record of what an agent actually did. This project builds an offline,
human-in-the-loop auditor that analyses an LLM application's source and reports
findings mapped to a chosen subset of the OWASP Top 10 for LLM Applications
(2025 edition), supported by software and AI bill-of-materials evidence.

The system is complete across five phases. A static **LLM surface extractor**
identifies the four places where an application meets a model — prompt
templates, agent definitions, tool definitions, and the points where outside
data enters — and records each with an exact file and line, reading Python
through the standard library's `ast` and JavaScript/TypeScript through
tree-sitter. Supply-chain evidence joins each surface to the dependency behind
it, and since advisory ingestion landed, to **what is publicly known to be
wrong with that dependency**: Trivy runs offline as a second external
generator, and a finding is raised only when a vulnerable component is
*reached by an LLM surface* — the join no off-the-shelf scanner makes. An
agentic auditor runs the checks under a bounded planner and reports what it
could not examine with the same prominence as what it found. The findings are
re-emitted in two standard formats — SARIF for code scanning, and OpenVEX
statements this project *authors*, each carrying the reaching surface as the
evidence most VEX tooling has to guess at. A scorer grades everything against
hand-written keys and against two baselines.

The scorer reports **counts, never rates**: precision, recall and F1 are absent
as fields by design, so no number can be quoted without the denominator and the
qualifications that bound it. The headline comparison is reported first because
it is not a win: on the verified pre-advisory run, a five-rule regex baseline
reaches more of the grading key than the auditor does.

---

## 1. Introduction

### 1.1 Problem

An LLM application is not only the model. It is the prompts that instruct it,
the agent loop that drives it, the tools it is permitted to call, and every
channel through which text reaches it. Each is a place where the application's
behaviour can be changed by data rather than by code, which is what makes these
systems difficult to reason about with existing tooling.

Conventional static analysis has no concept of a prompt or a tool, so it cannot
say whether an agent has been given a shell, or whether a web page fetched at
runtime is concatenated into a system instruction. Dedicated LLM red-teaming
tools exist, but they probe a running system from the outside and therefore
cannot point at the line of code responsible. Dependency scanners know which
package versions are dangerous, but not whether the dangerous code sits on any
path a model can influence.

### 1.2 Aim

To build an auditor that reads an LLM application's source, identifies where
the application meets the model, and reports security findings that a developer
can act on — each tied to a specific file and line, an OWASP risk category, and
where relevant a dependency that carries the risk.

Three constraints shape the design throughout:

- **Offline.** Auditing makes no external network calls. Source code being
  audited is often proprietary, and sending it to a hosted model to be analysed
  would be an unacceptable disclosure. Acquiring a repository is a separate
  command, so the guarantee stays a guarantee rather than an approximation.
- **Human-in-the-loop.** The tool reports. It never edits, patches, commits, or
  merges the code it audits.
- **Evidence-backed.** Every finding cites a location and, where applicable, a
  component from a bill of materials and the advisory known against it, so a
  reader can check it.

### 1.3 Research questions

- **RQ1.** Can the places where an application meets a model be identified
  reliably from source alone, across more than one language and framework?
- **RQ2.** Does combining static surface extraction with supply-chain evidence
  and agentic probing detect issues that either approach alone misses?
- **RQ3.** How does detection quality vary across locally-runnable model
  families?

RQ1 is addressed by the extractor and its corpus results. RQ2 now has its first
measured evidence: the supply-chain finding class the auditor reaches alone
requires joining a surface to a component, which no baseline has (§6.3), and
advisory ingestion extends that join to known vulnerabilities. RQ3 remains
open: the local model writes remediation advice but no scored artifact, so
model choice cannot yet move a number.

### 1.4 Scope

Four risks from the OWASP Top 10 for LLM Applications, **2025 edition**, are in
scope: **LLM01** prompt injection (direct and indirect), **LLM03** supply chain,
**LLM06** excessive agency, and **inadequate auditability of agent actions**,
which is not a stock OWASP entry and is included deliberately. LLM02 (insecure
output handling) appears in the grading key of the vulnerable fixture. The
edition matters and is stated wherever a category is cited: supply chain is
LLM03 in the 2025 list and was LLM05 before it.

All five named classes now have a check behind them. Every report the tool
writes still states its own coverage explicitly, because a findings list that is
silent about what it did not examine reads as a clean bill.

**Both of the two newest checks landed on 2026-09-05, after every measurement in
this report was taken.** `src/checks/output_handling.py` (LLM02) and
`src/checks/auditability.py` (AUDITABILITY). Read the numbers below as measured
against a tool that covered three of five classes, not five — and note that the
grading keys went with the corpus, so this cannot be re-measured to show what
the two added.

**Both establish less than their risk class does, and both say so in their
title.** `output_handling.py` reports a query built by string interpolation, not
that the model wrote what was interpolated. `auditability.py` reports an agent
constructed with no callback or handler argument, not that its actions go
unrecorded — and its false-positive rate is measured, not estimated: on
`RAG-Examples-with-Langchain`, which imports `logging` and calls `logger.info`
roughly thirty times, it reports **all three** of that app's agents, because the
logging happens nowhere the constructor can see. That is accepted deliberately:
the alternative is a registry of blessed handler class names, which is the
LangSmith name-matching this project rejected on record.

---

## 2. Background

### 2.1 Where an LLM application can fail

Four categories are directly relevant to this work.

**Prompt injection** occurs when text that the system treats as data is
interpreted by the model as instruction. It is *direct* when the attacker types
it, and *indirect* when it arrives through a document, a web page, or a database
row that the application inserts into a prompt. Indirect injection is the harder
case, because the untrusted text may enter far from where the prompt is built.

**Excessive agency** is the risk that follows from giving a model tools. A tool
that runs shell commands, executes generated code, or queries a database gives
the model reach into systems the user never authorised. The severity depends not
on the model but on what the tool is permitted to do.

**Supply chain** risk arises because LLM applications lean on fast-moving
frameworks. A dependency can introduce a code-executing chain into an
application whose own source contains nothing dangerous — and a dependency with
a published CVE is only a risk *here* to the extent the application can reach
it.

**Inadequate auditability** is not a standard OWASP entry but is included
deliberately. When an agent chooses and invokes tools autonomously, the absence
of a durable record of what it did makes an incident impossible to reconstruct.

### 2.2 Bills of materials, advisories, and VEX

A **Software Bill of Materials (SBOM)** is a machine-readable inventory of a
project's components, in a standard format such as CycloneDX or SPDX. An
**AI Bill of Materials (AIBOM)** extends the idea to models, datasets, tools,
and agents. An SBOM states presence; an **advisory database** states risk — 
which exact versions are known to be bad. **VEX** (Vulnerability Exploitability
eXchange, here the OpenVEX format) is the third layer: a machine-readable
statement by a named author about whether a product is *actually* affected by a
known vulnerability, and on what evidence.

The value this project claims is the join across all three: knowing that an
application constructs a code-executing chain matters more when the package
providing it can be named, versioned, matched against the advisories published
for it — and shown to be reached from an LLM surface.

---

## 3. Related work

**The structured review remains outstanding** and is listed as such rather than
summarised, because a literature review that has not been done should not be
presented as though it has. The tools most relevant to it are now also
*dependencies or measured comparisons* of this project, which sharpens what the
review must position against:

- **Syft** generates the SBOM and **Trivy** supplies the advisory matching —
  both run offline as external generators, because component inventory and
  version-range semantics are specifications this project deliberately does not
  reimplement.
- **Trivy run directly** is also the measured contrast (§6.4): it answers
  "which of my packages have known CVEs" better than this project ever will,
  and cannot answer whether any of them is reachable from a model.
- **Garak and PyRIT** probe deployed systems and report behaviour; this work
  analyses source and reports locations. The contribution claimed is the join,
  not either capability in isolation.

---

## 4. Design

### 4.1 Phases and artifacts

Five phases, each producing JSON that later phases consume. Treating those
files as contracts is what allows the phases to be developed, tested, and now
extended separately: `findings.json` is on schema version 4, and every reader
that the version-3-to-4 change touched was found and updated through the schema
gate before the writer existed.

| Phase | Produces | Status |
|---|---|---|
| 1. LLM surface extraction | `surfaces.json` | **Complete** |
| 2. SBOM/AIBOM, mapping, advisories | `sbom.json`, `aibom.json`, `mapping.json`; advisory evidence via Trivy | **Complete** |
| 3. Agentic auditor and probes | `findings.json`, `report.md`, `remediation.json`/`.md` | **Complete** (the model writes advice only, never a scored field) |
| 4. Evaluation | `evaluation.json` — counts, never rates | **Complete**; this document is its write-up |
| 5. Acquire and publish | fetch by URL; `report.html`/`.pdf`; `findings.sarif.json`; `findings.openvex.json` | **Complete**, minus the VEX *filter*, which is out of scope (§7) |

The pipeline, as commands:

```
python src/fetch_repo.py https://github.com/...     # acquire (the one online step)
python src/main.py fetched/<name>                   # audit: 11 artifacts, offline
python src/emit_vex.py artifacts/agentic_auditor/<name>       # author VEX
python src/export_reports.py artifacts/agentic_auditor/<name> # HTML + PDF
```

### 4.2 What counts as an LLM surface

Phase 1 defines four kinds, chosen so that together they cover the boundary
between application and model:

| Kind | What it is | Example |
|---|---|---|
| `PROMPT_TEMPLATE` | text the application sends as instruction | a system prompt assigned to a variable |
| `AGENT_DEF` | an agent, chain, or model client being constructed | `AgentExecutor.from_agent_and_tools(...)` |
| `TOOL_CALL` | a capability exposed to the model | `Tool(name='GetUserTransactions', ...)` |
| `DATA_SOURCE` | a point where outside data enters | a chat input, a file read, a database query |

Phase 1 records **where** untrusted data enters. It deliberately does not trace
whether that data reaches a prompt or a tool: following the flow is taint
analysis, which is a Phase 3 probe. Keeping the boundary sharp means Phase 1
remains fully deterministic.

### 4.3 The surface record

Each surface is one record in `artifacts/<system>/<app>/surfaces.json`:

| Field | Meaning |
|---|---|
| `id` | `file:line:kind:name` — a stable handle for later phases to reference |
| `kind` | one of the four above |
| `name` | the symbol, tool, or agent name taken from the syntax tree |
| `file` | repository-relative POSIX path |
| `line` | the line the construct starts on |
| `language` | `python`, `javascript`, or `typescript` |
| `module` | the import specifier the construct came from |
| `detail` | a short human-readable note |

Two design decisions in that table are worth explaining.

The `id` is derived from the surface's own content, never from its position in
a list. An index-based identifier would renumber every surface the moment a
detector was added, silently invalidating any Phase 2 mapping that referenced
it.

The `module` field stores the import specifier **exactly as the source wrote
it** — `langchain_experimental.sql` in Python, `@langchain/langgraph/prebuilt`
in TypeScript. It is the key by which Phase 2 joins a surface to an SBOM
component. It is not normalised to a package name in Phase 1, because the
submodule is itself a risk signal: `langchain_experimental.sql` is the
dangerous import, `langchain` is not.

### 4.4 From presence to risk to reachability

The mapping joins each surface to the component behind it, or records one of
five reasons why not. Advisory ingestion then joins each *reached* component to
the vulnerabilities published against its exact version. The design decision
that everything downstream rests on: **an advisory finding is anchored on the
surface that reaches the component**, so it carries a real file and line — it
can be scored by the same rule as every other finding, and it is bounded by
reachability rather than by a volume cutoff invented after seeing the numbers.
Components that carry advisories but are reached by no surface are reported as
a count, never dropped and never listed as findings: an ordinary dependency
scanner already lists them all, and this tool's claim is the reach.

Matching keys on exact versions only — lockfile-resolved or `==`-pinned. A
version inferred from a range is never matched, because asserting a
vulnerability against `~=0.3.25` would claim something the installed
application may not have.

### 4.5 Determinism

The same repository must always produce byte-identical output. Records are
sorted, keys are sorted, paths are repository-relative POSIX, and no timestamp
or absolute path is written. Three measured exceptions are documented in the
schema contract: model-authored prose (confined to `remediation.json` and one
nullable findings field); the model-chosen `order` in `planner.json`, and the
probe rationale in `findings.json`, both reachable only through the opt-in
`--semantic-probe`, which no scored run used; and the emitted OpenVEX document,
whose mandatory
`timestamp` is **pinned to the advisory database's own build date** — the value
states when the data was taken, which is the only instant the document has a
fact about. Determinism there required `TZ=UTC` in the child environment, found
by measurement: one OpenVEX field renders in the local UTC offset, so two
machines would otherwise produce different bytes from identical input.

---

## 5. Implementation

### 5.1 Structure

Sixty-two modules under `src/`, grouped by responsibility (`parsing/`,
`detectors/`, `artifacts/`, `deps/`, `checks/`, `evaluation/`, `baselines/`),
each with one job and a one-line statement of it; the documentation carries a
module map asserted complete against the tree. Four modules — and exactly four,
enforced by a set-equality test — may start a subprocess: the SBOM generator
(Syft), the advisory generator (Trivy), the repository fetcher (git), and the
VEX author (vexctl). Each pins its program name as a constant, asserted over
the syntax tree, so untrusted input can never become the program that runs; the
fetcher and the two generators additionally pass explicit scrubbed
environments, asserted **by value**, because a structural "an env was passed"
check is satisfied by `os.environ`.

### 5.2 Two parser backends

Python is read with the standard library's `ast`. JavaScript and TypeScript are
read with tree-sitter, because the standard library has no JavaScript parser.

Using one parser for both was considered and rejected. Python's `ast` resolves
imports properly, which a tree-sitter query cannot do without reimplementing
module semantics — and the Python path was already working and tested.

The cost of two backends is honest and worth recording: two lists of framework
names that can drift apart. They did drift, twice, during development. Both
cases were caught by tests, and both are described in §5.5.

The seam is kept invisible: both backends produce the same `Surface` type, so
nothing downstream knows which parser ran.

### 5.3 The detectors and checks

Each detector walks the syntax tree flatly and matches against a table of
names. Supporting a new framework means adding a name to a set, not writing new
logic. A prompt is recognised either as a framework prompt class, or as text
assigned to a prompt-shaped variable — and that second case must accept more
than literals, because corpus prompts are assembled with `.format()` and by
concatenation.

Four checks run under the bounded planner: over-privileged tools (LLM06),
undeclared dependencies (LLM03, hygiene), untrusted input reaching a model
(LLM01, a static taint trace), and — since advisory ingestion — known
advisories in reached components (LLM03, risk). The last is deliberately *not*
a vulnerability scanner: its input is Trivy's matching, its contribution is the
reachability join, and its findings quote the advisory (id, fixed version,
CVSS vector with its source named) rather than judging it. A severity *word*
is refused everywhere: Trivy's `Severity` is its own precedence choice among
disagreeing sources — a judgement — while the CVSS vector is a verifiable
quotation.

### 5.4 Correctness by construction

Several choices exist to make failure loud rather than quiet:

- A repository with no surfaces writes an artifact with `surface_count: 0`
  rather than erroring, so "audited, found nothing" is distinguishable from
  "never audited".
- A malformed file raises an error naming the file. tree-sitter never raises on
  bad syntax — it returns a tree containing error nodes — so the JavaScript
  backend checks for them explicitly.
- Symlinks are skipped: a link inside an audited repository can point anywhere
  on the machine.
- Coverage is paired with claims in both directions: an advisory "snapshot"
  without its generator name, version and database date is refused, and a
  "not ingested" carrying any of them is refused too, so a scan can never be an
  undated claim.
- The one status the VEX emitter may write is a constant; passing anything else
  raises, and a test bans the suppressing status as a *value* anywhere under
  `src/` — with a planted violation proving the ban fires, and a companion test
  proving a docstring explaining the ban does not trip it.
- What must never run is asserted structurally over the syntax tree — process
  launches, mutating git verbs, network imports — because a code path not taken
  looks identical to one that does not exist.

### 5.5 Defects found by the process

Recorded because each was found by a gate or a test rather than by inspection,
and because they illustrate the failure modes this kind of tool is prone to.
The first three are from the extractor's development; the rest from the
supply-chain and publishing work.

**Relative imports were recorded as packages.** `from .settings import x`
recorded `module: "settings"`, indistinguishable from a third-party package —
a wrong SBOM join with no error. Both backends had the defect; fixing Python
made the JavaScript test fail, which is how the second was found.

**A high-privilege tool was invisible.** `ShellTool` was listed as
high-privilege but never entered the detector's match set, so `new ShellTool()`
produced no surface at all — a silent false negative on the most severe
category, in the backend that then had no corpus fixture behind it.

**An over-broad name produced false positives.** `model.invoke(...)` was
reported as a data source; in LangChain.js `.invoke()` is the universal call
for models, chains and retrievers alike.

**A component-anchored finding is a false positive by construction.** The plan
gate caught that a finding with no file and line can never match a grading-key
entry, and that on a complete key every one counts against the tool — already
measured, as it happens, by the SBOM-only baseline's 187. The fix became the
design: anchor on the reaching surface.

**The document identifier was salted.** The OpenVEX document id was first
derived with Python's `hash()`, which is randomised per process; two identical
runs would have produced different ids. Caught before landing; replaced with
sha256.

**The standard tool's id does not mean what it appears to.** `vexctl`'s
document `@id` is a canonicalization hash of the document *as created*;
appending statements leaves it unchanged, so a multi-statement document would
carry an id identifying only its first claim. Measured before shipping; the
emitter sets its own.

**The product slot was wrong.** The first VEX design put the component's purl
in the product field, which makes the statement "this package is affected by
this CVE" — the advisory restated, in the package publisher's voice, with the
audited application absent from its own document. The plan gate caught it; the
product is the app, the component a subcomponent, and the statement became the
one thing this tool can uniquely assert.

**A predicted guard was nearly skipped.** The SARIF module records that it
needs no stale-schema guard because it only ever converts in-memory documents —
"the day anything converts a document off disk, it needs the same guard
`report.py` has." The VEX emitter was that day, and shipped its first draft
without the guard; the code gate found the uncaught `KeyError` and pointed at
the comment that had predicted it.

---

## 6. Evaluation

### 6.1 Method

Detection quality is measured against a hand-written grading key. For each
corpus application, a `ground_truth.json` records the known findings and the
surfaces that must be extracted, each with a file, a line, and an OWASP
identifier. The tool's output is compared to that key and the **counts** are
recorded — true positives, false negatives, and false positives where the key
claims to be complete.

Precision, recall and F1 are deliberately **not** fields in `evaluation.json`.
A reader who wants a rate has to divide, and to divide they must hold the
denominator, which travels beside the count with the `qualifications` that
bound it. F1 is refused outright while no corpus application supports both a
precision and a recall number: an absent field reads as unimplemented, so the
artifact says why instead.

Three details make the comparison trustworthy:

**The key is derived independently of the tool.** Findings come from reading
the application's source and its own documented vulnerabilities. A key derived
from the tool's output would make precision 100% by construction and the
measurement worthless. Keys are AI-drafted and human-verified, and both facts
travel into every score: `key_ai_drafted` is a standing qualification, and a
key edited since its last human check scores loudly as `key_unverified`.

**Line numbers are pinned.** Each corpus application was fixed to an upstream
commit recorded in a manifest, and each record stores a `code_anchor` — the
first 60 characters of the anchored line. A test read the real file and checked
the line still started with that text, so drift was detected rather than
silently grading against the wrong lines. **That test was deleted with the
fixtures on 2026-09-04** (see Appendix A): the anchors are still recorded, but
nothing checks them automatically any more, so a reader re-cloning from the
pins in Appendix A should expect to verify the anchors by hand.

**Matching allows a small window, and only downwards.** A finding matches when
the file and OWASP id are equal and the line falls within
`[line, (line_end or line) + 3]` — and, where the key names them, the surface
kind, surface name and component purl must match too; a finding above the
anchor is a different construct and is never credited. The rule has one definition,
`src/evaluation/grading.py`, because three copies of it had already drifted
apart — this paragraph describes that code and must not become a fourth. Where
a key entry names a component, the finding must cite the same one — the
extension that lets an advisory finding be graded on *reachability* rather than
on a CVE identity that would rot with the advisory database (§6.3, run C).

### 6.2 Corpus

Three applications, each pinned to a commit by a committed manifest, none
committed themselves:

| App | What it is | Key asserts |
|---|---|---|
| `vuln-app-1-support-agent` | *Damn Vulnerable LLM Agent* (Reversec Labs), a deliberately vulnerable LangChain support agent, four Python files | 6 findings; recall only (`findings_complete: false`) |
| `oss-app-react-agent` | LangChain's ReAct agent template, Python | clean; complete |
| `oss-app-langgraphjs-starter` | LangGraph.js studio starter, TypeScript | complete (see run C) |

The TypeScript fixture is what makes the multi-language claim testable end to
end, and — because its lockfile pins 80 of 82 components — it is also where
advisory matching has a real tree to work against.

### 6.3 Results, by run

The detector set and then the grading key changed during the work, so results
are reported as three labelled runs rather than one number. Suite at the time
of writing: 1,910 passing tests.

**Run A — pre-advisory, all keys human-verified (2026-08-28).** Three checks.

| System | Reaches, of 6 graded findings | False positives, two clean apps |
|---|---|---|
| `agentic_auditor` | 2 | 0 |
| `baseline_static_rules` (five regex rules) | 5 | 1 |
| `baseline_sbom_only` | 0 | 187 |

**The grep baseline beats the auditor on recall, 5 to 2**, and that is the
headline because a comparison that only shows wins is not evidence. The two are
near-complementary: their union is all six and they share one. What the auditor
reaches alone is the supply-chain finding, which requires joining a surface to
a component — the capability neither baseline has. The SBOM baseline's 187
false positives are all *true statements* (each component is present and
unreviewed) graded against a key that records vulnerabilities: a category
mismatch that measures the missing advisory layer, not the tool.

**Run B — advisory ingestion landed, keys unchanged.** The fourth check turns
the TypeScript fixture's lockfile against Trivy's database (pinned build
2026-09-01): of 26 advisories in its dependency tree, exactly 2 sit in a
component an LLM surface reaches — `@langchain/community@0.3.3`, reached by
the `TavilySearchResults` tool call at `src/agent.ts:9`. Recall is unchanged
(2 of 6: the Python fixture's requirements are unpinned, so the matcher
correctly refuses them) and the clean-app false positives move 0 → 2 — both
**true findings the key predates**. Reported rather than hidden, because the
delta is the measurement: it is the same category mismatch as the 187, at
1/90th the scale, and it is what a grading key rots into when the world learns
things the key does not.

**Run C — the key gains the reachability entry (drafted, not yet re-verified).**
Grading an advisory finding by its CVE id would pin the key to one database
build; grading the *reachability claim* — this surface reaches this vulnerable
component — is stable across database updates. The key therefore gains one
component-named entry, and the join honours the key's existing `component`
field. Against it: the auditor reaches **3 of 7** graded
findings (the starter's entry answered by both advisory findings — 1 entry, 2
answering findings, 0 false positives) against the grep baseline's **5 of 7**
with its 1 false positive and SBOM-only's **0 of 7** with its 187; the
auditor's produced findings on the complete-keyed apps are 2 of 2 answered.
F1 flips to *reportable* for the first time — an app now supports both sides —
and stays unstored: the artifact carries the counts and the flag, and the
division stays the reader's. These figures are **not yet thesis-grade**:
editing a key resets its verification, the scorer marks every affected score
`key_unverified`, and the numbers stand only after the second-person check the
project requires.

### 6.4 The scope comparison: what this tool is not

Run directly over a deliberately vulnerable dependency testbed
(`security-agent-testbed`, 528 components, no LLM code), Trivy reports **311
vulnerabilities**. This auditor reports **0 findings — and one number: 79
advisory-carrying components reached by no LLM surface**, with the pinned
database named beside it. Both are correct. Trivy answers "which of my packages
have known CVEs"; this project answers "which of them can my model reach", and
on an application with no LLM surfaces the honest answer is a count, not a
findings list. The same distinction bounds what the emitted VEX may say: the
mapping records one entry per LLM *surface*, so "reached by no surface" is not
"unreachable" — measured, `@langchain/core/messages` is imported by the
TypeScript fixture's own source while no surface reaches it. The emitter may
therefore state `affected` with evidence for a reached component and
`under_investigation` for an unreached one, and is structurally unable to state
`not_affected`, which from surface reachability alone would suppress a real
vulnerability in running code.

---

## 7. Limitations and threats to validity

Stated in the order they would affect a reader's confidence.

**The edited grading key is unverified at the time of writing.** Run C's key
entry was drafted by the tool's authors' AI assistant and awaits the
second-person check; until the `verified` flag is restored by a human, run C's
figures are provisional and every affected score says so in its own
qualifications. Runs A and B stand on the previously verified keys.

**Two named risk classes had no check when these runs were measured.** LLM02
and AUDITABILITY were in scope and unexamined; every report states it. A
findings count over three classes must not be read as coverage of five. LLM02
has had a check since 2026-09-05, and the corpus was removed before it shipped,
so these runs cannot be re-taken to show its effect — the figures stand as
measured and the gap is stated rather than closed on paper.

**A three-application corpus is a weak evidence base**, and both compared
systems were authored with the corpus visible. The `small_sample` qualification
travels with every score. Fetching by URL now makes corpus growth cheap; the
grading keys it requires are human work and are the real cost.

**Advisory results depend on a database build.** The match is pinned
(generator, version, database date travel in the artifact) and reproducible
while the cache is retained — but old builds are not re-downloadable, and a
newer database yields different findings. The grading key is insulated by
naming components rather than CVEs; the findings themselves are honest only
alongside their pin.

**Detection is pattern-based.** The detectors recognise the framework names
they are told about; measured, the corpus exercised 16 of 128 carried
names. A framework absent from the tables is invisible.

**The VEX filter is out of scope, and the reasons are measured.** Consuming
someone else's VEX would need an upstream document to exist — none does, for
any dependency of any fixture — and the standard filter joins on the
vulnerability id alone, ignoring the product: in testing, a statement about an
unrelated package suppressed a finding about PyYAML. Emission ships; filtering
is recorded as out of scope rather than as an open task that can never close.

**Reproducibility depends on upstream.** Corpus applications are downloaded,
not committed. Commits are pinned and drift is detected, but a deleted upstream
repository cannot be restored.

---

## 8. Ethics and safety

The auditor is defensive tooling and is constrained accordingly.

Auditing runs **offline**: the audited code never leaves the machine, and the
only socket the auditor's own process opens is to a local model server —
asserted structurally, by module. Acquisition is a separate command, restricted
to `https://`, with a scrubbed git environment, a size cap, and a pinned
commit. The tool **never modifies** the code it audits and only ever *parses*
it — nothing is imported, installed, or executed, so analysing an untrusted
repository does not run its code. Four subprocesses may be launched in total,
each a named tool with a constant program name; untrusted input can never
become the program that runs.

The corpus applications are published, deliberately vulnerable teaching
examples, used as their authors intended. No live or third-party system is
tested. The local model writes remediation *advice* only, under a contract that
rejects file-specific patches, and never a scored field. The emitted VEX
statements assert only what the evidence supports -- `affected` with the
reaching surface named for a reached component, `under_investigation` (present,
exploitability not assessed) for an unreached one -- never `not_affected`, so
they are structurally unable to suppress a finding.

---

## 9. Project status and plan

**Complete.** All five phases; a 1,910-test suite; the evaluation harness, two
baselines, and three labelled runs; SARIF and OpenVEX interchange outputs;
HTML/PDF export. The offline constraint, the no-mutation constraint, the
process-launch allow-list and the VEX status bound are each asserted by tests
rather than stated.

**Remaining, in dependency order:**

1. **Human re-verification of the edited grading key** — the one step that
   makes run C thesis-grade, and it must not be done by the tooling that
   drafted the entry.
2. **Corpus growth**, now that fetching is cheap: each new application costs a
   manifest and a hand-written key, and is what turns the comparison from a
   demonstration into a measurement.
3. **The structured related-work review** (§3), still outstanding and still
   listed as such.
4. **RQ3**, which becomes measurable only if a model-dependent stage ever feeds
   a scored artifact; today none does, by design.

**Out of scope, deliberately:** consuming VEX (§7). **Reversed during the
work, deliberately, and recorded where they happened:** the URL fetcher was
rewritten rather than restored (the tag the plan pointed at did not exist); the
advisory matcher was not hand-written but delegated to Trivy, on the same
argument that chose Syft and vexctl — a standard tool belongs between this
project's claim and the reader.

---

## A grading key for `damn-vulnerable-llm-agent`

The pinned corpus was removed on 2026-09-04, which left every check added since
unmeasured. A grading key needs no corpus: it is a file this project owns,
describing an application it does not.
`grading_keys/damn-vulnerable-llm-agent.ground_truth.json` pins upstream commit
`c0cf9a14`, and the application is cloned by URL like any other.

**This is not the first key for this code, and the earlier one was better.**
Appendix A records `vuln-app-1-support-agent` pinned to the same repository at
the same commit — `VULN1-01` to `VULN1-06`, **human-verified**, and the basis of
the published 5-of-6 against 2-of-6. That key went with the corpus. This one is
a re-derivation of the same six defects from the same source, and it is
**AI-drafted and unverified**: `source: "ai_drafted"`, `verified: false`, so the
scorer attaches `key_ai_drafted` and `key_unverified` to every figure below. A
human reading the six entries against `c0cf9a14` is what removes them. The
schema says it plainly: "A scorer run against `false` is not thesis-grade and
must say so loudly."

**A first draft of this key dropped two entries and both omissions flattered
nobody — they were caught in review.** It had five entries, missing the
untrusted-input source (`main.py:60`) and the supply-chain finding
(`utils.py:75`) — which are precisely the two the auditor reaches and the grep
baseline does not. A key selected that way would have made the comparison below
meaningless. Both are reinstated.

| Key entry | Risk | Location | What it asserts |
|---|---|---|---|
| DVLA-01 | LLM01 | `main.py:21` | The system prompt is the only control on which user's data is read — an instruction, not an enforced check |
| DVLA-06 | LLM01 | `main.py:60` | `st.chat_input` is the attacker-controlled entry point, passed to the executor unvalidated |
| DVLA-05 | AUDITABILITY | `main.py:71` | The trace is captured (`return_intermediate_steps=True`) and discarded into per-session UI state |
| DVLA-02 | LLM06 | `tools.py:40` | `GetUserTransactions` takes a free-text `userId` with nothing tying it to the caller |
| DVLA-03 | LLM02 | `transaction_db.py:62` | Transaction query built by f-string interpolation |
| DVLA-07 | LLM03 | `utils.py:75` | PyYAML is used but never declared, so no bill of materials can see it |

### Result, with both baselines on the same key

| System | Matched | Missed |
|---|---|---|
| Agentic auditor, static only | **4 of 6** | DVLA-01, DVLA-02 |
| Agentic auditor, `--semantic-probe` | **5 of 6** | DVLA-02 |
| Baseline A, grep/AST static rules | **5 of 6** | DVLA-07 |
| Baseline B, SBOM-only | **0 of 6** | all |

**The sets matter more than the counts, and they are near-complementary again.**

```
auditor  {DVLA-01, 03, 05, 06, 07}
baseline {DVLA-01, 02, 03, 05, 06}
shared    DVLA-01, 03, 05, 06        union: all six
```

**The auditor reaches DVLA-07 alone** — the supply-chain entry — because
reaching it means joining an LLM surface to a component in a bill of materials,
which no grep rule has. That is the same finding the original corpus produced
about `VULN1-06`, reproduced on an independently drafted key.

**The grep baseline reaches DVLA-02 alone**, and that is a real detector gap
rather than an artefact: `permissions.py` is silent because
`GetUserTransactions` grants no shell, interpreter or network reach. What makes
it a finding is a *missing authorisation check* — an absent comparison rather
than a present capability — which needs dataflow the auditor does not do. A
regex for a tool taking a bare identifier catches it; the auditor's stronger
machinery does not.

**What changed since the published headline.** The auditor scored 2 of 6 on the
verified key and scores 4 of 6 static here, 5 of 6 with the probe. That is not a
like-for-like improvement claim: different key, drafted by a different author,
unverified, and three of the checks that now match did not exist when the 2-of-6
was taken. What it does show is that LLM02, AUDITABILITY and the semantic probe
each reach an entry, which is the first evidence any of them work at all.

**The probe's contribution is one entry, and it is legible.** DVLA-01 is where
the taint trace runs and stays silent: `argument_names` collects `ast.Name` only,
so an f-string system prompt yields nothing to follow. The probe reads the
template text and reports it.

**Limits, plainly.** One application, six entries, an unverified key drafted by
the same system that built the tool, and `findings_complete: false` — so
precision is not measurable and none of these are false-positive rates. Every
row carries `key_ai_drafted`, `key_unverified`, `findings_not_complete`,
`small_sample` and `unresolved_components`; the probe row drops `model_disabled`
because a model ran, which is a provenance difference and not a detection one.

## Audit Execution Latency

The proposal committed to measuring "audit execution time". `src/main.py` times
every run with `time.monotonic()` and prints the duration; the figures below
were taken on `damn-vulnerable-llm-agent` at commit
`c0cf9a14adad76e9d6a53c41741f625334bd9971`, three runs per configuration on one
WSL2 machine with `qwen2.5-coder:7b-instruct` served locally by Ollama.

| Configuration | Run 1 | Run 2 | Run 3 | Typical | Findings |
|---|---|---|---|---|---|
| **Static only** — model server unreachable | 0.95 s | 0.93 s | 0.94 s | **0.94 s** | 6 |
| **Default** — model writes remediation advice | 17.41 s | 12.45 s | 12.35 s | **12.4 s** | 6 |
| **`--semantic-probe`** — model also plans and probes | 15.50 s | 15.12 s | 15.04 s | **15.1 s** | 7 |

Run 1 of the default configuration (17.41 s) is a cold-start outlier: the model
had not been resident since boot. The two warm runs are within 0.1 s of each
other, and every other row is stable to within 0.5 s.

### Latency is local model inference, in every configuration

**The audit's own work takes under a second.** The first row is a complete
audit — surface extraction, Syft SBOM generation, Trivy advisory scanning, and
all six static checks — with only the model server made unreachable. It produces
the same six findings as the default run and still records
`advisory_data: snapshot`, so nothing static was skipped. At 0.94 s, static
analysis and both external scanners together account for roughly **6% of a
default run**.

Everything above that line is local LLM inference, and **this is true with or
without the semantic probe**. The default configuration is not model-free: it
calls the model once per finding to write remediation advice, which is what
takes it from 0.94 s to 12.4 s. Enabling `--semantic-probe` adds a planner call
and one call per prompt template, costing a further **2.7 s — about 22%** — on
an application with a single prompt template. That increment scales with the
number of templates, not with repository size.

The practical reading for a reviewer: the auditor's static analysis is fast
enough to be irrelevant to the wait, and the cost of the offline design is paid
almost entirely in inference on the machine doing the auditing. A larger
repository moves the first row; more findings or more prompt templates move the
second and third.

**What these numbers are not.** They are one application on one machine, and the
hardware is not characterised here, so they support statements about *where the
time goes* rather than about absolute throughput. No cloud configuration was
measured — see the Addendum below — so this section cannot speak to the
latency trade-off between local and hosted inference, which the proposal also
asked about.

## Addendum: Methodology Deviations from Proposal

Two commitments in the research proposal were not delivered as written. Both
were deliberate, and both are recorded here rather than left for a reader to
find by diffing the proposal against the code. `docs/PROPOSAL_COVERAGE.md`
answers every proposal commitment against a file path; this section covers the
two that changed the study's shape.

### Objective 5 — the local versus cloud-hosted comparison was dropped

The proposal committed to determining "if Open weights models can compete with
frontier AI offerings as an alternative", and to comparing "local open-weight
and cloud-hosted frontier LLM configurations under identical LLM-application
security scenarios".

**This comparison was not run.** Two reasons, in order of weight:

1. **No funded API access.** Every frontier configuration named in the proposal
   is a paid, metered service, and no budget was available for the volume of
   calls a controlled comparison over a corpus would require.
2. **The privacy constraint the study exists to examine.** Running the
   comparison means transmitting the audited application's source, prompts,
   tool definitions and vulnerability evidence to an external provider. That is
   precisely the exposure the project was proposed to avoid, and doing it on
   real repositories to measure it would have created the risk the research
   argues against.

**What this project does establish.** The tool completes an end-to-end audit
with a local open-weight model (`qwen2.5-coder:7b-instruct`) and no external
network access at any point: `src/model_client.py` is the only module in `src/`
that opens a connection and it addresses localhost, and
`tests/parsing/test_offline.py` refuses every socket and asserts the audit
*attempts* none — counting attempts, not successes, so a call that failed
quietly would still fail the test. The offline guarantee is therefore an
enforced property, not a design intention.

**Which parts of this report a model actually authored, stated precisely.**
Every finding in §6 was produced by deterministic static checks with **no model
involved**: `model_run.status` is `disabled` throughout those runs, and
`planner.json` did not exist when the numbers were taken. What a local model
authored is the remediation advice, and -- under the opt-in `--semantic-probe`,
which no scored run used -- the probe verdicts and the check order.

**What it does not establish, stated plainly.** Objective 5 asked a
*comparative* question, and a comparison with one arm is not a comparison.
Nothing here shows that an open-weight model matches, approaches, or falls short
of a frontier model at this task. The correct reading of this report is that a
local model was **sufficient to complete the task with zero data exposure** —
not that it was shown competitive. Establishing the latter remains open work,
and any future run has most of the harness it needs: `planner.json` records the
model identifier, and `findings.json`'s `model_run` records the identifier, its
digest and its decode settings, so two configurations could be told apart
reproducibly.

### `probe_injection` is a static semantic analyser, not a sandbox

The proposal specifies "`probe_injection`: conducts controlled, benign direct
and indirect prompt-injection tests **in a sandboxed environment**". What
shipped is `src/checks/semantic_probe.py`, which executes nothing: it reads a
prompt template off the syntax tree and asks a local model to judge, as an
attacker would, whether the template drops an untrusted value into instruction
text with no separation. This was a deliberate methodological choice, not a
shortfall of time, and the reasons are worth stating in full because two of them
are about coherence rather than cost.

**1. A sandbox would contradict the thesis it was meant to serve.** The
motivating application, `damn-vulnerable-llm-agent`, reaches
`gpt-4-1106-preview` through LiteLLM. Executing it means transmitting the
audited application's prompts and its test payloads to an external provider --
the precise data exposure this project was proposed to avoid, performed by the
tool whose argument is that such exposure is avoidable. Pointed at the local
model instead, the app is no longer the app under test: an injection observed
against `qwen2.5-coder:7b-instruct` is a fact about that model, not about the
audited code. The dynamic test either breaks the offline guarantee or measures
the wrong subject.

**2. It would cost the auditor its strongest safety property.** The tool never
executes the code it audits, and this is enforced rather than asserted:
`tests/test_no_mutation.py` hashes the audited tree before and after a run, and
`tests/test_no_write_commands.py` refuses any write-capable subprocess. That
guarantee is what makes it safe to point this auditor at an unknown -- or
actively hostile -- repository fetched from a URL, which is how the tool is used.
A sandbox stage trades that away for every audit, including the ones that would
never have needed it.

**3. The engineering is disproportionate and fragile.** A general sandbox must
synthesise a container definition for an application it has never seen, infer
its entry point (`streamlit run`, `npm start`, `python main.py`), wait on a
server that may never bind, and drive a headless browser to locate a chat input.
Each step fails differently on each application, and none of it measures
anything until all of it works.

**What the static approach demonstrated, stated precisely.** On
`damn-vulnerable-llm-agent`, the probe reported `main.py:21` -- the anchor of
grading-key entry `VULN1-01` -- with the model's own reasoning carried as probe
evidence: *"The template directly includes the `userId` returned by the
`GetCurrentUser()` tool into the instruction text without any delimiter,
quoting, or system/data separation."* That entry had previously been a miss
attributed to a check that ran and stayed silent.

**And what it does not demonstrate.** One application, one prompt template, one
model, with no grading key scored against it. The verdict is model-dependent:
another Ollama build may not reproduce it, which is why `model_run` records the
model's digest and why the probe is off by default. This is a worked example of
a static, offline alternative to dynamic injection testing -- not evidence that
the static approach matches a dynamic one in recall, which would require the
comparison this study did not run. The honest claim is that structural
weaknesses in prompt templates are *detectable* without execution, and that the
detection is cheap: the auditor's entire static pass runs in under a second (see
"Audit Execution Latency"), where a sandbox stage would add container build and
boot time to every audit.

**The classification, for a reader who wants the standard framing.** This is a
SAST result where the proposal anticipated DAST. The two answer different
questions -- a dynamic test can confirm exploitability and a static one cannot;
a static test can examine every template in a repository, including those on
code paths a dynamic run never reaches. The substitution narrows what can be
claimed and widens what can be covered, and this report claims only the
narrower thing.

### RAG/data-layer retrieval risk was substituted with AUDITABILITY

The proposal names four risks: prompt injection, supply-chain vulnerabilities,
excessive agency and unsafe tool permissions, and **RAG/data-layer retrieval
risks**. The delivered tool covers the first three, plus improper output
handling (LLM02) and **inadequate auditability of agent actions** — the last of
which is this project's own category and is not a stock OWASP entry.

**What was kept.** Retrieval is not absent from the analysis. Retrieval points
are extracted as first-class `DATA_SOURCE` surfaces — `as_retriever`,
`similarity_search`, `get_relevant_documents`, document loaders — and
`src/checks/taint.py` treats them as *untrusted sources*, so a value arriving
from a retrieved document and reaching a model is reported under LLM01. Indirect
prompt injection through the retrieval layer is therefore partially covered by
the prompt-injection check.

**What was dropped.** No check reports a retrieval-layer risk as its own class,
and **retrieval poisoning has no dedicated detector**. The substitution was made
because auditability proved both more tractable statically and more useful on
the applications available: proving a corpus of documents has been poisoned
requires the documents, which a static source audit does not have, whereas
whether an agent was constructed with any means of recording its actions is
decidable from the code. `src/checks/auditability.py` reports that, and its
title states the structural fact it establishes rather than the conclusion —
"Agent constructed with no callback or handler argument", not "inadequate
auditability" — because a static check cannot distinguish a display handler from
an audit sink.

**The cost, stated rather than discovered.** The delivered risk subset is not
the proposed one. A reader comparing the two lists will find one class swapped,
and this section is that comparison made in advance.

## References

1. OWASP. *OWASP Top 10 for Large Language Model Applications*, 2025 edition.
   https://owasp.org/www-project-top-10-for-large-language-model-applications/
2. Reversec Labs (formerly WithSecure Labs). *Damn Vulnerable LLM Agent.*
   https://github.com/ReversecLabs/damn-vulnerable-llm-agent
3. WithSecure Labs. *Prompt injection attacks against LLM agents.*
   https://labs.withsecure.com/publications/llm-agent-prompt-injection
4. Pedro, R. et al. *From Prompt Injections to SQL Injection Attacks: How
   Protected is Your LLM-Integrated Web Application?* arXiv:2308.01990.
5. *LLM4Shell: Discovering and Exploiting RCE Vulnerabilities in Real-World
   LLM-Integrated Frameworks and Apps.* Black Hat Asia 2024.
6. OWASP CycloneDX. https://cyclonedx.org/
7. Linux Foundation. *SPDX Specification.* https://spdx.dev/
8. tree-sitter. *An incremental parsing system for programming tools.*
   https://tree-sitter.github.io/tree-sitter/
9. Anchore. *Syft.* https://github.com/anchore/syft
10. Aqua Security. *Trivy.* https://github.com/aquasecurity/trivy
11. OpenVEX. *Specification and vexctl.* https://github.com/openvex
12. OASIS. *Static Analysis Results Interchange Format (SARIF) 2.1.0.*

*References 2–5 are the corpus application's own sources and the publications
it cites. The structured literature review recorded in §3 as outstanding will
extend this list.*

## Appendix A — The graded corpus, and why the numbers in §6 still stand

Every figure in §6 was measured against three pinned third-party
repositories and hand-written grading keys. On **2026-09-04** that corpus was
**removed from the project**, deliberately: the auditor takes any repository by
URL (§5), so a fixed set of fixtures no longer reflects how the tool is used,
and the project ships the auditor rather than copies of other people's code.

**The measurements are kept, with their inputs named, rather than deleted.** A
number whose input has been withdrawn is not repeatable, but deleting it would
be worse — it would leave §6 describing a system nobody had measured. So this
appendix records exactly what each number was taken against, which is what makes
the claim falsifiable by anyone willing to re-clone:

| App (artifact directory name) | Upstream | Commit |
|---|---|---|
| `vuln-app-1-support-agent` | https://github.com/ReversecLabs/damn-vulnerable-llm-agent | `c0cf9a14adad76e9d6a53c41741f625334bd9971` |
| `oss-app-react-agent` | https://github.com/langchain-ai/react-agent | `9bbd82d84905acc37f527b1f372dae841016f3b4` |
| `oss-app-langgraphjs-starter` | https://github.com/langchain-ai/langgraphjs-studio-starter | `cd9a02c64afd97fe008199665ebb0aac803451da` |

The commit matters as much as the URL: every line number in a grading key was
recorded against that exact commit.

**One grading-key entry existed only outside git** and is transcribed here so it
is not lost with the folder. `STARTER-01` was added to
`oss-app-langgraphjs-starter`'s key on 2026-09-03 to grade the reachability
claim the advisory check makes, and was never committed:

- **id** `STARTER-01`, **owasp_id** `LLM03`, **detection** `static`
- **title** — Tool-call surface reaches a component carrying a known advisory
- **file** `src/agent.ts`, **line** 9, **llm_surface** `TOOL_CALL`,
  **surface_name** `TavilySearchResults`
- **code_anchor** — `new TavilySearchResults({ maxResults: 3, }),`
- **component** `pkg:npm/%40langchain/community@0.3.3`
- **notes** — snapshot-dependent by design: it names no CVE, and holds while the
  pinned version carries at least one advisory in whatever database the run
  reads. It grades the (surface, component) reach rather than an advisory
  identity, so it does not rot when the database updates. Several produced
  findings, one per advisory, answer this one entry.
- Its `verified` flag was reset when it was added, so any score touching this
  key was qualified `key_unverified` (blocker B9, closed with the removal).

**What the removal does not change.** The scorer, the one join rule, the two
baselines and `evaluation.json`'s schema all remain in the code and remain
tested — 268 tests, none of which needs a fixture. What is gone is the *shipped*
set of apps to score. A future measurement means placing a grading key under
`grading_keys/` for an app that has been audited, which is the interface §5's
URL workflow implies.
