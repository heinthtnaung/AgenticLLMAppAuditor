# AgenticLLMAppAuditor

An offline, human-in-the-loop security auditor for LLM applications
(LangChain / LangGraph). It analyses a repository and reports findings mapped
to a subset of the OWASP Top 10 for LLM Applications, backed by SBOM/AIBOM
evidence.

It reads **Python** (via the standard library's `ast`) and **JavaScript and
TypeScript** (via tree-sitter). The design is language-agnostic: adding one
starts in `src/languages.py`.

It **reports only** — it never edits, patches, or merges the audited code — and
it runs offline against a local model.

Master's degree project. Contributors: Hein Thet Naung, Neo Jia Wei,
Tan Bing Hong.

## Status

**Phase 1: LLM surface extractor.** Static analysis only — the extractor finds
prompt templates, agent definitions, tool definitions, and data-source sites,
and records where each one lives. LLM-driven detection and sandboxed probing
are Phase 3.

Progress and blockers: [`docs/TODO.md`](docs/TODO.md).

## Prerequisites

Only the first row is needed to run the auditor. The rest are for specific
tasks, so you can start without them.

| You need | Version | What for | Check |
|---|---|---|---|
| **Python** | 3.10 or newer | everything — the auditor uses modern type hints | `python3 --version` |
| **git** | any | cloning this repository | `git --version` |
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

The auditor makes **no network calls at all**. Ollama, when you use it, runs on
your own machine.

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

### Downloading the app

The audited app is a third-party project, so its source is **not** committed
here — only what this project authored about it, in `corpus/evidence/`.
Download it once:

```sh
git clone https://github.com/ReversecLabs/damn-vulnerable-llm-agent \
    corpus/vuln-app-1-support-agent
git -C corpus/vuln-app-1-support-agent checkout -q c0cf9a14adad76e9d6a53c41741f625334bd9971
```

**Both lines matter.** Every line number in the grading key is recorded against
commit `c0cf9a14`, which happens to be the default branch today — but the
moment upstream commits anything, a plain `git clone` lands on different code.
That drift is caught (the `code_anchor` test fails, naming the findings), but
it is far easier to pin the commit than to debug the failure later. The same
commit is recorded in
`corpus/evidence/vuln-app-1-support-agent.manifest.json`.

Optionally, `rm -rf corpus/vuln-app-1-support-agent/.git` afterwards. It saves
1.5 MB and stops a later `git pull` silently moving you off the pin. Nothing
depends on it: the auditor skips `.git` directories anyway.

Until you run this, the tests that need the app skip and say so; everything
else runs.

### Running the auditor

Extract the LLM surfaces of a repository:

```sh
python src/main.py corpus/vuln-app-1-support-agent
```

It writes `artifacts/<app>/surfaces.json` and makes no network call.

This writes `artifacts/<app>/surfaces.json`. Run the tests with:

```sh
python -m pytest tests -q
```

## Layout

```
src/         the auditor's source code, one responsibility per module
corpus/
  <app>/     the audited app, downloaded not committed (see Usage)
  evidence/  committed: grading key, manifest, baseline — this project's work
tests/       pytest tests
docs/        plans, roadmap, and the artifact schemas
artifacts/   generated JSON output (gitignored)
```

The app under `corpus/` is a deliberately vulnerable third-party fixture,
pinned to an upstream commit in `corpus/evidence/`. It is audited input, not a
dependency: never install its requirements, and never "fix" its code. Its
source is downloaded rather than committed, so this repository contains no
other project's code. Phase 1 audits one app; more are added when the
evaluation needs them.

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

Nothing else needs editing: the suite discovers a fixture from its grading key
in `corpus/evidence/`. Putting those files inside `corpus/<name>/` instead
leaves the app **silently ungraded**, so the layout matters.

## Documentation

- [`docs/CODING_RULES.md`](docs/CODING_RULES.md) — the standard this code is held to
- [`docs/FLOW.md`](docs/FLOW.md) — how the system works, step by step
- [`docs/TODO.md`](docs/TODO.md) — roadmap, current progress, open blockers
- [`docs/PHASE_1_PLAN.md`](docs/PHASE_1_PLAN.md) — Phase 1 task breakdown
- [`docs/SCHEMAS.md`](docs/SCHEMAS.md) — the JSON contracts between phases

## Licence

MIT for this project's own code — see [LICENSE](LICENSE). The demo apps under
`corpus/` keep their own upstream licences.
