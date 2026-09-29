"""The page's stylesheet and script, read from package data and inlined whole.

They live beside this module under `assets/` and are read through
`importlib.resources`, so an installed copy of the tool finds them the same way a
source checkout does -- `pyproject.toml` ships the folder as package data, and
`tests/test_pyproject.py` holds that list to the files on disk. Read at render
time, not cached at import, so the page always carries exactly what shipped.

**The stylesheet is four files joined in a fixed order** -- tokens, layout,
components, then the narrow-screen and print rules -- because one file outgrew the
size limit; the join is what the page inlines. **Both go inside the page, never as
a link or a src:** a scan runs offline behind a corporate proxy, so a fetched
stylesheet or script is a report that arrives unreadable where it was made.
"""

from importlib.resources import files

ASSET_FOLDER = "assets"
STYLESHEET_FILES = ("tokens.css", "layout.css", "components.css", "media.css")
SCRIPT_FILE = "report.js"


def read_asset(name: str) -> str:
    """Read one packaged asset in full, so the page carries exactly what shipped."""
    return files("report").joinpath(ASSET_FOLDER, name).read_text(encoding="utf-8")


def stylesheet() -> str:
    """Join the stylesheet's files in their fixed order, to be inlined in the one `<style>`."""
    return "\n".join(read_asset(name) for name in STYLESHEET_FILES)


def script() -> str:
    """Give the whole script, to be inlined in the page's one `<script>`."""
    return read_asset(SCRIPT_FILE)
