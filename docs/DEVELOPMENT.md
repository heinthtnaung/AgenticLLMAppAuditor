# Working on the auditor

What is built, how the tests run, and where everything is.
[The README](../README.md) is for running it.

## Status

**It runs end to end.** A repository on disk becomes a report: components
catalogued, advisories joined, every source's published vector scored and kept
attributed, a council of local models asked if you name one, and every finding
weighed against your environment into an Organisation Risk Score if you answer
the approved questions. The two optional halves are named as absent when you
leave them out — `NOT ASSESSED`, never a zero and never an omission. So is every
manifest the scan could read no version from, and an inventory in which Syft
catalogued nothing.

| Part | State | What it is |
|---|---|---|
| `src/deps/` | built | Syft and Trivy: the components a directory declares, the advisories published against them, the secrets Trivy's built-in rules match, and the database's own build date; and which manifests have no lock file Syft reads |
| `src/cvss/` | built | a CVSS v3 vector parsed and validated, Temporal metrics included, and its Base score by the published equations |
| `src/findings/` | built | the join — a CVE affecting an installed component, with every source's score kept apart and attributed |
| `src/scoring/` | built | the approved question library, per-question weights, categories clamped then weighted, the band, the two severity floors that can raise it, and the version naming those rules |
| `src/council/` | built | the roster and its `egress` gate, redaction, the prompt, a provider registry holding one Ollama client, the quotation check, the order check, the chairman, the runner, escalation of what the council leaves open to one larger model on the members' server, and the explainer that says why a finding's sources differ |
| `src/organisation/` | built | the answer file, the approval record, the rule for which findings need approval, and one risk score per published source |
| `src/report/` | built | the record every run produces, and its three renderings: a terminal report, the JSON audit artefact, and one self-contained, tabbed HTML page with its stylesheet and script inlined |
| `src/cli/` | built | the arguments, the preflight refusals, the order the packages run in, which findings the council is put to, the server version and model digests a council run records, the progress it prints to stderr, the three report files in `reports/`, and the exit code |
| question selector | design | every approved question is asked, rather than the few a CVE's prerequisites call for |
| answer validation | design | no model reads the answers back for gaps or contradictions |
| hosted provider client | design | the local client works; nothing reaches OpenRouter or another API, so a hosted member is skipped for want of one. An adapter and a registry entry, and no other module moves |
| an approval command | design | an approval is recorded, never stamped: the time arrives with it in the answer file, because there is no clock anywhere in `src/` |

Diagram 5 of [`docs/diagrams.md`](diagrams.md) draws the same boundary from
the import graph. Nothing built is unreachable any more: `src/organisation`
imports the scoring engine, and `src/cli` reaches six packages to close the line
from a directory on disk to a banded score.

## Running the tests

`pytest` is the only development dependency — the runtime is standard library —
and the `dev` extra installs it:

```bash
pip install -e '.[dev]'
python -m pytest -q
```

`requirements.txt` pins the same pytest, and `tests/test_pyproject.py` holds the
two to each other.

No total is pasted here: the suite grows with every module that lands, so a
total written down is wrong within the day. The table below is held instead:
`tests/docs/test_development_gated.py` runs each file it names with no flag
set, and checks that the file skips as many tests as the Tests column says, each
for a reason naming its flag. Nothing checks the Runs or Needs columns, beyond
the path each Runs cell starts with.

**Four files skip unless asked for**, because each needs something the
ordinary suite may not depend on. A plain run counts their tests as skipped, the
sum of the Tests column below, and each skip's reason names its flag:

| Flag | Runs | Tests | Needs |
|---|---|---|---|
| `COUNCIL_LIVE_OLLAMA=1` | `tests/council/test_ollama_live.py`: asks a model for real, the default `qwen2.5:7b-instruct` unless `COUNCIL_LIVE_MODEL` names another, so the recordings the council tests use are checked against it and a new model is checked the same way: it answers in the council's shape, quotes the advisory, and gives the same reply from two cold starts | 3 | `ollama serve` with `qwen2.5:7b-instruct` pulled, or the model `COUNCIL_LIVE_MODEL` names (for example `COUNCIL_LIVE_MODEL=gemma4:latest`); it skips, naming the model, when that model is not pulled |
| `DOCS_LIVE_SCAN=1` | `tests/docs/test_readme_live.py`: reruns the README's marked audits and fails on any printed line that drifted | 1 | `fetched/vulnscout`, Syft, Trivy and the advisory database |
| `DOCS_LIVE_SCAN=1` | `tests/docs/test_usage_live.py`: reruns the marked audits in `docs/USAGE.md` the same way | 1 | `fetched/vulnscout`, Syft, Trivy and the advisory database |
| `SYFT_LIVE_SCAN=1` | `tests/deps/test_manifests_live.py`: measures the lock-file table in `docs/USAGE.md` against the real Syft again | 13 | Syft on the path |

All of them at once, as one line:

```bash
COUNCIL_LIVE_OLLAMA=1 DOCS_LIVE_SCAN=1 SYFT_LIVE_SCAN=1 python -m pytest -q
```

The prefix sets the variables for that command alone, so nothing stays
exported. With every flag on and everything each needs in place, nothing
skips. A skip that remains names its cause: Syft is not installed; the docs
check's corpus, a scanner or the database is missing; or the model declined
the one metric a test asks about, which is a result and not a failure. Run as
root, the tests that provoke a permission refusal skip too.

## Working on it

The working rules and agent definitions this project is developed with stay on
the development machine, and the design brief `docs/SCORING_MODEL.md` was read
from is kept outside this repository. `CLAUDE.md`, `.claude/` and
`docs/sources/`, the report's source documents, are in `.gitignore`, so a clone
has none of them. Where any other instruction disagrees with
`docs/SCORING_MODEL.md`, the design document wins.

## Repository layout

```text
.
├── README.md                 the short guide
├── LICENSE                   MIT
├── .gitignore
├── .env.example              the six AUDITOR_* settings, copied to `.env`
├── pytest.ini                src on the path, tests under tests/
├── pyproject.toml            the package, and the `audit` command
├── requirements.txt          pytest; the runtime is standard library
├── answers.example.json      a skeleton answer file, every answer No
├── measurements/             the corpus and council runs behind cited figures
├── docs/
│   ├── USAGE.md              the full guide: every flag, output and setting
│   ├── SETUP.md              prerequisites, the advisory database, the proxy
│   ├── DEVELOPMENT.md        this file
│   ├── SCORING_MODEL.md      the Organisation Risk Score
│   ├── COUNCIL.md            the assessor council
│   └── diagrams.md           every flow, as diagrams
├── src/
│   ├── cli/                  arguments, preflight, the audit order, the council scope, the report files, the exit code
│   ├── council/              the roster, redaction, the providers, the chairman
│   ├── cvss/                 vector parser, metric vocabulary, Base score
│   ├── deps/                 the Syft and Trivy runners, the secrets, the database's build date, unread manifests
│   ├── findings/             the join, and every source's score kept apart
│   ├── organisation/         the answer file, the approval and what needs it, one score per source
│   ├── report/               the record, and the text, JSON and HTML renderings
│   └── scoring/              the approved questions and the risk score engine
└── tests/                    mirrors what it tests: src/ by module, the docs under docs/
```

`fetched/` and `reports/` are ignored: a repository under audit is an argument,
never this project's evidence, and so is what a run writes.
