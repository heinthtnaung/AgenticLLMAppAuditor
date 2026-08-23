"""Which languages the auditor can read, and which file extensions they own.

Two separate ideas live here, and keeping them apart matters:
the LANGUAGE is what goes in the artifact and is part of the contract, while
the GRAMMAR is an internal tree-sitter detail. A .jsx file is JavaScript, but
it needs the TSX grammar to parse its embedded markup.
"""

PYTHON = "python"
JAVASCRIPT = "javascript"
TYPESCRIPT = "typescript"

# The fixed vocabulary of Surface.language. Part of the artifact contract.
LANGUAGES = (PYTHON, JAVASCRIPT, TYPESCRIPT)

# One entry per readable extension. Adding a language starts here.
LANGUAGE_BY_EXTENSION = {
    ".py": PYTHON,
    ".js": JAVASCRIPT,
    ".mjs": JAVASCRIPT,
    ".cjs": JAVASCRIPT,
    ".jsx": JAVASCRIPT,
    ".ts": TYPESCRIPT,
    ".tsx": TYPESCRIPT,
}

# Which tree-sitter grammar parses each extension. Internal, never serialised.
TSX_GRAMMAR = "tsx"
GRAMMAR_BY_EXTENSION = {
    ".js": JAVASCRIPT,
    ".mjs": JAVASCRIPT,
    ".cjs": JAVASCRIPT,
    ".jsx": TSX_GRAMMAR,
    ".ts": TYPESCRIPT,
    ".tsx": TSX_GRAMMAR,
}

SOURCE_EXTENSIONS = tuple(LANGUAGE_BY_EXTENSION)

# Generated or type-only files: real code never lives here, so reading them
# only produces noise. A .d.ts holds declarations with no behaviour at all.
IGNORED_SUFFIXES = (".d.ts", ".min.js", ".bundle.js")


def _extension_of(path: str) -> str:
    """Return the registered extension a path ends with, or '' if none does."""
    if path.endswith(IGNORED_SUFFIXES):
        return ""
    for extension in SOURCE_EXTENSIONS:
        if path.endswith(extension):
            return extension
    return ""


def is_readable(path: str) -> bool:
    """Say whether the auditor has a parser for this file."""
    return _extension_of(path) != ""


def language_of(path: str) -> str:
    """Return the language a file is written in, failing clearly for an unreadable one."""
    extension = _extension_of(path)
    if not extension:
        raise ValueError(f"no language registered for {path!r}; known: {SOURCE_EXTENSIONS}")
    return LANGUAGE_BY_EXTENSION[extension]


def grammar_of(path: str) -> str:
    """Return the tree-sitter grammar that parses a file. Python does not use one."""
    extension = _extension_of(path)
    if extension not in GRAMMAR_BY_EXTENSION:
        raise ValueError(f"no tree-sitter grammar for {path!r}")
    return GRAMMAR_BY_EXTENSION[extension]
