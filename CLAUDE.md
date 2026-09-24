# Rules

Binding. Work that breaks one is not done.

## Code

1. **Simple beats clever.** If a reader has to pause, rewrite it.
2. **No nested loops.** One level. Use a helper, a comprehension, or an early
   `continue`. Two levels needs a reason in a comment; three is never allowed.
3. **Small functions, one job.** Under 30 lines. Under 200 lines per file.
4. **Flat, not deep.** Guard clauses and early returns instead of `else`.
5. **Clear names.** `extract_tool_calls`, not `process`. No single letters
   except a short loop counter.
6. **Type hints everywhere.** `@dataclass` for structured data.
7. **One-line docstring on every function.** Say what it does. Comment *why*
   when it is not obvious; never narrate the code.
8. **Fail loudly.** Validate input, raise with a useful message. No silent
   failure, no ambiguous `None`.
9. **Named constants, not magic values.** Defined once at the top of the file.
10. **No dead code.** Remove it; git remembers.

## Layout

11. **Group related files in a folder.** One responsibility per folder, one per
    file. When a folder starts doing two jobs, split it.
12. **Tests mirror what they test.** Code mirrors the source tree,
    `src/thing/x.py` → `tests/thing/test_x.py`. A document mirrors the document
    tree, `README.md` → `tests/docs/test_readme_*.py`.
13. **Never put everything in one file.**

## Commits

14. **Short messages.** One line saying what changed. A second line only if the
    *why* is not obvious. **No long paragraphs, no essays.**
15. **Small commits.** One change each. If the subject line needs an "and",
    it is two commits.
16. **Imperative mood.** "Add the CVSS parser", not "Added" or "Adding".

## Working

17. **Always route work through the project agents.** Every task goes to the
    agent that owns it. Doing it yourself instead is a rule violation, not a
    shortcut.

    | Work | Agent |
    |---|---|
    | Python, parsers, CLI, scoring engine | `python-developer` |
    | prompts, model clients, measuring a model | `ai-engineer` |
    | components, styling, the build | `frontend-developer` |
    | tests, failures, reproducing a bug | `tester` |
    | README, `docs/*.md`, design records | `technical-writer` |
    | reviewing finished work | `judge` |

    Two exceptions, and only two: an agent already running a task does not
    re-delegate it, and a single lookup — reading one file, answering from what
    is already known — is not a task. If you are editing a file, it is a task.

    **If no agent owns the work, write one.** Add an `.md` to
    `.claude/agents/`, commit it, then use it. Never reach for a
    general-purpose agent: it does the job once and everything it learned is
    gone, so the next person starts from nothing. An agent file is where the
    project keeps what it knows.

    **One live agent per type, and send the next task to it.** A second
    `python-developer` starts cold; a message to the one already running resumes
    it with the conventions it set and the files it has read. Three runs for
    three consecutive steps means learning the same conventions three times.
    Spawn another of a type only for work that is genuinely parallel, and name a
    run after its type — `python-developer`, not `council-rewrite`.

18. **The judge sees it before the commit.** Every change, no exceptions.
19. **Keep `docs/diagrams.md` true.** After any change to how the system works —
    a new component, a changed flow, a deleted one — update the diagrams in the
    same change. It is the one page somebody reads to understand the system, so
    a stale diagram is worse than none: it is confidently wrong. If a change
    touches no flow, say so rather than skipping in silence.
20. **A test lands with its change.** No test, not done.
21. **Run the tests before saying it works.** Report real output.
22. **Do not widen scope.** Build what was asked. Flag the rest.
23. **Say what you did not do**, and why.
24. **State a limitation as an assertion, not a sentence.** A gap accepted on
    purpose gets a test asserting it, so closing the gap turns it red. A comment
    or docstring says what the code does, not what it was meant to do.

## This machine

A corporate HTTP proxy is set. Before running anything that talks to a local
service:

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
```

Without it, `urllib` sends loopback requests to the proxy, which answers 502.
Fetching from the internet (`git clone`, `trivy image --download-db-only`) needs
the proxy **on**. The two go in opposite directions.
