# AgenticLLMAppAuditor

An offline, human-in-the-loop security auditor for LLM applications
(LangChain / LangGraph). It analyses a repository and reports findings mapped
to a subset of the OWASP Top 10 for LLM Applications, backed by SBOM/AIBOM
evidence.

It reads **Python** (via the standard library's `ast`) and **JavaScript and
TypeScript** (via tree-sitter). The design is language-agnostic: adding one
starts in `src/parsing/languages.py`.

It **reports only** — it never edits, patches, or merges the audited code — and
it runs offline against a local model.

Master's degree project. Contributors: Hein Thet Naung, Neo Jia Wei,
Tan Bing Hong.

## Status

**Phase 2: SBOM/AIBOM and surface-to-component mapping.** Static analysis only.
LLM-driven detection and sandboxed probing are Phase 3, and the local model
client is set up but not yet used to detect anything.

Phase 1 is complete: the extractor finds prompt templates, agent definitions,
tool definitions and data-source sites, and records where each one lives.
Phase 2 adds a bill of materials for Python and npm dependencies, an inventory
of the models, tools and agents, and a join from each surface to the package it
came from.

What that produces on the two fixtures today:

| Fixture | surfaces | components | surfaces joined to a package |
|---|---|---|---|
| `vuln-app-1-support-agent` (Python) | 19 | 5 | 6 of 19 |
| `oss-app-langgraphjs-starter` (TypeScript) | 5 | 82 | 4 of 5 |

Most unjoined surfaces are not defects: a language builtin, the app's own code,
or a call on a local variable whose type static analysis cannot follow.

One kind is a finding. A package used but never declared is a supply-chain
risk — one surface in the Python fixture hits it, importing PyYAML.
`mapping.json` records which of the five reasons each surface got, so "no
package exists" is never confused with "we could not tell", and neither is
confused with a finding.

The second app has no planted vulnerabilities, so it is the fixture that
measures **false positives**: it currently reports 5 of 5 expected surfaces and
nothing else.

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
```

The first app carries planted vulnerabilities and measures **recall**. The
second is an official starter template with nothing planted in it, so it is the
only fixture that can measure **false positives** — a detector that flags
something here is wrong by construction.

**The checkout line matters as much as the clone.** Every line number in a
grading key is recorded against that app's pinned commit. Both happen to be on
the default branch today, but the moment upstream commits anything a plain
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

It writes everything it can into `artifacts/<app>/` and makes no network call:

| Artifact | Needs |
|---|---|
| `surfaces.json` | nothing but the source. Also records any file it could not read, so a later phase never mistakes a partial scan for a complete one |
| `aibom.json` | the same — it is derived from the surfaces |
| `sbom.json` | Syft, plus a `requirements.txt` (Python) or a `package.json` (npm) |
| `sbom.cyclonedx.json` | the same scan, re-emitted in the standard format |
| `mapping.json` | the SBOM, to join each surface to the package it came from |

Producing less is a normal outcome, not a failure. Without Syft, or with no
manifest it knows how to read, it writes the first two and says on stderr why
the rest were skipped. A repository declaring **both** a Python and an npm
manifest is refused a bill rather than given half of one.

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
  main.py    the single entry point; model_client.py talks to Ollama
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
- [`docs/SCHEMAS.md`](docs/SCHEMAS.md) — the JSON contracts between phases

## Licence

MIT for this project's own code — see [LICENSE](LICENSE). The demo apps under
`corpus/` keep their own upstream licences.
