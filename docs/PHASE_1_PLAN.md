# Phase 1 — Environment & LLM Surface Extractor

**Goal:** turn a Python LLM-app repository into a structured list of "LLM
surfaces" (prompt templates, agent definitions, tool-call sites, and data
sources feeding prompts/tools), with exact file + line locations.

**Language:** Python only.

**Important scope rule:** Phase 1 uses **static analysis only** — no LLM
reasoning, no probes. The model server is set up here so it is ready for
Phase 3, but detection logic in this phase is deterministic code.

---

## Coding rules (apply to every task below)

These are binding for all Phase 1 code.

1. **Keep it simple.** Prefer the most obvious solution. If a task feels
   complicated, split it into smaller functions rather than writing clever code.
2. **Avoid deep nesting.** No more than 2 levels of nested loops or
   conditionals. Use early `return`/`continue` (guard clauses) and helper
   functions to keep code flat.
3. **Small functions, one job each.** A function should do one thing and be
   short enough to read without scrolling (aim < 30 lines).
4. **Clear names.** Descriptive names for functions and variables
   (`extract_tool_calls`, not `etc` or `process`). No single-letter names
   except short loop counters.
5. **Type hints everywhere.** Every function has typed parameters and return
   type. Use `dataclass` for structured data.
6. **Docstrings.** Every module and public function has a one-line docstring
   saying what it does.
7. **No premature optimisation.** Write clear code first. Only optimise if a
   measured problem exists.
8. **Fail clearly.** Validate inputs; raise explicit errors with useful
   messages instead of failing silently or returning `None` ambiguously.
9. **Pure functions where possible.** Prefer functions that take input and
   return output without hidden side effects. Keep file I/O at the edges.
10. **Stable JSON output.** All artifacts are JSON with a fixed schema.
    Do not change a schema without updating everything that reads it.
11. **Standard library first.** Use the Python standard library (especially
    `ast`, `pathlib`, `json`) before reaching for third-party packages.
12. **One responsibility per file.** Keep each module focused (loader,
    extractor, model client, etc. live in separate files).
13. **Constants, not magic values.** Named constants for skip-lists, size
    limits, and file extensions — defined once at the top of a module.
14. **Write a test as you go.** Each task has a check against the demo apps
    before it is considered done.
15. **No dead code / no TODO left behind.** Remove commented-out code before
    marking a task complete.

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
- Function `list_python_files(repo_path: str) -> list[Path]` that returns
  `.py` files, skipping the skip-dirs and oversized files.
- Use guard clauses (`continue`) instead of nested `if`s.

**Done when:** run on `corpus/vuln-app-1-support-agent` it returns exactly
the app's Python files (and none from skip-dirs).

---

## Task 1.4 — Surface data model

Define the structured output shape before writing the extractor.

**Do:**
- Write `src/surface.py`.
- A `@dataclass Surface` with fields: `kind` (str), `name` (str),
  `file` (str), `line` (int), `detail` (str).
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
- [x] Tests pass (167; 166 without a local model server); code follows the coding rules above.

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
