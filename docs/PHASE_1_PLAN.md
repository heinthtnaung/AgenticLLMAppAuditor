# Phase 1 — Environment & LLM Surface Extractor

**Goal:** turn a Python LLM-app repository into a structured list of "LLM
surfaces" (prompt templates, agent definitions, tool-call sites, and data
sources feeding prompts/tools), with exact file + line locations.

**Languages:** Python (stdlib `ast`) and JavaScript/TypeScript (tree-sitter).
The design is language-agnostic: `src/languages.py` is where a new one starts.

**Important scope rule:** Phase 1 uses **static analysis only** — no LLM
reasoning, no probes. The model server is set up here so it is ready for
Phase 3, but detection logic in this phase is deterministic code.

---

## Coding rules

Every task below is held to the binding rules in
[`CODING_RULES.md`](./CODING_RULES.md). They are not repeated here: this plan
used to carry its own copy, and the two lists had already drifted to the point
of numbering different rules as 11.

---

## Task 1.1 — Project scaffolding

Set up the repository structure and tooling.

**Do:**
- Create folders: `src/`, `corpus/`, `tests/`, `artifacts/`.
- Add `requirements.txt` and a `README.md`.
- Add a `.gitignore` that excludes: `.venv/`, `__pycache__/`, `*.pyc`,
  model weight files (`*.gguf`, `*.bin`, `*.safetensors`), and `artifacts/`.
- Place the two vulnerable demo apps under `corpus/`.

**Done when:** the repo is `git init`'d, `pip install -r requirements.txt`
runs cleanly, and the demo apps are present under `corpus/`.

---

## Task 1.2 — Offline model client (set up, not used yet)

Install a local model server and write a thin client wrapper.

**Do:**
- Install Ollama and pull the primary model (`qwen2.5-coder:7b-instruct`).
- Write `src/model_client.py` with one function: `ask(prompt: str) -> str`
  that calls the local server and returns the text.
- Keep it small — no retry logic or streaming yet.

**Done when:** a smoke-test script calls `ask("say hello")` and prints a
response, with no internet connection required.

**Rule reminder:** this file has one job (talk to the local model). Do not
add extraction logic here.

---

## Task 1.3 — Repo loader

Walk a local repo and return the Python files worth analysing.

**Do:**
- Write `src/repo_loader.py`.
- Define constants at the top: `SKIP_DIRS` (`.venv`, `__pycache__`,
  `node_modules`, `.git`), `MAX_FILE_BYTES`.
- Function `list_source_files(repo_path: str) -> list[Path]` that returns
  `.py` files, skipping the skip-dirs and oversized files.
- Use guard clauses (`continue`) instead of nested `if`s.

**Done when:** run on `corpus/vuln-app-1-support-agent` it returns exactly
the app's Python files (and none from skip-dirs).

---

## Task 1.4 — Surface data model

Define the structured output shape before writing the extractor.

**Do:**
- Write `src/surface.py`.
- A `@dataclass Surface`. Its fields are defined once in
  [`SCHEMAS.md`](./SCHEMAS.md) — do not restate them here, or the two
  documents will disagree.
- `kind` is one of a fixed set of constants:
  `PROMPT_TEMPLATE`, `AGENT_DEF`, `TOOL_CALL`, `DATA_SOURCE`.
- A function `surfaces_to_json(surfaces: list[Surface]) -> str`.

**Done when:** a `Surface` can be created and serialised to stable JSON.

---

## Task 1.5 — LLM surface extractor (core of Phase 1)

Static analysis using Python's `ast` module to find the four surface kinds.
Build it as **four small, separate detector functions**, one per surface
kind — do not write one big function.

**Do — write `src/extractor.py` with:**
- `find_prompt_templates(tree, file) -> list[Surface]`
  Detect `ChatPromptTemplate`, prompt strings, and f-strings that feed a
  model call.
- `find_agent_defs(tree, file) -> list[Surface]`
  Detect agent constructors (e.g. `create_react_agent`).
- `find_tool_calls(tree, file) -> list[Surface]`
  Detect `@tool`-decorated functions and tool definitions.
- `find_data_sources(tree, file) -> list[Surface]`
  Detect file reads, retrieval calls, and request inputs that flow toward
  prompts or tools.
- `extract_file(path: Path) -> list[Surface]`
  Parse one file with `ast.parse` and run the four detectors.
- `extract_repo(repo_path: str) -> list[Surface]`
  Loop over files from the loader, call `extract_file`, collect results.

**Rules for this task specifically:**
- Each detector walks the AST with `ast.walk` (flat), not manual recursion.
- One detector = one surface kind. Keep them independent.
- Record the real `line` number from the AST node (`node.lineno`).

**Done when:** `extract_repo` on both demo apps produces a `surfaces.json`
whose entries correspond to the surfaces referenced in each app's
`ground_truth.json` (`llm_surface` field). No real surface is missed.

---

## Task 1.6 — Command-line entry point

A simple CLI so the extractor is runnable and produces an artifact.

**Do:**
- Write `src/main.py` that takes a repo path argument, runs `extract_repo`,
  and writes `artifacts/<app-name>/surfaces.json`.
- Use `argparse`. Keep it to a few lines.

**Done when:** `python src/main.py corpus/vuln-app-1-support-agent` writes a
valid `surfaces.json`.

---

## Task 1.7 — Validation against the demo apps

Confirm the extractor is correct before Phase 1 is closed.

**Do:**
- Write `tests/test_extractor.py` that runs `extract_repo` on each demo app
  and asserts every expected surface kind is found at the expected file.
- Cross-check the output by hand against both `ground_truth.json` files.

**Done when:** the tests pass and a manual review confirms no real surface on
the two demo apps is missed.

---

## Task 1.8 — Language registry

Make the choice of language explicit and data-driven, so adding one is an
edit in a single place.

**Do:**
- Write `src/languages.py` holding two separate tables: extension to
  **language** (the artifact vocabulary: `python`, `javascript`,
  `typescript`), and extension to **tree-sitter grammar** (internal).
  They differ: `.jsx` is JavaScript but needs the TSX grammar.
- Add `IGNORED_SUFFIXES` for files with no behaviour to audit
  (`.d.ts`, `.min.js`, `.bundle.js`).
- Add a required `language` field to `Surface`, and bump `SCHEMA_VERSION`.

**Done when:** `language_of` and `grammar_of` disagree for `.jsx`, both raise
for an unregistered extension, and every emitted surface carries a language.

---

## Task 1.9 — JavaScript and TypeScript backend

**Do:**
- Split parsing per language: `src/extractor_python.py` (`ast`) and
  `src/extractor_js.py` (tree-sitter). `src/extractor.py` keeps only the
  dispatch and the repository walk.
- Write `src/ts_utils.py` and `src/detectors_js.py` — the same four surface
  kinds, the same name-table approach as the Python side.
- tree-sitter never raises on bad syntax, so `parse_source` must check
  `root_node.has_error` and raise, naming the file.

**Done when:** `extract_repo` on a mixed repository returns surfaces from both
languages, each carrying the right `language` and `module`, and a malformed
`.ts` file fails loudly rather than yielding nothing.

---

## Task 1.10 — A clean-code fixture

**Do:**
- Add `corpus/oss-app-langgraphjs-starter`, pinned in
  `corpus/evidence/<app>.manifest.json`.
- Record its surfaces in `corpus/evidence/<app>.ground_truth.json` as
  `expected_surfaces`, with
  `findings: []`. It has no planted vulnerabilities: that is the point, it is
  what lets the evaluation report a false-positive rate.

**Done when:** the extractor finds exactly the recorded surfaces and no others,
and the app's zero findings read as "asserted clean" rather than "nothing
found". See [`SCHEMAS.md`](./SCHEMAS.md).

---

## Not in Phase 1 — auditing a repository by URL

Downloading a repository from a URL and auditing it was built and then
**removed**, deliberately. Phase 1 is offline static analysis over one pinned
fixture, and fetching brought in an untrusted input with the safety work that
implies: URL allow-listing, path-traversal guards on the derived directory
name, symlink handling, non-interactive git. All of that is real, and none of
it belongs in the phase that establishes the extractor.

It returns in Phase 3 or 4, when the evaluation actually needs more than one
app. See `docs/TODO.md`.

---

## Phase 1 exit checklist

- [x] Repo scaffolded, installs cleanly, demo apps under `corpus/`.
- [x] Offline model client returns a response (ready for Phase 3).
      Verified: `python src/model_client.py` answers from the local server.
- [x] Repo loader returns correct file lists.
- [x] `Surface` data model + stable JSON serialisation.
- [x] Four independent detectors implemented.
- [x] `surfaces.json` produced for both demo apps.
- [~] All surfaces in `ground_truth.json` are found; none missed.
      Every one is matched by a test, but the ground truth itself is AI-drafted
      and awaiting human sign-off (`TODO.md` B3).
- [x] Tests pass; code follows the coding rules above.
- [x] Language registry, and a JavaScript/TypeScript backend (tasks 1.8-1.10).

The finished flow is walked through step by step in [`FLOW.md`](./FLOW.md).

**Artifacts produced this phase:** `artifacts/<app>/surfaces.json`
(consumed by Phase 2 mapping and Phase 3 auditing). Its schema, and the
`ground_truth.json` input schema, are documented in [`SCHEMAS.md`](./SCHEMAS.md).

---

## Notes / honest cautions

- `ast`-based detection is pattern-based; it will find the surfaces it is
  told to look for. Expanding to new frameworks later means adding detectors,
  not rewriting.
- Keep the surface schema stable — Phase 2 and Phase 3 depend on it.
- Do **not** add probing or LLM detection here. That is Phase 3. Finishing
  Phase 1 cleanly is more valuable than starting Phase 3 early.
