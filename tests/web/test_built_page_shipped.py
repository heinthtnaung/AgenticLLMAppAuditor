"""The committed `frontend/dist/` is there, complete, and built from the source beside it.

This is the one file in the suite that reads a real directory instead of
writing one into `tmp_path`, and it is allowed to because the directory is
*this project's own build output* -- not audited code, and not a fixture that
was removed. "Clone, pip install, run" rests entirely on that output being
committed and current, and until now nothing but the README said so.

**Freshness is not asserted by mtime, on purpose.** `git clone` does not
preserve modification times: every file is written at checkout time, in
checkout order, and `frontend/dist/` sorts before `frontend/src/`. So "no
source file is newer than `dist/index.html`" is false on a clean clone about as
often as it is true, and a guard that fails on a fresh checkout is a guard
people delete. The join used instead is content: every static `className="..."`
literal in the JSX must appear verbatim in the bundle the page loads. Those are
string literals, which esbuild carries through minification unchanged, so
editing a component's markup without running `npm run build` fails here and
surviving a clone does not.

What that does not catch is an edit that changes no class name -- reworded
prose, a changed handler. Nor does it catch a class name *removed* from the
JSX: the sweep runs one way, source to bundle, so every name still in the
source is looked for in the bundle and a stale bundle keeps names the source
has dropped. It is a floor under the hazard, not a proof of a rebuild.

The `/assets` mount is driven here too, over the real bundle:
`test_page_route.py` points the route at a tree it writes and says in its own
docstring that the mount is left untested. This is where it is tested.

The whole file skips without the server packages: `web/page.py` owns the
paths asserted below and imports fastapi to do it.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the mount")

from fastapi.testclient import TestClient    # noqa: E402

import api                                   # noqa: E402
import page                                  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

# Where `page.py` serves assets from, as a URL rather than a path.
ASSETS_PREFIX = "/assets/"

# Every local file the built page pulls in, and the one it executes.
REFERENCE_PATTERN = re.compile(r'(?:src|href)="(/[^"]+)"')
SCRIPT_PATTERN = re.compile(r'<script[^>]+src="(/[^"]+)"')

# A static class attribute, which is a plain string literal in the built bundle.
# The braced form -- `className={`tag tag--${tone}`}` -- is skipped: it is
# assembled at runtime and never appears whole in the output.
CLASS_NAME_PATTERN = re.compile(r'className="([^"{}]+)"')

# Floors, so a sweep that read nothing cannot pass as a sweep that found no
# fault. Vite emits one script and one stylesheet for this app; the class names
# were 60 when this was written, and the floor is set well under that so an
# ordinary edit does not have to move it.
EXPECTED_ASSET_REFERENCES = 2
MINIMUM_CLASS_NAMES = 40

OK = 200


def index_html() -> str:
    """The built page itself, which names everything else the browser fetches."""
    return page.INDEX.read_text(encoding="utf-8")


def referenced_paths() -> list[str]:
    """Every root-relative file the built page references, assets and otherwise."""
    return REFERENCE_PATTERN.findall(index_html())


def referenced_assets() -> list[str]:
    """Just the references the `/assets` mount is responsible for."""
    return [path for path in referenced_paths() if path.startswith(ASSETS_PREFIX)]


def script_path() -> Path:
    """The built bundle the page executes, on disk, or say plainly that it is not there."""
    found = SCRIPT_PATTERN.findall(index_html())
    assert len(found) == 1, f"expected one script in the built page, got {found}"
    built = page.DIST / found[0].lstrip("/")
    assert built.is_file(), f"index.html loads {found[0]}, which is not under {page.DIST}"
    return built


def class_names_in_source() -> list[tuple[Path, str]]:
    """Every static class attribute in the JSX, paired with the file it came from."""
    found: list[tuple[Path, str]] = []
    for source in sorted(FRONTEND_SRC.rglob("*.jsx")):
        text = source.read_text(encoding="utf-8")
        found += [(source, name) for name in CLASS_NAME_PATTERN.findall(text)]
    return found


# --- the build is there and complete ------------------------------------------

def test_the_built_page_is_committed() -> None:
    """Without this file there is no page at all, and `serve.py` answers 503."""
    assert page.INDEX.is_file(), f"{page.INDEX} is missing; run `npm run build` in frontend/"


def test_every_asset_the_page_loads_was_built() -> None:
    """A reference with no file behind it is a blank screen, and the server says 200 to it."""
    for reference in referenced_assets():
        built = page.ASSETS / reference[len(ASSETS_PREFIX):]
        assert built.is_file(), f"index.html loads {reference}, absent from {page.ASSETS}"


def test_every_other_file_the_page_references_was_built() -> None:
    """The favicon is served by the catch-all rather than the mount, and must be there too."""
    for reference in referenced_paths():
        assert (page.DIST / reference.lstrip("/")).is_file(), reference


def test_the_page_really_references_a_bundle_and_a_stylesheet() -> None:
    """Non-vacuity: an index.html referencing nothing would pass both sweeps above."""
    assert len(referenced_assets()) >= EXPECTED_ASSET_REFERENCES


# --- the mount that serves them -----------------------------------------------

def test_the_assets_mount_serves_the_built_bundle() -> None:
    """The mount `register` adds, over the real build `test_page_route.py` cannot reach."""
    reference = f"{ASSETS_PREFIX}{script_path().name}"
    response = TestClient(api.app).get(reference)
    assert response.status_code == OK
    assert response.content == script_path().read_bytes()


# --- the build matches the source it was built from ---------------------------

def test_every_class_name_in_the_source_is_in_the_built_bundle() -> None:
    """A component edited without `npm run build` ships a page that does not match its source."""
    bundle = script_path().read_text(encoding="utf-8")
    stale = [(source.name, name) for source, name in class_names_in_source()
             if name not in bundle]
    assert stale == [], f"not in {script_path().name}; rebuild frontend/: {stale}"


def test_the_freshness_sweep_read_a_real_set_of_class_names() -> None:
    """Guard: a regex that matched nothing would make the test above pass over an empty list."""
    assert len(class_names_in_source()) >= MINIMUM_CLASS_NAMES
