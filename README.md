# AgenticLLMAppAuditor

An offline, human-in-the-loop security auditor for LLM applications
(LangChain / LangGraph). It analyses a repository and reports findings mapped
to a subset of the OWASP Top 10 for LLM Applications, backed by SBOM/AIBOM
evidence.

It reads **Python** (via the standard library's `ast`) and **JavaScript and
TypeScript** (via tree-sitter). The design is language-agnostic: adding one
starts in `src/parsing/languages.py`.

It **reports only** — it never edits, patches, or merges the audited code, and
it never runs it either: the auditor reads source and artifacts, so auditing an
app cannot execute it. Both guarantees are asserted by tests rather than
promised in prose. It runs offline against a local model.

Master's degree project. Contributors: Hein Thet Naung, Neo Jia Wei,
Tan Bing Hong.

## Status

**All five phases produce their artifacts.** Static analysis only, and the
auditor never runs the app it audits.

- **Phase 1** extracts LLM surfaces — prompt templates, agent definitions, tool
  definitions and data-source sites — and records where each one lives.
- **Phase 2** builds a bill of materials for Python and npm dependencies, an
  inventory of the models, tools, agents, datasets and MCP servers, and a join from each surface to the
  package it came from.
- **Phase 3** runs five checks under a bounded LangGraph planner, writing
  `findings.json` and a `report.md` that gives what was *not* examined the same
  billing as what was found.
- **Phase 4** scores those findings against hand-written grading keys and against
  two baselines, in counts and never rates.
- **Phase 5** takes a repository by URL and exports both reports as HTML and
  PDF. Fetching and exporting are commands of their own, not flags, so the audit
  path still reaches no network and needs no renderer installed. **Emission of
  VEX ships** as its own command; *consuming* VEX is out of scope, for measured
  reasons — see below.

**What is not built is inside those phases, not after them.** The local model
advises on every finding into `remediation.json`, but writes nothing into any
scored artifact: `findings.json` still records `model_run.status: "disabled"`
and is byte-identical whether the model ran or not — **unless the opt-in `--semantic-probe` is passed**, which is the one flag that puts model-authored findings in that file, records `model_run.status: used` beside them so the provenance is not a lie, and is off by default for exactly that reason. Advisory data **is**
ingested — Trivy, run offline against a pinned database — so a supply-chain
finding can now say what is known to be wrong with a component, and which LLM
surface reaches it. The auditor covers all five risk classes it
names, as of 2026-09-05.

### The headline result

**On the graded corpus a five-rule regex baseline reaches more of the grading
key than the auditor does — 5 of 6 against 2 of 6.** That is reported first
because a comparison that only shows wins is not evidence.

That corpus was **removed from the project on 2026-09-04** — the auditor now
takes any repository by URL, so a fixed set of fixtures no longer reflects how
it is used. The figures are kept with their inputs named rather than deleted:
[`docs/REPORT.md`](docs/REPORT.md) Appendix A records the three apps, their
upstream URLs and the exact commits each number was measured against, so the
claim stays falsifiable by anyone willing to re-clone them.

The two are near-complementary rather than competing: their union is all six,
and they share only one. The auditor reaches `VULN1-06` alone — the
supply-chain finding — because reaching it means joining a *surface* to a
*component*, which no baseline has. Where the auditor loses, it loses ground it
never entered: at the time of that measurement LLM02 and AUDITABILITY were
absent from its coverage entirely.

**LLM02 and AUDITABILITY have both since gained a check, and these numbers
have not been re-measured.** AUDITABILITY's is `src/checks/auditability.py`,
which reports `VULN1-05`'s line; it carries a measured false-positive rate,
stated where the check is described in `docs/REPORT.md`.
`src/checks/output_handling.py` reports a query built by string interpolation,
which is the rule the baseline held `VULN1-04` with. The corpus was removed
before it shipped, so the comparison above cannot honestly be re-run — the
5-of-6 against 2-of-6 stands as measured, against code that had no LLM02 check.
What can be said is what the new check does on a repository anyone can fetch:
on `damn-vulnerable-llm-agent` it reports `transaction_db.py:62` — the line
`VULN1-04` names — and `:76`, and stays silent on the four constant-query
`execute` calls in the same file.

**Re-measured after advisory ingestion, and the delta is the result**: recall is
unchanged — 2 of 6, because the Python fixture's unpinned requirements give the
new check nothing to match — while the clean apps went from 0 false positives
to **2**. Both are *true* statements (real CVEs in a component a tool call
reaches, `src/agent.ts:9`) that the hand-written grading key has no entries
for, so they score as false positives by construction — the same category
mismatch as the SBOM baseline's 187, at 1/90th the scale.

**Re-measured again after the key gained its reachability entry** (`STARTER-01`
— one component-named entry, deliberately naming no CVE so it does not rot when
the advisory database updates): recall **3 of 7**, false positives **0**; the
grep baseline **5 of 7** with its 1; SBOM-only **0 of 7** with its 187. Both
advisory findings answer the one entry — the auditor's third graded reach, and
the one neither baseline can touch. **These figures are not yet thesis-grade**:
editing a key resets its verification, and the scorer marks every affected
score `key_unverified` until a human re-checks the entry. The headline above
stays on the last fully verified run for exactly that reason.

Both systems were authored with that corpus visible, so neither figure
generalises. See [`docs/PHASE_4_PLAN.md`](docs/PHASE_4_PLAN.md) for the full
table and its caveats.

What that produces on the three fixtures today:

| Fixture | surfaces | components | surfaces joined to a package |
|---|---|---|---|
| `vuln-app-1-support-agent` (Python) | 19 | 5 | 6 of 19 |
| `oss-app-langgraphjs-starter` (TypeScript) | 5 | 82 | 4 of 5 |
| `oss-app-react-agent` (Python) | 4 | — | — |

Most unjoined surfaces are not defects: a language builtin, the app's own code,
or a call on a local variable whose type static analysis cannot follow.

One kind is a finding. A package used but never declared is a supply-chain
risk — one surface in the Python fixture hits it, importing PyYAML.
`mapping.json` records which of the five reasons each surface got, so "no
package exists" is never confused with "we could not tell", and neither is
confused with a finding.

The last two have no planted vulnerabilities, so a finding in either is wrong by
construction unless its key grades it (the starter's now grades one). Only the TypeScript one currently carries real **false-positive**
evidence: its supply-chain check ran against an 82-component SBOM and its one
tool surface was judged, so a check could have been wrong and was not. The
Python one reports no findings either, but no check there had a subject to be
wrong about — it has no tool surface, its taint trace ran and reached no
conclusion, and it has no bill of materials at all. Its zero is **0 out of 0
opportunities**, which is worth having and is not the same claim.

> **Read a quiet taint result with two remaining blind spots in mind.**
> `agent.invoke(...)` and `agent.run(...)` are now traced (fixed 2026-09-05,
> along with the false positive that fix nearly shipped — see `docs/TODO.md`).
> Still silent, with **no inconclusive probe** to say so: a receiver that is
> not a local name (`agent.runnable.invoke(x)`), and a value passed inside a
> container (`agent.invoke({"input": x})`). For those two shapes a trace that
> could not follow is still indistinguishable from one that followed and found
> nothing. A strict xfail holds each, so neither can be quietly forgotten.

`oss-app-react-agent` declares its dependencies in `pyproject.toml` and pins
them in `uv.lock`, and this tool reads neither, so it produces no bill of
materials and no mapping — the dashes above. That is a real gap, not a bad fixture: it is the only fixture that
exercises what the tool does when it cannot see an app's dependencies at all.

### What it scores against the grading keys

| Fixture | key findings | matched | missed | false positives |
|---|---|---|---|---|
| `vuln-app-1-support-agent` | 6 | 2 | 4 | **not measurable** — its key does not claim to list every finding, so the count is `null` rather than `0` |
| `oss-app-langgraphjs-starter` | 1 *(STARTER-01, key `key_unverified` — never re-verified before the corpus was removed, so this row stays qualified permanently)* | 1 — answered by both advisory findings | 0 | 0 |
| `oss-app-react-agent` | 0 | — | 0 | 0 |

**Counts, never rates.** `evaluation.json` holds no float and no percentage:
precision, recall and F1 are absent as fields, so a number cannot be quoted
without the denominator beside it. F1 is refused outright, with the reason
recorded in the file — no fixture supports both a precision and a recall number,
so there is nothing to combine.

Each miss carries the reason it was missed rather than a bare count. Of the
four: two are checks that ran and stayed silent, and two were risk classes no
check covered **when these numbers were measured** -- both have one now. That breakdown is more useful than the total, and it is why
a short findings list is never reported as a clean bill.

**One caveat on "ran and stayed silent".** `scorer.py`'s own comment warns that
a dropped probe downgrades *a probe gave up* to *a check was silent* — "the
opposite conclusion". The two shapes the taint trace still cannot follow do
exactly that, so a `checked_and_silent` miss on an app written in either shape
should be read as *at most* that strong. **These numbers predate the fix** and
were measured while `.invoke(...)` was blind entirely; re-scoring would need
the corpus that produced them, which is gone (Appendix A).

Three applications is still a demonstration, not a measurement, and the artifact
says so: all three trip the `small_sample` qualification. Two of the three keys
are human-verified; the TypeScript starter's was edited 2026-09-03 (it gained
the reachability entry `STARTER-01`) and scores `key_unverified` — the human
re-check it was waiting on never happened before the corpus was removed, so
that row is qualified for good. All three remain `source: ai_drafted`,
because who drafted a key and who checked it are different facts and the
artifact records both.

Progress and blockers: [`docs/TODO.md`](docs/TODO.md).

## Prerequisites

Only the first row is needed to run the auditor. The rest are for specific
tasks, so you can start without them — and each degrades rather than fails: no
Syft means no bill of materials, no Ollama means no advice. vexctl is the one
that does not degrade: `src/emit_vex.py` needs it and fails without it, but an
audit never calls it, so nothing else is affected. Every one of those is recorded in the artifacts rather than
passed over in silence.

| You need | Version | What for | Check |
|---|---|---|---|
| **Python** | 3.10 or newer | everything — the auditor uses modern type hints | `python3 --version` |
| **git** | any | cloning this repository, and fetching one to audit (`src/fetch_repo.py`). Unlike Syft and Ollama this one does not degrade: without it a fetch fails, though a local path still audits fine | `git --version` |
| **Trivy** | 0.74.0 | the known-vulnerability check (`known_advisory`). Fetch its database once, out-of-band: `trivy fs --download-db-only .` — every audit scan runs offline against that cache. Without Trivy or a cached database an audit still completes, `advisory_data` says `not_ingested`, and the check is absent rather than silent | `trivy --version` |
| **A Unicode TTF** | any | the PDF half of `src/export_reports.py`. DejaVu is looked for on the machine rather than committed — without one the HTML is still written and the PDF is skipped | `fc-list \| grep -i dejavu` |
| **Syft** | 1.51.0 | building an SBOM (`src/main.py`) from a `requirements.txt` or a `package.json`. Not needed to extract surfaces | `syft version` |
| **Ollama** | any | the remediation advice in `remediation.md`, and the embeddings that ground it. Without it an audit still completes and every finding records that no model answered | `ollama --version` |
| **A knowledge base** | — | grounding that advice in the OWASP Cheat Sheet Series (see below). Built out-of-band with `src/index_knowledge.py`; without it an audit still completes, `remediation.json` records `knowledge_base.status: not_indexed` with the reason, and the advice is written ungrounded | `ls knowledge/manifest.json` |
| **vexctl** | 0.4.4 | authoring this project's own VEX statements (`src/emit_vex.py`). Unlike Syft and Ollama it does **not** degrade — without it that command fails — but an audit never runs it, so an audit is unaffected | `vexctl version` |

On Debian or Ubuntu, Python's venv support is a separate package:

```sh
sudo apt install python3-venv
```

Everything else is installed by `pip` into the virtual environment below.
None of it is needed to read Python, which the standard library's `ast` handles:

| Package | What for |
|---|---|
| `tree-sitter` + `tree-sitter-javascript` + `tree-sitter-typescript` | parsing JavaScript and TypeScript. Python is read with the standard library's `ast`, so these are only used for JS/TS |
| `langgraph` | the audit workflow. The thesis argues an agentic LLM app should be audited by one, so the auditor is built the way the apps it audits are built |
| `fpdf2` | the PDF export. Pure Python, so it needs no system libraries — but it does need a Unicode font on the machine, see the table above |
| `pytest` | running the tests |

**Auditing a local path opens no socket. A link fetches first, then audits
offline.** `python src/main.py <path>` is the pure audit, and
`tests/parsing/test_offline.py` runs one with every socket refused, while
`test_offline_containment.py` closes the gap a run cannot — which modules may
open a connection at all, and which third-party defaults would reach out from a
process a blocked socket cannot watch;
`python src/main.py <https-link>` runs the fetch stage first (https only, a
scrubbed git environment, the network living in git's child process) and every
stage after it is the same offline audit. `src/fetch_repo.py` remains the
stage's own command for anyone who wants acquisition and auditing separated.

Everything else runs on your own machine. Ollama, Syft and vexctl are all
local; Syft is told explicitly not to check for its own updates, which is the
one thing it would otherwise do over the network. VEX documents are fetched
out-of-band as a manual step and read from disk, never at runtime — the same
policy the advisory snapshot follows. Within the auditor's own process the only
socket opened at all is the one to Ollama, and a test asserts that by module.

Install Syft to `~/.local/bin` without root:

```sh
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
  | sh -s -- -b ~/.local/bin
```

Install vexctl the same way — it ships a static binary, so there is nothing to
build:

```sh
curl -sL -o ~/.local/bin/vexctl \
  https://github.com/openvex/vexctl/releases/download/v0.4.4/vexctl-linux-amd64
chmod +x ~/.local/bin/vexctl
```

### Optional: the local model

Needed for the remediation advice. Everything else — extraction, the bill of
materials, the findings and the score — runs without it, and an audit with no
model reachable says so rather than substituting anything. Install Ollama, then:

```sh
ollama pull qwen2.5-coder:7b-instruct
python src/model_client.py          # prints a reply from the local server
```

Without it the extractor works normally, the model test skips, and
`remediation.md` records that no advice was written.

### Optional: the knowledge base behind the advice

The advice is grounded in passages retrieved from a pinned local copy of the
OWASP Cheat Sheet Series, indexed in ChromaDB with a local embedding model.
Three commands, run once, after `pip install -r requirements.txt`:

```sh
git clone --depth 1 https://github.com/OWASP/CheatSheetSeries knowledge/owasp-cheatsheets
ollama pull nomic-embed-text
python src/index_knowledge.py       # ~3,500 passages, about a minute
```

Only `knowledge/manifest.json` is committed — the clone and the index are
fetched and built out-of-band and gitignored, the same policy as any audited
tree and the advisory database. The manifest pins the commit, a digest of the
indexed bytes, the embedding model and the ChromaDB version, so the index can
be rebuilt from the same inputs and checked against it. Before retrieving
anything an audit compares three of those — the manifest text against the
digest the index recorded of it, the installed ChromaDB version, and the
configured embedding model — and writes the advice ungrounded if any has moved.
It does **not** re-read the clone: an edited clone is invisible to an audit,
because the manifest and the index still agree about each other. Catching that
is what `content_digest` is for, and re-checking it is what a rebuild does. See [`knowledge/README.md`](knowledge/README.md) and
[`docs/RAG_PLAN.md`](docs/RAG_PLAN.md).

## Setup

Use one virtual environment named `.venv` at the repo root:

```sh
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

If `python -m venv` reports that `ensurepip` is unavailable, install the
matching venv package first (on Debian/Ubuntu: `sudo apt install python3-venv`).

### Settings (optional)

Everything runs on sensible defaults with no configuration. To point the
auditor at a different model or a non-standard Ollama address, copy the
template and edit it:

```sh
cp .env.example .env
```

`.env` is gitignored — it holds your machine's settings, not the project's.
A real environment variable always wins over a value in `.env`, which in turn
wins over the built-in default:

```sh
AUDITOR_MODEL=llama3.1:8b python src/main.py ~/code/some-llm-app
```

## Usage

### Auditing any repository in one command

Hand `main.py` an `https://` link and it runs the whole pipeline: fetch (pinned
to the commit it resolved), surface extraction, SBOM and AIBOM via Syft, known
advisories via Trivy, the five checks, LLM remediation advice via Ollama, an
OpenVEX document via vexctl, and the HTML and PDF reports — each stage
degrading with a printed reason when its tool or data is absent, never
silently:

```sh
python src/main.py https://github.com/Kilo-Org/security-agent-testbed
python src/main.py https://github.com/edgecases-PurpleHax/cve-images
```

Everything lands in `artifacts/agentic_auditor/<name>/`; the fetched tree and
its pin live under `fetched/`. A second run of the same link reuses the pinned
tree and says so; a *different* repository that happens to share the name is
refused rather than silently audited. A **local path** argument still runs the
pure offline audit and nothing else — that is the path the no-network tests
hold.

### Scoring an audit against a grading key

The auditor reports; **scoring is what says whether the report was right**, and
that needs a hand-written answer key. One ships -- `damn-vulnerable-llm-agent`, AI-drafted and unverified — the pinned
corpus it once carried was removed on 2026-09-04, because the tool now takes
any repository by URL and a fixed set of fixtures no longer reflects how it is
used. `docs/REPORT.md` Appendix A records the three apps and commits the
published figures were measured against.

To score an app yourself, audit it, then write a key beside its artifact name:

```sh
python src/main.py https://github.com/some/llm-app     # writes artifacts/agentic_auditor/llm-app/
$EDITOR grading_keys/llm-app.ground_truth.json          # what is really in it, by hand
$EDITOR grading_keys/llm-app.manifest.json              # the upstream URL and exact commit
python src/evaluate.py --system agentic_auditor         # counts, never rates
```

`<app>` is the only join key: the directory name `main.py` wrote artifacts
under is the name the key must take. A key with no manifest is refused — its
line numbers mean nothing without the commit they were read at. See
`docs/SCHEMAS.md` for both shapes.

**The suite needs none of this.** With no keys, no Syft, no Trivy, no vexctl
and no Ollama, `pytest` is green: those tests skip or build what they need in a
temporary directory, so a fresh checkout needs only Python. **The skip count is
a fact about your machine, not about the suite** — with every optional tool
installed nothing skips, and with none of them roughly a dozen do. Neither
number means anything on its own.

### Running the auditor

Audit a repository already on disk:

```sh
python src/main.py ~/code/some-llm-app
```

To audit one you do not have yet, hand `main.py` the link — the one-command
pipeline above — or run the stages yourself; every stage stays a command of its
own:

```sh
python src/fetch_repo.py https://github.com/langchain-ai/react-agent
python src/main.py fetched/react-agent
```

The fetch takes `https://` URLs only, clones shallowly with a scrubbed git
environment, removes the history, and writes `fetched/<name>.manifest.json`
recording the exact commit — without which an audit of "whatever was on main
that day" could never be repeated. It refuses to write over anything it did not
create.

Once an audit has run, export its two reports for someone who does not read
Markdown in a terminal:

```sh
python src/export_reports.py artifacts/agentic_auditor/some-llm-app
```

That writes `report.html`, `report.pdf`, `remediation.html` and
`remediation.pdf` beside the Markdown they come from. The PDF needs a Unicode
font on the machine; without one the HTML is still written and the run says why
the PDF was skipped.

It writes everything it can into `artifacts/agentic_auditor/<app>/` and makes no
network call. The `agentic_auditor` segment names which system produced the
files, so a Phase 4 baseline's output cannot overwrite the auditor's:

| Artifact | Needs |
|---|---|
| `surfaces.json` | nothing but the source. Also records any file it could not read, so a later phase never mistakes a partial scan for a complete one |
| `aibom.json` | the same — it is derived from the surfaces |
| `sbom.json` | Syft, plus a `requirements.txt` (Python) or a `package.json` (npm) |
| `sbom.cyclonedx.json` | the same scan, re-emitted in the standard format |
| `mapping.json` | the SBOM, to join each surface to the package it came from |
| `findings.json` | the surfaces, and the mapping for the supply-chain check. Records which risk classes were examined, so silence is never read as a clean result |
| `report.md` | the two files above, rendered for a person. Not a contract: nothing consumes it |
| `findings.sarif.json` | the findings, re-emitted in SARIF for other tooling. Carries `coverage` in its property bag, so it is not read as a caveat-free list; `skipped_files` and the probe records stay in the other two artifacts |
| `remediation.json` | the findings, plus the local model. One entry per finding saying how to fix it — or recording that the answer was refused, or that no model answered |
| `planner.json` | which order the checks ran in, and what chose it — a local model with `--semantic-probe`, nothing otherwise. **Read by nothing**: the order is a fact about one execution, and because `checks_run`, findings and probes are all sorted it changes no other byte of any artifact unless the step cap binds |
| `remediation.md` | the findings and the advice, rendered for a person. Not a contract either |

Producing less is a normal outcome, not a failure. Without Syft, or with no
manifest it knows how to read, it writes what it can and says on stderr why the
rest were skipped. A repository declaring **both** a Python and an npm
manifest is refused a bill rather than given half of one.

### Scoring what was found

Once an app has been audited and given a grading key (see above), score what
was found against it:

```sh
python src/evaluate.py --system agentic_auditor
```

It writes `artifacts/<system>/evaluation.json` — one file per system per run,
not one per app, because a comparison across apps is not a per-app fact. The
system defaults to `agentic_auditor`; `--system` takes one of the three names
in `SCORED_SYSTEMS`, and that name is also the directory the artifacts are read
from, so three systems can be scored without overwriting each other.

It prints counts and what bounds them, and **never a rate**. Two of the three
per-app blocks from a real run (the third, `oss-app-react-agent`, scores 0 of
0), with the pools beneath — note the TypeScript fixture saying `key_unverified`
out loud, because its key was edited and awaits the human re-check:

```
scored 3 apps as agentic_auditor, wrote artifacts/agentic_auditor/evaluation.json
  oss-app-langgraphjs-starter: 1 of 1 matched, 0 missed, false positives 0
    bounded by: key_ai_drafted, key_unverified, model_disabled, small_sample
  vuln-app-1-support-agent: 2 of 6 matched, 4 missed, false positives not measurable
    bounded by: expected_surfaces_not_complete, findings_not_complete, key_ai_drafted, model_disabled, small_sample, unresolved_components
  recall pool: 3 of 7 over oss-app-langgraphjs-starter, vuln-app-1-support-agent
  precision pool: 2 of 2 produced over oss-app-langgraphjs-starter, oss-app-react-agent
  f1: reportable
```

That transcript predates 2026-09-05. The command now prints three more lines
beneath the pools — how many findings carry a code, SBOM/AIBOM or VEX evidence
link, each with its denominator and the apps it rests on:

```
  code evidence: 2 of 3 findings over oss-app-langgraphjs-starter, vuln-app-1-support-agent
  SBOM/AIBOM evidence: 2 of 3 findings over oss-app-langgraphjs-starter, vuln-app-1-support-agent
  VEX evidence: 1 of 3 findings over oss-app-langgraphjs-starter, vuln-app-1-support-agent
```

Counts there too, for the same reason. The proposal asks for the *percentage*
of findings carrying each link; it is one division, and the divisor is on the
line.

Precision, recall and F1 are absent from the artifact as fields. A reader who
wants a rate divides for themselves, which means holding the denominator and
the qualifications printed beside it. "False positives not measurable" is not
a bug: that fixture's key does not claim to list every finding, so the count is
undefined and recorded as `null` rather than `0`.

### The remediation report

Beside `report.md`, which says what was found, `remediation.md` says what to do
about it. **The local model writes it** — prose and one illustrative snippet per
finding, from the evidence the tool already gathered.

This reversed a decision recorded in `docs/SCHEMAS.md`, which had forbidden the
model to write a suggested fix at all, on the grounds that a patch is one
copy-paste from applying a change to code nobody reviewed. That concern was not
dropped; it was given a mechanism, and the old text is struck through rather
than deleted so the reversal stays legible.

**The guard runs on the model's answer, never on the prompt.** That is not a
stylistic choice — prompt wording was measured to leak. Told in general terms
not to reference the audited app's identifiers, the model returned a snippet
containing that app's own `st.chat_input`; told the exact forbidden tokens, it
did not. A property that turns on phrasing is not a safety property.

So an answer is refused **whole** — never edited — if it names an identifier
from the finding's own evidence or the app's modules, arrives as a diff, runs
past the length caps, smuggles a code fence through the prose, or re-classifies
the finding. Refusals are recorded, so the report can say *the model answered
and the answer was refused* rather than quietly showing nothing.

**The advice is grounded, and every passage it used is named.** The prompt
carries a fixed reference entry for the finding's risk class and up to three
passages retrieved from the knowledge base above, and each entry in
`remediation.json` records which passages grounded it — source, path, section
heading and the URL of the upstream page — so the report can print a
*Grounded on* list a reader can open. The report states the sources' licence
once, because the passages are quoted verbatim.

This is confined to the advice. Nothing about retrieval touches `findings.json`,
`owasp_id`, `model_run` or the scorer, and it is **not** a reversal of the
Phase 0 decision to drop LLM08: that dropped retrieval as a *risk class the
auditor detects*, because none of the graded apps retrieved. This adds retrieval as a
*mechanism the auditor uses on its own advice*.

With no index built, or a stale one, or the embedding model unreachable, the
run records which of those it was in `knowledge_base.reason` and writes the
advice exactly as it did before Phase 6. An unreachable chat model and an
unbuilt index are two different absences and are recorded in two blocks.

**No advice reaches a score.** It lands in `remediation.json`, which the Phase 4
scorer cannot open — it reads three files and that is not one of them. So
`findings.json` is byte-identical whether the model ran or not, and every number
in the evaluation still rests on static analysis alone.

**Every report names the model that wrote it**, with its build digest and the
decode settings:

> **Advice written by `qwen2.5-coder:7b-instruct`**, build `dae161e27b0e`, run at
> seed 0, temperature 0. Every word below the findings is that model's; a
> different model would write different advice.

The digest matters because a tag does not pin anything — `gemma4:latest` names a
different build after the next pull, so a report recorded by tag alone could not
be traced back.

If the model cannot be reached the audit still completes: every entry records
`unavailable`, and the report opens by saying so. Nothing is substituted.

### The VEX layer

A VEX statement says whether a product is *actually* affected by a known
vulnerability, and why not when it is not. `vexctl filter` applies those
statements to a results set and drops what they rule out, so the layer sits
between the findings and the report: a finding a maintainer has already declared
`not_affected` should not reach a reader as though nobody had looked.

**This project emits VEX and consumes none, and the asymmetry is deliberate.**
Emitting needs only its own evidence; consuming needs an upstream publisher to
exist, and none does for any dependency of any fixture.

```sh
python src/emit_vex.py artifacts/agentic_auditor/some-llm-app
```

That writes `findings.openvex.json` beside the other artifacts: one statement
per (advisory, component), with the audited app as the **product**, the
vulnerable package as a **subcomponent**, and the reaching surface as the
evidence for the status. The claim is "this app is affected by this CVE via this
component, reached by `TavilySearchResults` at `src/agent.ts:9`" — which is what
`mapping.json` measured and what a dependency scanner cannot say.

**Every statement is `affected`, and `not_affected` is refused.** Measured:
`mapping.json` holds one entry per LLM *surface*, so "no surface reaches this
component" is not "the vulnerable code is unreachable" — on the TypeScript
fixture `@langchain/core/messages` is imported by the app's own source with no
surface reaching it. Claiming `vulnerable_code_not_in_execute_path` from
surface reachability would suppress a real vulnerability in running code, so
`tests/test_vexctl_launch.py` asserts no module can pass that status at all.

**The consuming half is out of scope, for two measured reasons — revived only
by an upstream document appearing and a product-aware filter.** `vexctl filter`
joins on the SARIF `ruleId` being an advisory identifier and nothing else — a
condition advisory ingestion now satisfies, since a `known_advisory` finding's
`ruleId` is its CVE id. But in testing a statement about
`pkg:npm/totally-unrelated@1.0.0` suppressed a result about PyYAML, because the
product is ignored entirely; a filter that drops findings without checking which
component they concern would quietly undo "every finding cites the evidence that
produced it". And there is still no upstream document to apply.

What *did* come out of it is `findings.sarif.json`, emitted beside
`findings.json` — the same relationship `sbom.cyclonedx.json` has to
`sbom.json`. It stands on its own: SARIF is what CI annotations and code
scanning read. It is also **lossy**, and the loss is the important half —
`coverage`, the probes and the skipped files have no SARIF equivalent, so a
reader of that file alone gets a findings list with no caveat attached. It names
`findings.json` as the file that has them.

The vocabulary a statement may use, straight from `vexctl list`:

| Status | Justification, when `not_affected` |
|---|---|
| `not_affected` | `component_not_present` |
| `affected` | `vulnerable_code_not_present` |
| `fixed` | `vulnerable_code_not_in_execute_path` |
| `under_investigation` | `vulnerable_code_cannot_be_controlled_by_adversary` |
| | `inline_mitigations_already_exist` |

Two of those justifications are reachability claims, which is where this project
has something most VEX tooling has to guess at — and it is why the emitted
document carries the reaching surface in `status_notes`. It states reachability
positively and never negatively: the third justification in that column is
exactly the one this tool refuses to assert.

### Comparing against the baselines

The auditor is scored against two simpler systems: a five-rule regex scan, and
an SBOM-only scan. Each writes into its own directory, so no system can
overwrite another's output and the same scorer grades all three unchanged:

```sh
python src/run_baseline.py baseline_static_rules ~/code/some-llm-app
python src/run_baseline.py baseline_sbom_only ~/code/some-llm-app
python src/evaluate.py --system baseline_static_rules
```

| System | Reaches, of 6 graded findings *(verified run; re-measured 7 above)* | False positives on the two OSS apps |
|---|---|---|
| `agentic_auditor` | 2 | 2 — see the re-measure note above: both are real CVEs the key does not grade yet |
| `baseline_static_rules` | 5 | 1 |
| `baseline_sbom_only` | 0 | 187 |

Read the last column with care. Every one of the SBOM baseline's 187 is a *true*
statement — the component is present and unreviewed. They count as false
positives because the key grades vulnerabilities while the finding reports
inventory, which is a category mismatch rather than a tool being wrong. What
was missing was advisory data — since built, which is why the auditor's own
row above now carries the same category mismatch at 1/90th the scale.

### And against an off-the-shelf scanner

Worth doing once, because it shows what this project is and is not for. Trivy
has since become this project's own advisory engine (`deps/trivy_runner.py`
runs it offline, the way Syft is run) — but running it **directly** still
answers a different question than the auditor does, and the contrast is the
clearest statement of scope this repository can make.

```sh
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
  | sh -s -- -b ~/.local/bin
python src/fetch_repo.py https://github.com/Kilo-Org/security-agent-testbed
trivy fs --scanners vuln fetched/security-agent-testbed
```

On that repository, pinned at `89eaa8ab`, with Trivy 0.74.0:

| System | Findings | What it needed |
|---|---|---|
| Trivy, directly | **311** (22 critical, 128 high, 284 unique CVEs across 68 packages) | an advisory database |
| this auditor | **0 findings, and one number**: 79 advisory-carrying components reached by no LLM surface | the same database, plus the surface mapping |

**Both are correct, and the difference is now stated by the tool itself.** The
auditor reads the same database and joins it to the surface mapping: a finding
appears only when a vulnerable component is **reached by an LLM surface**, and
everything else becomes `coverage.advisory_unreached_component_count` — for
this repository, all 79, because a Next.js site has no LLM surfaces
(`surface_count: 0`). On an app that does call an LLM the same check fires:
`oss-app-langgraphjs-starter` yields two findings, both CVEs in
`@langchain/community@0.3.3`, anchored at the `TavilySearchResults` tool call
in `src/agent.ts:9` — a located, scorable claim `trivy fs` alone cannot make.

Run the tests with:

```sh
python -m pytest tests -q
```

## Layout

```
src/         the auditor's source code, one responsibility per module
  parsing/   read a repository and turn its files into syntax trees
  detectors/ find the four kinds of LLM surface in a tree
  artifacts/ the JSON documents each run produces, and their shapes
  deps/      read an app's dependencies, and match imports to packages
  checks/    the security checks, and the LangGraph planner that runs them
  retrieval/ the knowledge base behind the advice: chunks, pin, store, retrieve
  evaluation/ score the findings against a grading key; the one join rule
  baselines/ the two simpler systems the auditor is compared against
  main.py    audits one app; evaluate.py scores an audit against its key
  index_knowledge.py builds the knowledge index and writes its pin
  run_baseline.py runs one baseline over one repository
  outputs.py writes a run's artifacts, and makes the one model call an audit makes
  report.py  renders the audit report; remediation_report.py the fix advice
  model_client.py talks to Ollama
  config.py  settings from the environment; grading_keys.py locates the keys
knowledge/   the security guidance the advice is grounded on: an upstream clone
             per source and the index built from it, both gitignored. Only
             manifest.json and knowledge/README.md are committed
vex/         OpenVEX documents about the dependencies, with a manifest pinning
             each one. Empty, deliberately and expectedly: consuming VEX is out
             of scope, and vex/README.md says why
grading_keys/ committed: <app>.ground_truth.json, .manifest.json, .baseline.json
             — this project's own hand-written record of what is in an app.
             Empty as shipped; audited code is never committed here
tests/       pytest tests
docs/        plans, roadmap, and the artifact schemas
artifacts/   generated JSON output (gitignored)
```

**No audited code lives in this repository.** The auditor is pointed at a
repository by path or URL; a fetched tree lands under the gitignored `fetched/`,
never anywhere a grading key could be reading. That is why `grading_keys/`
holds only what this project wrote *about* an app.

### Making an app gradeable

Audit it first, so `artifacts/<system>/<name>/` exists. Then write, under
`grading_keys/` and named after that same directory:

- `<name>.manifest.json` — the upstream URL and the exact commit taken. Every
  line number in the grading key is only valid against that commit, so a key
  without a manifest is refused rather than scored.
- `<name>.ground_truth.json` — the known findings and expected surfaces,
  written by hand. Without it the auditor still runs; the app just cannot be
  scored. It is validated on load, because a hand-written key is input.
- `<name>.baseline.json` — optional: a snapshot of what the extractor finds
  today, so a change that silently drops or adds a surface fails a test. It is
  tool-derived, so it can never measure the tool's own accuracy — that is the
  grading key's job, and the scorer must not read this file.

Nothing else needs editing: `src/evaluate.py` discovers an app from its grading
key. **A key is only as good as the human who checked it**, which is why every
key records `source`, `verified`, `verified_by` and `verified_date`, and why a
score computed from an unverified key is qualified in `evaluation.json` rather
than reported plain.

## Documentation

- [`docs/CODING_RULES.md`](docs/CODING_RULES.md) — the standard this code is held to
- [`docs/FLOW.md`](docs/FLOW.md) — how the system works, step by step
- [`docs/TODO.md`](docs/TODO.md) — roadmap, current progress, open blockers
- [`docs/PHASE_1_PLAN.md`](docs/PHASE_1_PLAN.md) — Phase 1 task breakdown
- [`docs/PHASE_2_PLAN.md`](docs/PHASE_2_PLAN.md) — Phase 2 task breakdown
- [`docs/PHASE_3_PLAN.md`](docs/PHASE_3_PLAN.md) — Phase 3 task breakdown
- [`docs/PHASE_4_PLAN.md`](docs/PHASE_4_PLAN.md) — Phase 4 task breakdown, and
  what the evaluation may and may not claim
- [`docs/PHASE_5_PLAN.md`](docs/PHASE_5_PLAN.md) — Phase 5: auditing from a URL,
  and exporting the reports
- [`docs/RAG_PLAN.md`](docs/RAG_PLAN.md) — Phase 6: grounding the remediation
  advice in a pinned knowledge base, and what that may not claim
- [`docs/ADVISORY_PLAN.md`](docs/ADVISORY_PLAN.md) — advisory ingestion: Trivy
  as an offline generator, and the check anchored on the reaching surface
- [`docs/SCHEMAS.md`](docs/SCHEMAS.md) — the JSON contracts between phases

## Licence

MIT for this project's own code — see [LICENSE](LICENSE). Any repository you
audit keeps its own upstream licence; none is included here.
