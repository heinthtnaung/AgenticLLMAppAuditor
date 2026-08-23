# System flow

How the auditor works today, step by step. Everything on this page is
**implemented and tested** unless it is marked *planned*.

One sentence version: point it at a repository, and it walks every
source file's syntax tree looking for the four places an LLM touches the
application, then writes what it found to a JSON file.

---

## 1. The whole picture

```mermaid
flowchart TD
    U([You run:<br/>python src/main.py corpus/my-app]) --> M[main.py<br/>read the arguments]
    M --> X[extractor.py<br/>read each file]
    X --> L[repo_loader.py<br/>which files are worth reading?]
    L --> X
    X --> D[detectors.py<br/>find the four surface kinds]
    D --> S[surface.py<br/>tidy up and serialise]
    S --> A[(artifacts/my-app/<br/>surfaces.json)]

    GT[(corpus/evidence/<br/>my-app.ground_truth.json<br/>the known answers)] -.->|tests compare| A

    style U fill:#e8f0fe,stroke:#4285f4
    style A fill:#e6f4ea,stroke:#34a853
    style GT fill:#fef7e0,stroke:#f9ab00
```

The dotted line is the part that makes this a research tool rather than just a
script: the answers are known in advance, so the output can be **scored**.

---

## 2. Step by step

### Step 1 — Read the arguments (`main.py`)

```sh
python src/main.py corpus/vuln-app-1-support-agent
```

`build_parser()` takes the repository path, plus an optional `--artifacts-dir`.
The path is the only required input, and the tool makes no network call at any
point: nothing leaves the machine.

The audited app's source is not committed to this repository — it is a
third-party project, downloaded once with the command in the README and
pinned to the commit its grading key was written against.

### Step 2 — Decide which files to read (`repo_loader.py`)

`list_source_files()` walks the repository and keeps every `.py` file, except:

| Skipped | Why | Constant |
|---|---|---|
| `.git`, `.venv`, `__pycache__`, `node_modules`, … | not the app's own code | `SKIP_DIRS` |
| files over 1 MB | generated or vendored, not hand-written | `MAX_FILE_BYTES` |
| `*.d.ts`, `*.min.js`, `*.bundle.js` | declarations and bundles: no behaviour to audit | `IGNORED_SUFFIXES` |

`list_source_files()` itself stays pure and just returns the list; `main.py`
asks `list_oversized_files()` separately and **reports the skips on stderr**,
so nothing is dropped silently — a missed file could be a missed vulnerability.

A path that does not exist raises immediately, naming the path.

### Step 3 — Turn each file into a syntax tree (`extractor.py`)

The auditor reads more than one language, so this is where it picks a parser.
`languages.py` maps the file extension to a language, and `extractor.py`
dispatches:

| Language | Parser | Why |
|---|---|---|
| Python | the standard library's `ast` | it resolves imports properly, which a tree-sitter query cannot do without reimplementing module semantics |
| JavaScript, TypeScript | tree-sitter | the standard library has no JavaScript parser |

Two backends is a deliberate choice, and it has an honest cost: two name
tables (`detector_names.py` and `detector_names_js.py`) that can drift apart.
What keeps the seam invisible is that both produce the same `Surface` type, so
nothing downstream knows or cares which parser ran.

One trap worth naming: `.jsx` is *JavaScript* the language but needs
tree-sitter's *TSX* grammar to parse its embedded markup. `languages.py` keeps
those two ideas in separate tables for exactly that reason.

`extract_repo()` loops the file list and calls `extract_file()` on each.
On the Python side, `parse_file()` reads the source with `tokenize.open`
(which honours a file's own encoding declaration) and hands it to `ast.parse`.
On the JavaScript side, `parse_source()` has to check `root_node.has_error`
itself and raise: tree-sitter never raises on bad syntax, it just returns a
tree full of ERROR nodes, so an unchecked malformed file would silently yield
zero surfaces.

Each file is labelled with its path **relative to the repository root**, in
POSIX form. That is what makes the output identical on Windows, WSL, and Linux.

### Step 4 — Run the four detectors (`detectors.py`, `detectors_js.py`)

This is the heart of Phase 1. Four independent detectors, one per surface kind.
Each one walks the tree flatly with `ast.walk` and never calls the others:

```mermaid
flowchart LR
    T[syntax tree<br/>of one file] --> P[find_prompt_templates]
    T --> A[find_agent_defs]
    T --> C[find_tool_calls]
    T --> S[find_data_sources]

    P --> R1["PROMPT_TEMPLATE<br/>what the app tells the model"]
    A --> R2["AGENT_DEF<br/>the agent, chain, or model client"]
    C --> R3["TOOL_CALL<br/>what the model can do"]
    S --> R4["DATA_SOURCE<br/>where outside data enters"]
```

| Detector | Looks for | Example it catches |
|---|---|---|
| `find_prompt_templates` | prompt classes, and text assigned to a prompt-shaped name — literals, f-strings, `.format()`, concatenation | `system_msg = """Assistant helps…"""` at `main.py:21` |
| `find_agent_defs` | agent and chain factories, and model clients | `AgentExecutor.from_agent_and_tools(...)` at `main.py:71` |
| `find_tool_calls` | `@tool` functions, `Tool(...)` constructors, tool subclasses | `Tool(name='GetUserTransactions')` at `tools.py:40` |
| `find_data_sources` | file reads, HTTP calls, database queries, retrieval, web route handlers | `st.chat_input(...)` at `main.py:60` |

The names each detector recognises live in **`detector_names.py`** (Python) and
**`detector_names_js.py`** (JavaScript/TypeScript), as plain constants.
Supporting a new framework means adding a name to a set there, not rewriting a
detector.

Every detector also builds a small import table for the file
(`ast_utils.build_import_table`) so each finding records which package it came
from — `langchain_experimental.sql`, for example. Phase 2 uses that to join a
surface to an SBOM component.

**What Phase 1 deliberately does not do:** it records *where* untrusted data
enters, but not whether that data reaches a prompt or a tool. Following the
flow is taint analysis, and that is a Phase 3 probe.

### Step 5 — Tidy up and write the file (`surface.py` → `main.py`)

`surfaces_to_json()` deduplicates, sorts by `(file, line, kind, name)`, and
serialises. Two runs on the same repository produce **byte-identical** output.

Each record gets an `id` built from its own content, `file:line:kind:name`, so
later phases can point at a surface without repeating four fields.

`main.py` writes the result to `artifacts/<app>/surfaces.json`. A repository
with no surfaces is a valid answer, not an error: the file is still written
with `surface_count: 0`, so "audited, found nothing" is distinguishable from
"never audited".

---

## 3. How it is checked

```mermaid
flowchart LR
    C[corpus/my-app/<br/>the app being audited] --> E[extract_repo]
    E --> F[surfaces found]
    G[corpus/my-app/<br/>ground_truth.json] --> M{does every known<br/>finding match a<br/>surface we found?}
    F --> M
    M -->|yes| OK([pass])
    M -->|no| BAD([fail, naming the finding id])

    style OK fill:#e6f4ea,stroke:#34a853
    style BAD fill:#fce8e6,stroke:#ea4335
```

A finding matches when the file and the surface kind are equal and the line is
within 3 of the recorded range. Exact line equality would be wrong, because a
detector may report a decorator line where a human noted the `def`.

Failures name the finding, not just the assertion:

```
AssertionError: VULN2-03: no AGENT_DEF surface extracted for
.../llm_shell_chain.py lines 27-42 (ground truth line 30, name 'PALChain')
```

---

## 4. Settings and the model client

Two pieces exist but sit outside the extraction flow above.

**`config.py`** resolves settings in this order, so nothing machine-specific is
written into the source:

```mermaid
flowchart LR
    E[environment variable] -->|wins over| D[.env file]
    D -->|wins over| B[built-in default]
```

**`model_client.py`** sends a prompt to the local Ollama server and returns the
text. It is fully working — `python src/model_client.py` answers — but **no
detection logic uses it yet**. Phase 1 is deterministic static analysis; the
model is set up here so Phase 3 can start immediately.

---

## 5. Where the later phases attach

Phase 2 is built. `python src/main.py <repo>` produces `sbom.json`,
`aibom.json` and `mapping.json` beside the surfaces, joining each surface to
the dependency it came from on the `module` field. Phases 3 and 4 are not
built.

```mermaid
flowchart TD
    P1[Phase 1<br/>surface extractor] --> SJ[(surfaces.json)]
    SJ --> P2[Phase 2<br/>SBOM / AIBOM + mapping]
    P2 --> MJ[(sbom.json, aibom.json,<br/>mapping.json)]
    SJ --> P3[Phase 3<br/>agentic auditor + probes]
    MJ --> P3
    P3 --> FJ[(findings.json)]
    FJ --> P4[Phase 4<br/>scoring vs ground truth]
    GT[(ground_truth.json)] --> P4
    P4 --> RES([precision / recall / F1])

    style P1 fill:#e6f4ea,stroke:#34a853
    style SJ fill:#e6f4ea,stroke:#34a853
```

Each phase reads the previous phase's JSON, which is why those files are
treated as contracts. The field lists are in [`SCHEMAS.md`](./SCHEMAS.md).

---

## 6. Module map

`src/` groups modules by what they do. The folders are plain directories, not
packages — Python imports them without an `__init__.py`, so there are no empty
files to explain.

| Folder | What it holds |
|---|---|
| `parsing/` | turning a repository's source files into syntax trees |
| `detectors/` | finding the four kinds of LLM surface in a tree |
| `artifacts/` | the JSON documents each run produces, and their shapes |
| `deps/` | reading an app's dependencies, and matching imports to packages |

| File | Its one job |
|---|---|
| `main.py` | command line entry point |
| `languages.py` | which extension is which language, and which grammar reads it |
| `corpus_paths.py` | where the corpus keeps code, and where it keeps evidence |
| `repo_loader.py` | which files to analyse |
| `extractor.py` | pick the backend for a file, and walk a repository |
| `extractor_python.py` | parse Python with `ast`, run the Python detectors |
| `extractor_js.py` | parse JS/TS with tree-sitter, run the JS detectors |
| `detectors.py` | the four detectors, Python |
| `detectors_js.py` | the four detectors, JavaScript and TypeScript |
| `detector_names.py` | the framework names, Python |
| `detector_names_js.py` | the framework names, JavaScript and TypeScript |
| `ast_utils.py` | shared `ast` helpers |
| `ts_utils.py` | shared tree-sitter helpers |
| `surface.py` | the data model and stable JSON output |
| `config.py` | settings, from the environment |
| `model_client.py` | talk to the local model (Phase 3) |
| `syft_runner.py` | run the SBOM generator: the only outside process |
| `requirements_parser.py` | what the app says it depends on |
| `sbom.py` | normalise that into a deterministic bill of materials |
| `component_match.py` | which package an import came from |
| `mapping.py` | join each surface to its component, or say why not |
| `aibom.py` | the models, tools and agents, from the surfaces |

Every module stays under the project's 200-line cap, so none of them grows
into a file that does two jobs.

Call direction is one-way:

```
main -> extractor -> extractor_python -> detectors    -> surface
                  \-> extractor_js     -> detectors_js -^
```

so any file can be read on its own without chasing a cycle. The two backends
meet only at `Surface`: nothing downstream knows which parser ran.
