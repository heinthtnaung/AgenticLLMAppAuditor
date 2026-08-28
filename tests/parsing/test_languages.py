"""The language registry: which files the auditor can read, and which parser each needs."""

import pytest
from parsing.languages import (
    JAVASCRIPT,
    LANGUAGE_BY_EXTENSION,
    LANGUAGES,
    PYTHON,
    SOURCE_EXTENSIONS,
    TSX_GRAMMAR,
    TYPESCRIPT,
    grammar_of,
    is_readable,
    language_of,
)


def test_python_file_is_python() -> None:
    """A .py file reports the language the standard-library backend handles."""
    assert language_of("src/main.py") == PYTHON


def test_jsx_is_javascript_by_language() -> None:
    """A .jsx file is JavaScript: that is what lands in the artifact."""
    assert language_of("src/App.jsx") == JAVASCRIPT


def test_jsx_uses_the_tsx_grammar() -> None:
    """A .jsx file still needs the TSX grammar, because of its embedded markup."""
    assert grammar_of("src/App.jsx") == TSX_GRAMMAR


def test_tsx_is_typescript_by_language() -> None:
    """A .tsx file is TypeScript, not a language of its own."""
    assert language_of("src/App.tsx") == TYPESCRIPT


def test_tsx_uses_the_tsx_grammar() -> None:
    """A .tsx file is parsed by the TSX grammar."""
    assert grammar_of("src/App.tsx") == TSX_GRAMMAR


def test_language_and_grammar_disagree_for_jsx() -> None:
    """Language and grammar are separate ideas, and .jsx is the case that proves it."""
    assert language_of("src/App.jsx") != grammar_of("src/App.jsx")


def test_ts_uses_the_typescript_grammar() -> None:
    """A plain .ts file is parsed by the TypeScript grammar, not the TSX one."""
    assert grammar_of("src/agent.ts") == TYPESCRIPT


def test_every_registered_language_is_declared() -> None:
    """No extension may map to a language outside the declared vocabulary."""
    assert set(LANGUAGE_BY_EXTENSION.values()) <= set(LANGUAGES)


def test_source_extensions_are_the_registered_ones() -> None:
    """SOURCE_EXTENSIONS is derived from the registry, so the two cannot drift."""
    assert set(SOURCE_EXTENSIONS) == set(LANGUAGE_BY_EXTENSION)


@pytest.mark.parametrize("path", ["README.md", "notes.txt", "Makefile", "style.css"])
def test_unregistered_extension_has_no_language(path: str) -> None:
    """A file the auditor cannot parse fails loudly instead of guessing a language."""
    with pytest.raises(ValueError, match="no language registered"):
        language_of(path)


def test_unregistered_extension_has_no_grammar() -> None:
    """Asking for a grammar the auditor does not have fails loudly."""
    with pytest.raises(ValueError, match="no tree-sitter grammar"):
        grammar_of("README.md")


def test_python_has_no_tree_sitter_grammar() -> None:
    """Python is parsed by the standard library, so it has no grammar entry."""
    with pytest.raises(ValueError, match="no tree-sitter grammar"):
        grammar_of("src/main.py")


@pytest.mark.parametrize("path", ["src/main.py", "src/agent.ts", "src/App.jsx", "src/index.mjs"])
def test_readable_source_files(path: str) -> None:
    """Every extension in the registry is reported as readable."""
    assert is_readable(path)


def test_declaration_file_is_not_readable() -> None:
    """A .d.ts holds type declarations with no behaviour, so it is never analysed."""
    assert not is_readable("src/types.d.ts")


def test_minified_file_is_not_readable() -> None:
    """A .min.js is generated output, so it is never analysed."""
    assert not is_readable("static/app.min.js")


def test_bundled_file_is_not_readable() -> None:
    """A .bundle.js is generated output, so it is never analysed."""
    assert not is_readable("static/app.bundle.js")


def test_unreadable_file_has_no_language() -> None:
    """An ignored suffix is unreadable, so asking for its language fails loudly."""
    with pytest.raises(ValueError, match="no language registered"):
        language_of("src/types.d.ts")
