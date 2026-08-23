# Coding rules

The standard this project is held to. These are **binding**, not preferences:
work that breaks one is not finished.

This is the single place they are written down. `.claude/AGENTS.md` and
`docs/PHASE_1_PLAN.md` both point here rather than restating them, because two
copies of a rule list is how the two copies start disagreeing.

## Why they are strict

This is a Master's degree project. It is graded by people reading it, not just
by whether it runs. Optimise for a supervisor or examiner being able to open
any file and understand it in a minute:

- **Make it simple and easy to understand.** Obvious code beats clever code,
  always. If a reader needs to pause, rewrite it.
- **Every function gets a short, to-the-point comment.** One line saying what
  it does — no essays, no restating the code.
- **Never put all the source code in one file.** Separate concerns clearly:
  loader, data model, detectors, model client, CLI each live in their own
  module.
- **Follow best practice, not shortcuts.**

## The rules

1. **Keep it simple.** Prefer the most obvious solution. If something feels
   complicated, split it into smaller functions rather than writing clever code.
2. **Avoid deep nesting.** Max 2 levels of nested loops/conditionals. Use
   early `return` / `continue` (guard clauses) and helpers to stay flat.
3. **Small functions, one job each.** Aim under 30 lines; readable without
   scrolling.
4. **Clear names.** Descriptive function/variable names (`extract_tool_calls`,
   not `process`). No single-letter names except short loop counters.
5. **Type hints everywhere.** Typed parameters and return types. Use
   `@dataclass` for structured data.
6. **Docstrings.** One-line docstring on every module and public function.
7. **No premature optimisation.** Clear first; optimise only a measured problem.
8. **Fail clearly.** Validate inputs; raise explicit errors with useful
   messages. No silent failures or ambiguous `None` returns.
9. **Pure functions where possible.** Take input, return output, no hidden
   side effects. Keep file I/O at the edges.
10. **Stable JSON output.** Artifacts are JSON with fixed schemas. Do not
    change a schema without updating every reader.
11. **One responsibility per file.** Loader, extractor, model client, etc.
    live in separate modules.
12. **Constants, not magic values.** Named constants for skip-lists, size
    limits, extensions — defined once at the top of a module.
13. **Write a test as you go.** Validate each task against the demo apps in
    `corpus/` before marking it done.
14. **No dead code / no leftover TODOs.** Remove commented-out code before
    completing a task.
15. **Do not widen scope.** Build what the current phase's plan asks for.
    Flag ideas for later phases; do not implement them now.
16. **Written for a reader.** This is a Master's project — every module must
    be understandable on its own by someone seeing it for the first time.
    Simplicity is a requirement, not a preference.
17. **Short, to-the-point comments.** Every function has a one-line docstring
    or comment stating its job. Comment the *why* when it is not obvious;
    never narrate the *what* line by line.
18. **Clear file separation — no god files.** One responsibility per module,
    and no module grows past roughly 200 lines. When a file starts doing two
    jobs, split it before adding more.
19. **Always route work through the project sub-agents.** Every task and every
    test goes through `project-guard` before it is called done. See
    "Mandatory sub-agent use" below. Skipping it is a rule violation.
20. **Keep `docs/TODO.md` current.** It is the project roadmap and the single
    source of truth for progress. Tick the box in the *same* change that
    finishes the work — never leave a finished task unticked, and never tick
    something that is not actually done. If a task turns out to be bigger than
    one line, split the line; do not silently drop it.
