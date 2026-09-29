# AgenticLLMAppAuditor

An SBOM-based vulnerability auditor. It lists a repository's components with
Syft, matches them to advisories in an offline Trivy database, and scores every
published CVSS v3.1 vector, one source at a time. Answer twelve questions about
your environment and it adds an **Organisation Risk Score**. Name local models
and a **council** reads each disputed advisory, quoting the text behind every
value it gives. Every number comes from a deterministic engine, never a model.

This page is the short version. [docs/USAGE.md](docs/USAGE.md) is the full
guide.

## Prerequisites

| Tool | For | Tested with | Minimum |
|---|---|---|---|
| Python | everything | 3.11.11 | 3.10 |
| [Syft](https://github.com/anchore/syft) | listing the components | 1.52.0 | none set |
| [Trivy](https://trivy.dev) and its advisory database | matching advisories, offline | 0.74.0 | none set |
| [Ollama](https://ollama.com) and a pulled model | the council (optional) | 0.34.3 | none set |

The runtime is the standard library alone; pytest is the only development
dependency. [docs/SETUP.md](docs/SETUP.md) has the rest: git, npm, where the
database is kept, and the corporate proxy.

Download the advisory database once. It needs network access, so on a corporate
network the proxy must be **on**:

```bash
trivy image --download-db-only
```

It lands in `$TRIVY_CACHE_DIR` if set, else `$XDG_CACHE_HOME/trivy`, else
`~/.cache/trivy`. Scans read it offline and never update it; run the download
again to update it.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

This puts the `audit` command on your path. The install fetches a build
backend, so it needs network access too.

## Quick start

The examples scan `fetched/vulnscout`, the repository this project audits. Fetch
it once, at the commit the examples were checked against:

```bash
git clone https://github.com/savoirfairelinux/vulnscout.git fetched/vulnscout
git -C fetched/vulnscout checkout df874ef0669e4a861a2480d7dda18a9fcb6d4d66
```

Cloning needs network access, so on a corporate network the proxy must be
**on**; [docs/SETUP.md](docs/SETUP.md) says why scanning wants it off. `audit`
itself never clones: point it at any directory. Model names below are examples,
and any model pulled into the local Ollama can be named.

### Scan a repository

```bash
audit fetched/vulnscout
```

Prints the text report and saves it as text, JSON and HTML in `reports/`, named
after the directory. The last line on stderr says where:
`reports written to reports/vulnscout.txt, reports/vulnscout.json, reports/vulnscout.html`.

<!-- doc-check: run (elided) -->
```
Audit of fetched/vulnscout
  syft 1.52.0  ·  trivy 0.74.0  ·  advisory database built 2026-09-23T20:20:57.734988316Z
  scoring rules ors-1

18 findings across 60 components. 5 carry sources that disagree.
Approval is needed for 5 of 18: sources that disagree. With no organisation answers, none was
checked for a High or Critical Organisation Risk Score. No approval is recorded for this audit.

SOURCES DISAGREE (5)
  CVE-2025-13465  lodash-es 4.17.21
    2.9 apart  ·  High and Medium  ·  differ on A
    ghsa 6.5  ·  nvd 5.3  ·  redhat 8.2

SOURCES AGREE (13)
  CVE-2026-14257       brace-expansion 1.1.14          7.5  High      2 sources

NOT ASSESSED
  Organisation Risk Score
    no organisation answers were supplied, so no environment was weighed
  Approval record
    no answer file was given, so nobody was asked about this environment
  Council ruling
    no council assessed this run, so no council reading stands beside the published scores
  Why the sources differ
    no council was asked for, so no model was asked why the published sources differ
```

Elided: four of the five disagreements, twelve of the thirteen agreements, and
the `MATCHED NOTHING` and `NEEDS APPROVAL` blocks. The rest is verbatim, the
database date being the one it was recorded against. What is not assessed is
named, never printed as a zero.

### Print JSON or HTML instead

```bash
audit fetched/vulnscout --format json
```

Prints the JSON record on stdout (`--format html` prints the page). All three
files are saved either way.

### Score it against your environment

Answer the twelve approved questions in a JSON file.
[`answers.example.json`](answers.example.json) is a skeleton with every answer
`No`. Filled in for an internet-facing, business-critical asset:

<!-- doc-check: answers -->
```json
{
  "answers": {
    "EXP-1": "Yes", "EXP-2": "Yes", "EXP-3": "Yes", "EXP-4": "No", "EXP-5": "No",
    "BUS-1": "Yes", "BUS-2": "Yes", "BUS-3": "Yes", "BUS-4": "Yes",
    "THR-1": "No",  "THR-2": "No",  "THR-3": "No"
  },
  "by_advisory": {
    "CVE-2021-4279": {"THR-1": "Yes", "THR-2": "Yes"}
  },
  "approval": {
    "approver": "Hein",
    "decision": "approved",
    "recorded_at": "2026-09-23T09:15:00Z",
    "note": "reviewed against the staging inventory"
  }
}
```

```bash
audit fetched/vulnscout --answers answers.json
```

Adds an Organisation Risk Score, 0 to 100, for each published source:

<!-- doc-check: run --answers -->
```
ORGANISATION RISK (18)  ·  the source changes the band on 1
  weighted Technical severity 0.3, Exposure and reachability 0.25, Business impact 0.25, Threat and exploitation 0.2
  CVE-2026-4800        ghsa 70.5 to nvd 75.7       Critical and High
  CVE-2021-4279        ghsa 84.2 to nvd 91.7       Critical
  CVE-2025-13465       nvd 62.1 to redhat 70.8     High
  CVE-2026-13149       ghsa 62.1 to redhat 68.8    High
  CVE-2026-13676       68.8                        High
  CVE-2026-14257       68.8                        High
```

A range runs from one source's score to another's, and the heading counts the
findings whose band depends on which source you believe.

### Add a council of local models

Pull each model once, then name them:

```bash
ollama pull qwen2.5:7b-instruct
ollama pull llama3.2:latest
audit fetched/vulnscout --council-member qwen2.5:7b-instruct --council-member llama3.2:latest
```

Each model reads the advisory of every finding whose published sources disagree,
and the report adds the vector they settle, or the metrics they could not. A
model's readings need their own evaluation before they are trusted
([measurements/README.md](measurements/README.md)).

### Name the council once, in `.env`

```bash
audit fetched/vulnscout --council
```

Runs the models `AUDITOR_COUNCIL_MEMBERS` names in `.env`, for example
`AUDITOR_COUNCIL_MEMBERS=gemma4:latest,qwen2.5:7b-instruct`.

### Escalate what the council leaves open

```bash
AUDITOR_ESCALATION_MODEL=qwen2.5:14b audit fetched/vulnscout --council
```

Sends each metric the council leaves contested or unresolved to one larger
local model.

### Ask the council about every finding

```bash
audit fetched/vulnscout --council --council-all-findings
```

Puts every finding to the council, not only those whose sources disagree: for
two members on this repository, 576 council calls instead of 160. Either way
the run adds one explanation call per finding whose sources disagree, 5 here,
and escalation adds 2 for each metric the council leaves open.

A council run prints one line per model call on stderr, so a slow model is
visible. The report stays on stdout.

## Settings

Six `AUDITOR_*` keys, read from the environment, then from `.env` at the project
root, then the default. Copy `.env.example` to `.env` to start. `audit` reads
them only on a council run.

| Key | Default | Sets |
|---|---|---|
| `AUDITOR_COUNCIL_MEMBERS` | unset | the models `--council` runs, comma-separated |
| `AUDITOR_ESCALATION_MODEL` | unset | one local model for what the council leaves open |
| `AUDITOR_SERVER_URL` | `http://127.0.0.1:11434` | the Ollama server, which must be this machine |
| `AUDITOR_TIMEOUT_SECONDS` | `180` | how long one model call may wait |
| `AUDITOR_CONTEXT_TOKENS` | `8192` | the context window every model is pinned to |
| `AUDITOR_MODEL` | `qwen2.5:7b-instruct` | the model a measurement script asks; never the audit's |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | ran, catalogued components, found nothing, and read every manifest |
| `1` | ran and found something |
| `2` | could not run, or could not save its reports |
| `3` | ran and found nothing, but could not read a manifest or catalogued no component |

A pipeline that passes only on `0` stops on the rest.

## Running the tests

```bash
pip install -e '.[dev]'
python -m pytest -q
```

Some tests skip unless a flag asks for them, because they need a model, a
scanner or a real scan. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) lists the
flags.

## Learn more

| Document | What it holds |
|---|---|
| [docs/USAGE.md](docs/USAGE.md) | the full guide: every flag, output, setting and council behaviour |
| [docs/SETUP.md](docs/SETUP.md) | prerequisites in depth, the advisory database, the proxy |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | build status, the tests and their flags, the layout |
| [docs/SCORING_MODEL.md](docs/SCORING_MODEL.md) | how the Organisation Risk Score is computed |
| [docs/COUNCIL.md](docs/COUNCIL.md) | how the council works, and why |
| [docs/diagrams.md](docs/diagrams.md) | every flow, as diagrams |
| [measurements/README.md](measurements/README.md) | the measurements behind every cited figure |

## Licence

MIT. See [`LICENSE`](LICENSE).
