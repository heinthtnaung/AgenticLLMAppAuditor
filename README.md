# AgenticLLMAppAuditor

An offline, human-in-the-loop security auditor for Python LLM applications
(LangChain / LangGraph). It analyses a repository and reports findings mapped
to a subset of the OWASP Top 10 for LLM Applications, backed by SBOM/AIBOM
evidence.

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

## Setup

Python 3.10 or newer. Use one virtual environment named `.venv` at the repo
root:

```sh
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

If `python -m venv` reports that `ensurepip` is unavailable, install the
matching venv package first (on Debian/Ubuntu: `sudo apt install python3-venv`).

## Usage

Extract the LLM surfaces of a repository:

```sh
python src/main.py corpus/vuln-app-1-support-agent
```

This writes `artifacts/<app>/surfaces.json`. Run the tests with:

```sh
python -m pytest tests -q
```

## Layout

```
src/         the auditor's source code, one responsibility per module
corpus/      the applications being audited, with their ground truth
tests/       pytest tests
docs/        plans, roadmap, and the artifact schemas
artifacts/   generated JSON output (gitignored)
```

The apps under `corpus/` are **deliberately vulnerable** third-party fixtures,
pinned to an upstream commit in each app's `MANIFEST.json`. They are audited
input, not dependencies: never install their requirements, and never "fix"
their code.

## Documentation

- [`docs/TODO.md`](docs/TODO.md) — roadmap, current progress, open blockers
- [`docs/PHASE_1_PLAN.md`](docs/PHASE_1_PLAN.md) — Phase 1 task breakdown
- [`docs/SCHEMAS.md`](docs/SCHEMAS.md) — the JSON contracts between phases

## Licence

MIT for this project's own code — see [LICENSE](LICENSE). The demo apps under
`corpus/` keep their own upstream licences.
