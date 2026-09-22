# AgenticLLMAppAuditor

An SBOM-based vulnerability auditor. Build a bill of materials for a
repository, join it to a pinned advisory database, score each finding by the
published CVSS v3.1 equations, and add an **Organisation Risk Score** that
reflects the environment the code is deployed into.

A local model reads advisories and offers a judgement with its evidence. A
deterministic engine computes every number. The two are never the same step.

## Status

**Design stage. There is no code.**

| What exists | What it is |
|---|---|
| `CLAUDE.md` | the binding rules |
| `docs/SCORING_MODEL.md` | the Organisation Risk Score design |
| `docs/COUNCIL.md` | the assessor council design |
| `docs/diagrams.md` | every flow, as diagrams |
| `.claude/agents/` | six agent definitions |
| `docs/sources/` | the two source documents the design was read from |

What does not exist is everything else. No `src/`, no tests, no CLI, no
Python file of any kind. **This README has no usage section because there is
no command to run.** It gets one when a command exists and its output can be
pasted here.

## The design in brief

Four roles, and the boundaries between them are the design:

| Who | What they produce |
|---|---|
| NVD and the vendor | the published CVSS base score — quoted, never recomputed |
| the LLM | contextual analysis: exploit prerequisites, question selection, the rationale |
| the scoring engine | every number, deterministically, with no model in the path |
| the human | approval or override |

The CVSS base score and the Organisation Risk Score stay in separate fields
and are never blended. A CVE can be CVSS Critical and organisation Low — that
is the point of the exercise, not an error to reconcile.

The organisation score weights four categories on a 0–100 scale: technical
severity 30%, exposure and reachability 25%, business impact 25%, threat and
exploitation 20%.

The model may not determine a score, change a weight, override an escalation
rule, or approve a risk decision. Each of those is a refusal in application
code, not a line in a prompt.

Read [`docs/SCORING_MODEL.md`](docs/SCORING_MODEL.md) for the scoring design
and [`docs/COUNCIL.md`](docs/COUNCIL.md) for how several models assess one CVE
without any of them producing a number.

## Prerequisites

These are real today, unlike the tool. Versions are what is installed on the
development machine, not minimums except where stated.

| Tool | Version here | For |
|---|---|---|
| Python | 3.11.11 (3.10+) | the engine and the CLI |
| git | 2.43.0 | cloning the repositories under audit |
| Syft | 1.52.0 | building the SBOM |
| Trivy | 0.74.0 | the advisory database and the CVE join |
| Ollama | 0.34.2 | the local analyst model |

### The advisory database is a separate step

```bash
trivy image --download-db-only
```

```
2026-09-22T12:06:33+08:00	INFO	[vulndb] Need to update DB
2026-09-22T12:06:33+08:00	INFO	[vulndb] Downloading vulnerability DB...
2026-09-22T12:06:33+08:00	INFO	[vulndb] Downloading artifact...	repo="mirror.gcr.io/aquasec/trivy-db:2"
2026-09-22T12:06:38+08:00	INFO	[vulndb] Artifact successfully downloaded	repo="mirror.gcr.io/aquasec/trivy-db:2"
```

Progress bar elided. The download is 116 MiB and lands in `~/.cache/trivy`.

It is a separate step because scans will run offline, with
`--skip-db-update`, so that a scan is reproducible and pinned to a known
database. The cost of that choice: **an empty or stale cache produces a clean
report rather than an error.** Trivy finds no advisories, reports no
vulnerabilities, exits 0, and nothing in the output says the database was
missing. Every CVE is missed silently.

So check the database before trusting a scan:

```bash
trivy version
```

```
Version: 0.74.0
Vulnerability DB:
  Version: 2
  UpdatedAt: 2026-09-22 02:00:05.774028462 +0000 UTC
  NextUpdate: 2026-09-23 02:00:05.774027771 +0000 UTC
  DownloadedAt: 2026-09-22 04:06:38.609232067 +0000 UTC
```

## The proxy on this machine

A corporate HTTP proxy is set, and the two cases pull in opposite directions.

| Talking to | Proxy |
|---|---|
| a local service — Ollama, a dev server, anything on loopback | **off** |
| the internet — `git clone`, `trivy image --download-db-only` | **on** |

Before running anything that talks to a local service:

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
```

Without it, `urllib` sends loopback requests to the proxy, which answers 502.
The failure reads as the local service being down, which sends you looking in
the wrong place. `CLAUDE.md` carries the same note.

## Working on it

`CLAUDE.md` is binding. Work that breaks one of its rules is not done. Read it
before writing anything; it is short.

Six agents are defined in `.claude/agents/`:

| Agent | For |
|---|---|
| `python-developer` | the deterministic half — parsers, data models, CLI, the scoring engine |
| `ai-engineer` | prompts, the Ollama client, parsing model replies, measuring whether a model is any good |
| `frontend-developer` | the browser-facing JavaScript — components, state, styling, the build |
| `tester` | writes tests, runs the suite, reproduces bugs |
| `technical-writer` | this README, `docs/*.md`, docstrings, design records |
| `judge` | reviews finished work against `CLAUDE.md`; read-only, and it never edits |

Where an agent's instructions disagree with `docs/SCORING_MODEL.md`, the
design document wins.

## Repository layout

```
.
├── CLAUDE.md                 the binding rules
├── LICENSE                   MIT
├── .gitignore
├── .claude/
│   └── agents/
│       ├── judge.md
│       ├── ai-engineer.md
│       ├── frontend-developer.md
│       ├── python-developer.md
│       ├── technical-writer.md
│       └── tester.md
└── docs/
    ├── COUNCIL.md            the assessor council
    ├── SCORING_MODEL.md      the Organisation Risk Score
    └── sources/
        ├── brainstorming.pdf
        └── note.docx
```

That is the whole repository.

## Licence

MIT. See [`LICENSE`](LICENSE).
