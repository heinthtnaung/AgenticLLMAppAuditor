# How a run works

## One audit, end to end

```mermaid
flowchart TD
    IN["repo: local path or https URL"] --> FETCH
    FETCH{"URL?"} -->|yes| CLONE["fetch_repo<br/>clone --depth 1, pin the commit, drop .git"]
    FETCH -->|no| SCAN
    CLONE --> SCAN["parsing/extractor<br/>find the LLM surfaces"]

    SCAN --> A1[["surfaces.json<br/>aibom.json"]]
    SCAN --> DEPS["deps/inputs<br/>Syft, then map surface to component"]
    DEPS --> A2[["sbom.json<br/>sbom.cyclonedx.json<br/>mapping.json"]]
    DEPS --> TRIVY["deps/trivy_runner<br/>advisories, offline database"]

    TRIVY --> CHECKS["checks/run_checks<br/>plan, then run every check"]
    SCAN --> CHECKS
    CHECKS --> A3[["findings.json<br/>planner.json<br/>findings.sarif.json"]]

    A3 --> ADVISE["remediation_run<br/>advise on each finding, grounded in the knowledge base"]
    ADVISE --> A4[["remediation.json"]]
    A3 --> RENDER["outputs.write_all"]
    A4 --> RENDER
    RENDER --> A5[["report.md<br/>remediation.md"]]

    A5 --> PUB{"URL run?"}
    PUB -->|yes| PUBLISH["pipeline.publish<br/>OpenVEX, then HTML and PDF"]
    PUB -->|no| DONE
    PUBLISH --> DRAFT{"--draft-key?"}
    DRAFT -->|yes| KEY["key_drafting<br/>local model drafts a grading key"]
    DRAFT -->|no| DONE(["done"])
    KEY --> A6[["grading_keys/drafts/&lt;app&gt;.*"]]
    A6 --> DONE
```

A local path stops before `pipeline.publish`: **the audit itself opens no socket
and needs no renderer**. Everything after it is a separate concern, and three of
those stages are commands of their own so you can run them without re-auditing.

## Where a model is called, and where it is not

The question a reader of this project asks first. Four places, and **only two
run by default**:

```mermaid
flowchart LR
    subgraph DEFAULT["every audit"]
        PLAN["planner<br/>picks the check ORDER"]
        ADV["advise<br/>writes remediation prose"]
    end
    subgraph OPTIN["only with a flag"]
        PROBE["semantic_probe<br/>--semantic-probe<br/>judges prompt templates"]
        DRAFTK["key_drafting<br/>--draft-key<br/>drafts ground truth"]
    end
    subgraph NEVER["never a model"]
        T["taint"]
        P["permissions"]
        O["output_handling"]
        AU["auditability"]
        SC["supply_chain"]
        KA["known_advisory"]
    end
```

**The model never decides what counts as a finding.** It may reorder the plan
and narrow which surfaces a check sees, it writes advice, and behind two flags
it judges templates and drafts a key. Every finding in `findings.json` comes
from a check in the right-hand box.

`--draft-key` is the one place a model authors *ground truth* rather than
commentary, which is why it is a flag, why the draft lands where nothing
discovers it, and why every figure such a key produces is qualified.

## The checks

Run inside a bounded LangGraph loop, one check per step, capped at
`MAX_STEPS = 20`.

| Check | Risk | Subject | Model? |
|---|---|---|---|
| `permissions` | LLM06 | tool surfaces | no |
| `taint` | LLM01 | data source → model | no |
| `output_handling` | LLM02 | `execute` calls | no |
| `auditability` | AUDITABILITY | agent constructors | no |
| `supply_chain` | LLM03 | the mapping | no |
| `known_advisory` | LLM03 | the mapping + advisories | no |
| `semantic_probe` | LLM01 | prompt templates | yes, opt-in, at the edge |

A check is named in `coverage.checks_run` only if it had something to look at.
Absent means "could not look", which the scorer reads as
`no_check_for_risk_class` — so absence is a claim, not a detail.

## The planner

Chooses the **order** checks run in, and **which surfaces** each examines. It
never chooses which checks run, and never what counts as a finding.

Five rules stop a narrowing becoming a silent claim: a check the model does not
name examines everything; an empty selection is refused; a narrowing never takes
a check below one surface; surfaces the prompt never described always run; and
the two component-anchored checks are not narrowable at all. What each check
actually examined is in `findings.json`'s `checks_narrowed`.

The model is consulted at the **edge**, in `build_findings` — never inside a
graph node, because `tests/parsing/test_offline.py` asserts the graph *attempts*
no socket, counting attempts rather than successes.

## The commands

Nine entry points. The first audits; the rest each do one thing to what an audit
produced, so none of them is on the audit path.

- `python src/main.py <repo>`: Audit; `--semantic-probe`, `--draft-key`, `--compare-models`
- `python src/evaluate.py`: Score against `grading_keys/`
- `python src/run_baseline.py <system>`: Run a comparison baseline
- `python src/promote_key.py <app>`: Accept a corrected drafted key
- `python src/emit_vex.py <artifacts>`: OpenVEX, via vexctl
- `python src/export_reports.py <dir>`: HTML and PDF
- `python src/index_knowledge.py`: Build the advice knowledge base
- `python src/fetch_repo.py <url>`: Fetch and pin, without auditing
- `python src/model_client.py`: Check the local model answers

`python web/serve.py` is a tenth way in and deliberately not on that list: it is
a wrapper over the first command, not a command of its own, and it lives outside
`src/` because a module there may neither accept a connection nor name the
command that starts it.

## Boundaries

Each is asserted by a test, not just described here.

| Boundary | What holds it |
|---|---|
| **Four modules start a process** — `syft_runner`, `trivy_runner`, `fetch_repo`, the vexctl launcher — and each may start one named program | `test_no_write_commands.py` |
| **Nothing under `src/` accepts a connection** — the HTTP wrapper lives in `web/`, binds loopback, and is started by hand | `test_web_containment.py` (nothing in `src/` imports `web/`), `test_web_framework_containment.py` (no `src/` module imports a server framework), `tests/web/test_server_settings.py` (the bind address, and that no CORS policy exists — it skips without the web extra) |
| **Two modules in `src/` open a connection**, as an exact set: `model_client.py` to local Ollama, and `cloud_client.py` to a hosted model, constructed only under `--compare-models` | `test_offline_containment.py` |
| **An audit attempts no socket** beyond Ollama | `test_offline.py`, counting attempts rather than successes |
| **The audited tree is never written to** | `test_no_mutation.py`, hashing it before and after |
| **The scored trees never read the scorecard** | `test_scorer_boundary.py` |
| **`src/` never imports `experiments/`** | `test_experiments_containment.py` |

The second row used to read "one module". It says two because
`--compare-models` needs a hosted client, and that is a real reduction in what
the tool guarantees — bought deliberately, and narrowed by keeping the import
inside the flag's branch so an ordinary audit never constructs it.
