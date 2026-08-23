"""extract_repo must dispatch to both language backends over one mixed repository."""

from conftest import CORPUS_DIR
from extractor import extract_repo
from languages import PYTHON, TYPESCRIPT
from surface import PROMPT_TEMPLATE, surfaces_to_json

PYTHON_SOURCE = 'system_prompt = "You are a helpful support assistant."\n'

TYPESCRIPT_SOURCE = 'const systemPrompt = `You are a helpful support assistant.`;\n'

# The TypeScript fixture, used to prove a JS-only repository still yields surfaces.
LANGGRAPH_JS_APP = "oss-app-langgraphjs-starter"


def make_mixed_repo(root) -> str:
    """Create a repository holding one Python module and one TypeScript module."""
    (root / "agent.py").write_text(PYTHON_SOURCE, encoding="utf-8")
    (root / "agent.ts").write_text(TYPESCRIPT_SOURCE, encoding="utf-8")
    return str(root)


def test_mixed_repo_yields_surfaces_from_both_languages(tmp_path) -> None:
    """A repository with Python and TypeScript reports surfaces from both backends."""
    surfaces = extract_repo(make_mixed_repo(tmp_path))
    assert {surface.language for surface in surfaces} == {PYTHON, TYPESCRIPT}


def test_mixed_repo_names_the_surface_from_each_file(tmp_path) -> None:
    """Each file contributes its own prompt surface, at the right file and line."""
    surfaces = extract_repo(make_mixed_repo(tmp_path))
    found = sorted((s.file, s.line, s.name, s.kind) for s in surfaces)
    assert found == [
        ("agent.py", 1, "system_prompt", PROMPT_TEMPLATE),
        ("agent.ts", 1, "systemPrompt", PROMPT_TEMPLATE),
    ]


def test_mixed_repo_serialises_identically_across_runs(tmp_path) -> None:
    """Two runs over the same mixed repository produce byte-identical JSON."""
    repo = make_mixed_repo(tmp_path)
    assert surfaces_to_json(extract_repo(repo)) == surfaces_to_json(extract_repo(repo))