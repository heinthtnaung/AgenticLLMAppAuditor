"""Reads what the page reads: every `record.field` the JSX binds, as text.

Shared by the two files that sweep those accessors against the real records --
`test_jsx_record_fields.py` for the findings, surfaces and run-record shapes,
and `test_jsx_coverage_fields.py` for the coverage block the advisory section
renders. It was one file until the two jobs together ran past the size a reader
should have to scroll; the sweep lives here so the two cannot drift apart, and
the reasoning about what a sweep proves stays in the files that assert it.

Optional chaining is matched -- `record?.status` and `coverage?.checks_run` are
both written that way -- and so are names in rendered prose, which adds a
candidate to check rather than taking one away.

**Comments are stripped first, and that is a fix rather than a tidy-up.** A
comment in `FindingList.jsx` naming `src/artifacts/finding.py` made this sweep
report `finding.py` as a field no record answers, so the only way to green was
to stop naming that module in a comment -- a rule nobody agreed to, nothing
wrote down, and the next reader would have hit again. `//` lines, `/* */`
blocks and JSX's `{/* */}` go before the pattern runs.

Two things the stripping is careful about, each with a real instance in the
page. String and template literals are kept, so the `//` in
`placeholder="https://github.com/..."` is not read as a comment and cannot eat
the rest of its line; and `://` is never a comment opener at all, because
`AuditForm.jsx` renders a bare `https://` in prose rather than in a literal.

What it still cannot see -- and these are false negatives, so a floor under the
number of accessors found belongs in every file that uses this: a field read
through a variable or after destructuring, a field read in a `.js` module rather
than a `.jsx` one, an accessor written inside a comment, which is now ignored on
purpose, and the rest of any line where a bare `//` opens something that is
neither a comment nor a URL. `docs/TODO.md` carries that last one.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

# Comment openers and the literals that must not be mistaken for one, scanned
# left to right in a single pass so that whichever starts first wins: a `//`
# inside a string is part of the string, and a quote inside a comment opens
# nothing. Only a template literal may span lines -- that is JavaScript's own
# rule, and it is what stops an apostrophe in prose ("the server's own disk")
# from swallowing the rest of the file as a string.
LITERAL_OR_COMMENT = re.compile(
    r"""
      "(?:\\.|[^"\\\n])*"     # a double-quoted string, kept
    | '(?:\\.|[^'\\\n])*'     # a single-quoted string, kept
    | `(?:\\.|[^`\\])*`       # a template literal, kept
    | /\*.*?\*/               # a block comment, JSX's `{/* */}` included
    | (?<!:)//[^\n]*          # a line comment, but never a URL's `://`
    """,
    re.DOTALL | re.VERBOSE,
)

COMMENT_OPENERS = ("//", "/*")


def _without_comment(match: re.Match) -> str:
    """One space for a comment, and a literal handed back exactly as written."""
    token = match.group(0)
    if token.startswith(COMMENT_OPENERS):
        return " "
    return token


def strip_comments(text: str) -> str:
    """The same JSX with its comments gone and every string literal untouched."""
    return LITERAL_OR_COMMENT.sub(_without_comment, text)


def accessors_in(text: str, record: str) -> list[str]:
    """Every field name one file's JSX reads off a record, comments excluded."""
    pattern = re.compile(rf"\b{record}\??\.([A-Za-z_]\w*)")
    return pattern.findall(strip_comments(text))


def accessors(record: str) -> list[tuple[str, str]]:
    """Every `record.field` the JSX reads, paired with the file that reads it."""
    found: list[tuple[str, str]] = []
    for source in sorted(FRONTEND_SRC.rglob("*.jsx")):
        text = source.read_text(encoding="utf-8")
        found += [(source.name, name) for name in accessors_in(text, record)]
    return found


def field_names(record: str) -> set[str]:
    """Just the field names read off one record, without the files that read them."""
    return {name for _, name in accessors(record)}


def unknown(record: str, allowed: set[str], read: list[tuple[str, str]]) -> list[str]:
    """Name every accessor the record cannot answer, file and all, or return nothing."""
    return sorted({f"{where}: {record}.{name}" for where, name in read
                   if name not in allowed})
