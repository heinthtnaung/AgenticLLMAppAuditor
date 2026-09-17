"""A comment may name a module; the accessor sweep has to look past it.

`jsx_sweep.py` matches `finding.x` as text, and a comment in `FindingList.jsx`
naming `src/artifacts/finding.py` was therefore reported as
`FindingList.jsx: finding.py` -- a field no record answers. The sweep was right
that no `Finding` has a `py`, and wrong about what it had read. The only way to
green was to stop naming that module in a comment, which is a rule nobody
agreed to and nothing wrote down, so the sweep strips comments first now.

**Both halves are asserted, and the second is the one that matters.** Ignoring
comments is easy to do too well: a stripper that swallowed a line too many, or
ran to the end of the file on an unclosed token, would hide real accessors and
every sweep above it would pass having read less than it claims. So each test
that plants an accessor in a comment plants a real one straight after it and
requires that one back.

Every input here is written in the test. The one exception is the last pair,
which reads the page's own files -- because the regression was a comment in a
file that is still there, and a fix that only works on invented text is not the
fix. Nothing is skipped: this is `re` over strings.
"""

from .jsx_sweep import FRONTEND_SRC, accessors, accessors_in, strip_comments

# The record prefix every case below is written against, and the field a real
# accessor reads. `Finding` carries `title`; nothing carries `py`.
RECORD = "finding"
REAL_FIELD = "title"
FIELD_FROM_A_FILENAME = "py"

# The module the comment names, which is what made a filename look like a field.
NAMED_MODULE = "src/artifacts/finding.py"

# What a URL in a string literal must not do: `//` inside it is not a comment,
# so the accessor after it on the same line is still code. Two spellings,
# because only the second needs the literal to be recognised as a literal -- a
# scheme's `://` is refused as a comment opener wherever it appears, and a
# protocol-relative URL has no scheme in front of the slashes.
URL_IN_A_LITERAL = 'placeholder="https://github.com/owner/app.git"'
PROTOCOL_RELATIVE_IN_A_LITERAL = 'src="//cdn.example.invalid/logo.svg"'

# The same trap outside a literal: `AuditForm.jsx` renders a bare `https://` in
# its own prose, where nothing quotes it.
URL_IN_PROSE = "An https:// link is fetched and pinned at its current commit."

# A real read of the record, spelled as the components spell one.
REAL_READ = f"<td>{{{RECORD}.{REAL_FIELD}}}</td>"


def swept(text: str) -> list[str]:
    """The field names the sweep finds in one piece of JSX."""
    return accessors_in(text, RECORD)


# --- an accessor inside a comment is not read ---------------------------------

def test_a_module_named_in_a_line_comment_is_not_read_as_a_field() -> None:
    """The regression, in one line: `finding.py` is a filename and not a field."""
    assert swept(f"// The keys live beside the record in {NAMED_MODULE}\n") == []


def test_a_module_named_in_a_block_comment_is_not_read_as_a_field() -> None:
    """The same name in the other comment syntax, which docstrings above a function use."""
    assert swept(f"/** Read off {NAMED_MODULE}, across the language boundary. */\n") == []


def test_a_module_named_in_a_jsx_comment_is_not_read_as_a_field() -> None:
    """JSX's third syntax: braces around a block comment, inside rendered markup."""
    assert swept(f"<p>{{/* {NAMED_MODULE} owns the vocabulary */}}</p>\n") == []


def test_a_comment_spanning_lines_is_not_read_as_a_field() -> None:
    """A block comment is the one comment that runs past its own line."""
    text = f"/* {NAMED_MODULE}\n   holds the record this reads. */\n"
    assert swept(text) == []


# --- and a real accessor beside one still is ----------------------------------

def test_the_accessor_on_the_line_after_a_comment_is_still_read() -> None:
    """The half that keeps the fix honest: a stripper may not eat the next line."""
    text = f"// See {NAMED_MODULE} for the record.\n{REAL_READ}\n"
    assert swept(text) == [REAL_FIELD]


def test_the_accessor_after_a_block_comment_on_one_line_is_still_read() -> None:
    """`/* */` closes where it says it closes, so the code beside it is code."""
    assert swept(f"/* {NAMED_MODULE} */ {REAL_READ}\n") == [REAL_FIELD]


def test_the_accessor_after_a_comment_ends_is_still_read_across_lines() -> None:
    """A multi-line comment closes too; everything under it is still swept."""
    text = f"/* {NAMED_MODULE}\n   is where this comes from. */\n{REAL_READ}\n"
    assert swept(text) == [REAL_FIELD]


def test_both_a_commented_and_a_real_accessor_leave_only_the_real_one() -> None:
    """The two halves in one input, which is how the page actually reads."""
    text = f"// {RECORD}.{FIELD_FROM_A_FILENAME} named in prose\n{REAL_READ}\n"
    assert swept(text) == [REAL_FIELD]


# --- a `//` that is not a comment ---------------------------------------------

def test_a_url_in_a_string_literal_does_not_eat_the_rest_of_its_line() -> None:
    """`//` inside a literal is two slashes in a string, whether a scheme precedes it."""
    text = f"<input {URL_IN_A_LITERAL} {PROTOCOL_RELATIVE_IN_A_LITERAL} /> {REAL_READ}\n"
    assert swept(text) == [REAL_FIELD]


def test_a_url_in_rendered_prose_does_not_eat_the_rest_of_its_line() -> None:
    """The page writes one unquoted: a scheme's `://` is never a comment."""
    assert swept(f"<p>{URL_IN_PROSE} {REAL_READ}</p>\n") == [REAL_FIELD]


def test_an_apostrophe_in_prose_does_not_swallow_the_code_after_it() -> None:
    """`the server's own disk` is on the page; a string cannot span lines, so it stops."""
    text = f"<p>it resolves against the server's own disk</p>\n{REAL_READ}\n"
    assert swept(text) == [REAL_FIELD]


def test_an_accessor_inside_a_template_literal_is_still_read() -> None:
    """Literals are kept rather than dropped: the page builds `file:line` in one."""
    assert swept("const where = `${finding.file}:${finding.line}`;\n") == ["file", "line"]


# --- the stripper leaves the code it was handed -------------------------------

def test_stripping_keeps_the_declaration_the_comment_sat_above() -> None:
    """Read once as text: what goes is the comment, and what stays is a declaration."""
    text = f"// {NAMED_MODULE}\nconst RISK_TONE = {{}};\n"
    assert NAMED_MODULE not in strip_comments(text)
    assert "const RISK_TONE = {};" in strip_comments(text)


def test_nothing_is_stripped_from_a_file_with_no_comments() -> None:
    """Non-vacuity on the stripper itself: it is not simply returning less than it got."""
    assert strip_comments(REAL_READ) == REAL_READ


# --- over the page's own files ------------------------------------------------

def components_naming(module: str) -> list[str]:
    """Which components mention one module path anywhere in their text."""
    return [source.name for source in sorted(FRONTEND_SRC.rglob("*.jsx"))
            if module in source.read_text(encoding="utf-8")]


def test_the_page_may_name_the_module_its_vocabulary_comes_from() -> None:
    """The comment that failed is back in `FindingList.jsx`, and the sweep passes it now."""
    assert components_naming(NAMED_MODULE), (
        f"no component names {NAMED_MODULE}, so the regression has no subject here")
    assert FIELD_FROM_A_FILENAME not in {name for _, name in accessors(RECORD)}


def test_the_real_files_still_yield_the_fields_the_components_read() -> None:
    """The other half over the real tree: stripping did not cost the sweep its subject."""
    assert REAL_FIELD in {name for _, name in accessors(RECORD)}
