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

**All four phases produce their artifacts.** Static analysis only, and the
auditor never runs the app it audits.

- **Phase 1** extracts LLM surfaces — prompt templates, agent definitions, tool
  definitions and data-source sites — and records where each one lives.
- **Phase 2** builds a bill of materials for Python and npm dependencies, an
  inventory of the models, tools and agents, and a join from each surface to the
  package it came from.
- **Phase 3** runs three checks under a bounded LangGraph planner, writing
  `findings.json` and a `report.md` that gives what was *not* examined the same
  billing as what was found.
- **Phase 4** scores those findings against hand-written grading keys and against
  two baselines, in counts and never rates.

**What is not built is inside those phases, not after them.** The local model
writes nothing — every run records `model_run.status: "disabled"`. No advisory
data is ingested, so a supply-chain finding names a package but not what is
known to be wrong with it. The auditor covers three of the five risk classes it
names.

### The headline result

**On this corpus a five-rule regex baseline reaches more of the grading key than
the auditor does — 5 of 6 against 2 of 6.** That is reported first because a
comparison that only shows wins is not evidence.

The two are near-complementary rather than competing: their union is all six,
and they share only one. The auditor reaches `VULN1-06` alone — the
supply-chain finding — because reaching it means joining a *surface* to a
*component*, which no baseline has. Where the auditor loses, it loses ground it
never entered: LLM02 and AUDITABILITY are absent from its coverage entirely.

Both systems were authored with this corpus visible, so neither figure
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
construction. Only the TypeScript one currently carries real **false-positive**
evidence: its supply-chain check ran against an 82-component SBOM and its one
tool surface was judged, so a check could have been wrong and was not. The
Python one reports no findings either, but no check there had a subject to be
wrong about — it has no tool surface, its taint trace ran and reached no
conclusion, and it has no bill of materials at all. Its zero is **0 out of 0
opportunities**, which is worth having and is not the same claim.

`oss-app-react-agent` declares its dependencies in `pyproject.toml` and pins
them in `uv.lock`, and this tool reads neither, so it produces no bill of
materials and no mapping — the dashes above. That is a real gap, not a bad fixture: it is the only fixture that
exercises what the tool does when it cannot see an app's dependencies at all.

### What it scores against the grading keys

| Fixture | key findings | matched | missed | false positives |
|---|---|---|---|---|
| `vuln-app-1-support-agent` | 6 | 2 | 4 | **not measurable** — its key does not claim to list every finding, so the count is `null` rather than `0` |
| `oss-app-langgraphjs-starter` | 0 | — | 0 | 0 |
| `oss-app-react-agent` | 0 | — | 0 | 0 |

**Counts, never rates.** `evaluation.json` holds no float and no percentage:
precision, recall and F1 are absent as fields, so a number cannot be quoted
without the denominator beside it. F1 is refused outright, with the reason
recorded in the file — no fixture supports both a precision and a recall number,
so there is nothing to combine.

Each miss carries the reason it was missed rather than a bare count. Of the
four: two are checks that ran and stayed silent, and two are risk classes no
check covers yet. That breakdown is more useful than the total, and it is why
a short findings list is never reported as a clean bill.

Three applications is still a demonstration, not a measurement, and the artifact
says so: all three trip the `small_sample` qualification. All three keys are now
human-verified, so none trips `key_unverified` — but they remain
`source: ai_drafted`, because who drafted a key and who checked it are different
facts and the artifact records both.

Progress and blockers: [`docs/TODO.md`](docs/TODO.md).

## Prerequisites

Only the first row is needed to run the auditor. The rest are for specific
tasks, so you can start without them.

| You need | Version | What for | Check |
|---|---|---|---|
| **Python** | 3.10 or newer | everything — the auditor uses modern type hints | `python3 --version` |
| **git** | any | cloning this repository | `git --version` |
| **Syft** | 1.51.0 | building an SBOM (`src/main.py`) from a `requirements.txt` or a `package.json`. Not needed to extract surfaces | `syft version` |
| **Ollama** | any | only the local model client (`src/model_client.py`), which is set up for Phase 3 and unused by the extractor | `ollama --version` |

On Debian or Ubuntu, Python's venv support is a separate package:

```sh
sudo apt install python3-venv
```

Everything else is installed by `pip` into the virtual environment below.
There are only two dependencies, and neither is needed to read Python:

| Package | What for |
|---|---|
| `tree-sitter` + `tree-sitter-javascript` + `tree-sitter-typescript` | parsing JavaScript and TypeScript. Python is read with the standard library's `ast`, so these are only used for JS/TS |
| `pytest` | running the tests |

The auditor makes **no network calls**. Ollama and Syft both run on your own
machine; Syft is told explicitly not to check for its own updates, which is
the one thing it would otherwise do over the network.

Install Syft to `~/.local/bin` without root:

```sh
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
  | sh -s -- -b ~/.local/bin
```

### Optional: the local model

Needed only if you want `src/model_client.py` to answer. Install Ollama, then:

```sh
ollama pull qwen2.5-coder:7b-instruct
python src/model_client.py          # prints a reply from the local server
```

Without it the extractor works normally and the model test skips.

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
AUDITOR_MODEL=llama3.1:8b python src/main.py corpus/vuln-app-1-support-agent
```

## Usage

### Downloading the apps

The audited apps are third-party projects, so their source is **not** committed
here — only what this project authored about them, in `corpus/evidence/`.
Download them once:

```sh
git clone https://github.com/ReversecLabs/damn-vulnerable-llm-agent \
    corpus/vuln-app-1-support-agent
git -C corpus/vuln-app-1-support-agent checkout -q c0cf9a14adad76e9d6a53c41741f625334bd9971

git clone https://github.com/langchain-ai/langgraphjs-studio-starter \
    corpus/oss-app-langgraphjs-starter
git -C corpus/oss-app-langgraphjs-starter checkout -q cd9a02c64afd97fe008199665ebb0aac803451da

git clone https://github.com/langchain-ai/react-agent \
    corpus/oss-app-react-agent
git -C corpus/oss-app-react-agent checkout -q 9bbd82d84905acc37f527b1f372dae841016f3b4
```

The first app carries planted vulnerabilities and measures **recall**. The other
two are official starter templates with nothing planted in them, so they are
what measures **false positives** — a detector that flags something in either is
wrong by construction. They are deliberately one TypeScript and one Python: the
taint trace only reads Python, so a false-positive number taken solely from a
language it cannot parse would say very little.

**The checkout line matters as much as the clone.** Every line number in a
grading key is recorded against that app's pinned commit. All three happen to be
on the default branch today, but the moment upstream commits anything a plain
`git clone` lands on different code. The drift is caught — the `code_anchor`
test fails and names the findings — but pinning is far cheaper than debugging
that later. Each commit is recorded in its
`corpus/evidence/<app>.manifest.json`.

Optionally, `rm -rf corpus/*/.git` afterwards. It saves a few MB and stops a
later `git pull` silently moving you off the pin. Nothing depends on it: the
auditor skips `.git` directories anyway.

Until you run this, the tests that need an app skip and say so; everything else
runs. The suite is green without Syft and without Ollama too — those tests skip
rather than fail, so a fresh checkout needs only Python.

### Running the auditor

Audit a repository:

```sh
python src/main.py corpus/vuln-app-1-support-agent
```

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

Producing less is a normal outcome, not a failure. Without Syft, or with no
manifest it knows how to read, it writes what it can and says on stderr why the
rest were skipped. A repository declaring **both** a Python and an npm
manifest is refused a bill rather than given half of one.

### Scoring the corpus

Once every fixture has been audited, score what was found against their
grading keys:

```sh
python src/evaluate.py
```

It writes `artifacts/<system>/evaluation.json` — one file per system per run,
not one per app, because a comparison across apps is not a per-app fact. The
system defaults to `agentic_auditor`; `--system` takes one of the three names
in `SCORED_SYSTEMS`, and that name is also the directory the artifacts are read
from, so three systems can be scored without overwriting each other.

It prints counts and what bounds them, and **never a rate**. The vulnerable
fixture's block — a real run also lists the two clean fixtures first (apps are
sorted) and adds a `precision pool` line, omitted here:

```
scored 3 apps as agentic_auditor, wrote artifacts/agentic_auditor/evaluation.json
  vuln-app-1-support-agent: 2 of 6 matched, 4 missed, false positives not measurable
    bounded by: advisory_data_not_ingested, expected_surfaces_not_complete, findings_not_complete, key_ai_drafted, model_disabled, small_sample, unresolved_components
  recall pool: 2 of 6 over vuln-app-1-support-agent
  f1: no app supports both precision and recall
```

Precision, recall and F1 are absent from the artifact as fields. A reader who
wants a rate divides for themselves, which means holding the denominator and
the qualifications printed beside it. "False positives not measurable" is not
a bug: that fixture's key does not claim to list every finding, so the count is
undefined and recorded as `null` rather than `0`.

### Comparing against the baselines

The auditor is scored against two simpler systems: a five-rule regex scan, and
an SBOM-only scan. Each writes into its own directory, so no system can
overwrite another's output and the same scorer grades all three unchanged:

```sh
python src/run_baseline.py baseline_static_rules
python src/run_baseline.py baseline_sbom_only
python src/evaluate.py --system baseline_static_rules
```

| System | Reaches, of 6 graded findings | False positives on the clean apps |
|---|---|---|
| `agentic_auditor` | 2 | 0 |
| `baseline_static_rules` | 5 | 1 |
| `baseline_sbom_only` | 0 | 187 |

Read the last column with care. Every one of the SBOM baseline's 187 is a *true*
statement — the component is present and unreviewed. They count as false
positives because the key grades vulnerabilities while the finding reports
inventory, which is a category mismatch rather than a tool being wrong. What is
missing is advisory data, and that is this project's own unfinished Phase 2
work.

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
  evaluation/ score the findings against a grading key; the one join rule
  baselines/ the two simpler systems the auditor is compared against
  main.py    audits one app; evaluate.py scores the corpus against its keys
  run_baseline.py runs one baseline over the corpus
  report.py  renders the human-readable report
  model_client.py talks to Ollama
  config.py  settings from the environment; corpus_paths.py locates fixtures
corpus/
  <app>/     the audited app, downloaded not committed (see Usage)
  evidence/  committed: grading key, manifest, baseline — this project's work
tests/       pytest tests
docs/        plans, roadmap, and the artifact schemas
artifacts/   generated JSON output (gitignored)
```

The apps under `corpus/` are third-party fixtures, one of them deliberately
vulnerable, each pinned to an upstream commit in `corpus/evidence/`. They are
audited input, not dependencies: never install their requirements, and never
"fix" their code. Their source is downloaded rather than committed, so this
repository contains no other project's code. One measures recall against
planted findings; the other measures false positives on clean code.

### Adding an app to the corpus

Clone it into `corpus/<name>/` and delete its `.git`. That directory is then a
byte-identical copy of upstream and is never edited again.

Everything you write about it goes in `corpus/evidence/`, **not** inside the
app directory:

- `corpus/evidence/<name>.manifest.json` — the upstream URL and the exact
  commit taken. Every line number in the ground truth is only valid against
  that commit.
- `corpus/evidence/<name>.ground_truth.json` — the known findings and expected
  surfaces. Without it the extractor still runs, but the app cannot be scored,
  so it contributes nothing to Phase 4.
- `corpus/evidence/<name>.baseline.json` — a snapshot of what the extractor
  finds today, so a change that silently drops or adds a surface fails a test.
  It is tool-derived, so it can never measure the tool's own accuracy: that is
  the grading key's job, and Phase 4 must not read this file.

Nothing else needs editing: the suite discovers a fixture from its grading key
in `corpus/evidence/`. Putting those files inside `corpus/<name>/` instead
leaves the app **silently ungraded**, so the layout matters.

## Documentation

- [`docs/CODING_RULES.md`](docs/CODING_RULES.md) — the standard this code is held to
- [`docs/FLOW.md`](docs/FLOW.md) — how the system works, step by step
- [`docs/TODO.md`](docs/TODO.md) — roadmap, current progress, open blockers
- [`docs/PHASE_1_PLAN.md`](docs/PHASE_1_PLAN.md) — Phase 1 task breakdown
- [`docs/PHASE_2_PLAN.md`](docs/PHASE_2_PLAN.md) — Phase 2 task breakdown
- [`docs/PHASE_3_PLAN.md`](docs/PHASE_3_PLAN.md) — Phase 3 task breakdown
- [`docs/PHASE_4_PLAN.md`](docs/PHASE_4_PLAN.md) — Phase 4 task breakdown, and
  what the evaluation may and may not claim
- [`docs/SCHEMAS.md`](docs/SCHEMAS.md) — the JSON contracts between phases

## Licence

MIT for this project's own code — see [LICENSE](LICENSE). The demo apps under
`corpus/` keep their own upstream licences.
