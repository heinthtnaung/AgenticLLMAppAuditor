"""The pages the docs checks read, and what each one is expected to carry.

Every page is described once, here: where it is, how many `run` blocks it marks,
and how many fences of this tool's output it leaves unmarked. **The counts are
per page**, because a marker lost from one page is not made up for by a block
added to another, and a count summed across pages would let exactly that pass.

A page that marks no run may carry no marker at all, and finding none there is
its normal state. On a page that marks runs, finding none is a loss.
"""

from dataclasses import dataclass, replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_FOLDER = PROJECT_ROOT / "docs"


@dataclass(frozen=True)
class Document:
    """One page, and what the checks expect to find on it."""

    path: Path
    run_blocks: int
    # Fences of this tool's output with no marker above them, which no live
    # check reruns. A new one wants a marker, not a raised count.
    unmarked_tool_output: int

    @property
    def carries_markers(self) -> bool:
        """Say whether the page marks runs, so that finding no marker on it is a loss."""
        return self.run_blocks > 0


@dataclass(frozen=True)
class Page:
    """One page's text, as published or as a test damaged it, and the document it is."""

    document: Document
    text: str


README = Document(PROJECT_ROOT / "README.md", run_blocks=2, unmarked_tool_output=0)
# The one unmarked output is the council's progress: a council run's stderr,
# which needs Ollama, so no marker can rerun it.
USAGE = Document(DOCS_FOLDER / "USAGE.md", run_blocks=1, unmarked_tool_output=1)
SETUP = Document(DOCS_FOLDER / "SETUP.md", run_blocks=0, unmarked_tool_output=0)
DEVELOPMENT = Document(DOCS_FOLDER / "DEVELOPMENT.md", run_blocks=0, unmarked_tool_output=0)


def read(document: Document) -> Page:
    """Give one page as the project publishes it."""
    return Page(document, document.path.read_text(encoding="utf-8"))


def rewritten(page: Page, text: str) -> Page:
    """Give the same page carrying other text, as a test's damage leaves it."""
    return replace(page, text=text)
