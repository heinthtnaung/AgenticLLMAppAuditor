"""Which palette the page shows, and the one thing that may write it down.

`theme.js` had a single `applyTheme(theme)` that stamped `data-theme` *and*
wrote `localStorage`, and `ThemeToggle`'s mount effect called it. So **merely
loading the page stored an explicit `light` or `dark`**: after one visit
`storedTheme()` never answered `system` again, a machine whose preference later
changed stopped being followed, and two comments claiming `system` stays the
default were false in a way that changed behaviour. It is split now --
`showTheme` sets the attribute and writes nothing, `rememberTheme` writes
storage and is called from the click handler alone -- and the pair of tests
under "the split" is that fix's regression. Neither half proves anything alone:
a `showTheme` that did nothing would also write no storage, so the attribute it
stamps is asserted beside the storage it does not.

**It runs the page's own code.** `theme.js` has no imports, so the module lifts
whole into a `.mjs` and node evaluates it under three stubs -- `localStorage`,
`document.documentElement` and `window.matchMedia` -- that record what was asked
of them instead of doing it. Nothing here reads a browser, so what the page does
with a *real* storage or a real media query is still unproven; what is proven is
the resolution and the writing, which is where the defect was.

The storage key is lifted from the module rather than written here, so a rename
follows instead of quietly making every read miss.

Skipped when node is absent, as the vexctl and PDF-font tests skip. Needs no
fastapi, no network and no rebuilt bundle: it reads `frontend/src/theme.js` and
`ThemeToggle.jsx`, not `dist/`.
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from .jsx_sweep import strip_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
THEME = FRONTEND_SRC / "theme.js"
TOGGLE = FRONTEND_SRC / "components" / "ThemeToggle.jsx"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The three states, spelled as the module spells them.
SYSTEM = "system"
LIGHT = "light"
DARK = "dark"

# What a chosen theme stamps on the root element, and what a machine is asked.
DATA_THEME = "data-theme"
COLOUR_SCHEME_QUERY = "prefers-color-scheme"

# A value no palette has ever been called, to drive the fallback.
THEME_THAT_DOES_NOT_EXIST = "wobble"

# The module's own storage key, and the two calls the component makes.
STORED_UNDER = re.compile(r'const STORED_UNDER = "([^"]*)";')
MOUNT_EFFECT = re.compile(r"useEffect\(\(\) => \{(.*?)\}, \[", re.DOTALL)
CLICK_HANDLER = re.compile(r"onClick=\{\(\) => \{(.*?)\}\}", re.DOTALL)

# Stubs for the three browser globals the module touches, each recording what
# was asked of it. `world` carries the browser being imitated: what storage
# holds, whether it is barred at all, and whether the machine asks for light
# (`null` for a webview with no `matchMedia` to ask).
STUBS = """
const world = JSON.parse(process.argv[2]);
const kept = {};
if (world.stored !== null) kept[world.key] = world.stored;
const writes = [];
const asked = [];
globalThis.localStorage = {
  getItem: (key) => {
    if (world.storageBarred) throw new Error("storage is blocked here");
    return key in kept ? kept[key] : null;
  },
  setItem: (key, value) => {
    if (world.storageBarred) throw new Error("storage is blocked here");
    writes.push([key, value]);
  },
};
const attributes = {};
globalThis.document = { documentElement: {
  setAttribute: (name, value) => { attributes[name] = value; },
  removeAttribute: (name) => { delete attributes[name]; },
} };
globalThis.window = world.prefersLight === null ? {} : {
  matchMedia: (query) => {
    asked.push(query);
    return { matches: world.prefersLight && query.includes("light") };
  },
};
"""


@dataclass(frozen=True)
class Shown:
    """What one call to the module answered, and everything it did on the way."""

    answer: str
    writes: list[list[str]]
    attributes: dict[str, str]
    asked: list[str]


def storage_key() -> str:
    """The key the module remembers a choice under, read out of the module."""
    found = STORED_UNDER.search(THEME.read_text(encoding="utf-8"))
    assert found, f"{THEME.name} declares no STORED_UNDER this test can lift"
    return found.group(1)


def probe(expression: str, tmp_path: Path, stored: str | None = None,
          prefers_light: bool | None = None, storage_barred: bool = False) -> Shown:
    """Evaluate one expression against the real module under stubbed browser globals."""
    script = tmp_path / "theme_probe.mjs"
    script.write_text(STUBS + THEME.read_text(encoding="utf-8")
                      + f"\nconst answer = {expression};\n"
                      "console.log(JSON.stringify({ answer, writes, attributes, asked }));\n",
                      encoding="utf-8")
    world = {"key": storage_key(), "stored": stored,
             "prefersLight": prefers_light, "storageBarred": storage_barred}
    done = subprocess.run([NODE, str(script), json.dumps(world)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused {expression}:\n{done.stderr}"
    return Shown(**json.loads(done.stdout))


# --- what is remembered -------------------------------------------------------

def test_the_stored_default_is_system(tmp_path) -> None:
    """A visitor who has never touched the toggle has chosen nothing."""
    assert probe("storedTheme()", tmp_path).answer == SYSTEM


def test_a_remembered_choice_is_read_back(tmp_path) -> None:
    """Non-vacuity: storage the module never reads would answer `system` to everything."""
    assert probe("storedTheme()", tmp_path, stored=LIGHT).answer == LIGHT


def test_an_unknown_stored_value_falls_back_to_system(tmp_path) -> None:
    """A key from an older build, or a hand-edited one, is not a palette to show."""
    assert probe("storedTheme()", tmp_path,
                 stored=THEME_THAT_DOES_NOT_EXIST).answer == SYSTEM


def test_storage_the_browser_bars_reads_as_system(tmp_path) -> None:
    """A private window throws rather than answering null, which is why there is a catch."""
    assert probe("storedTheme()", tmp_path, stored=LIGHT,
                 storage_barred=True).answer == SYSTEM


# --- what `system` resolves to ------------------------------------------------

def test_system_resolves_to_dark_when_the_page_cannot_ask(tmp_path) -> None:
    """Some embedded webviews have no `matchMedia`; `tokens.css` is dark on bare `:root`."""
    assert probe("effectiveTheme()", tmp_path, prefers_light=None).answer == DARK


def test_system_resolves_to_light_when_the_machine_asks_for_light(tmp_path) -> None:
    """The first visit follows the machine, which is what the stored default is for."""
    assert probe("effectiveTheme()", tmp_path, prefers_light=True).answer == LIGHT


def test_system_resolves_to_dark_when_the_machine_does_not_ask_for_light(tmp_path) -> None:
    """A machine that answers the query with `false` gets the dark-first palette."""
    assert probe("effectiveTheme()", tmp_path, prefers_light=False).answer == DARK


def test_resolving_system_asks_the_machine_about_the_colour_scheme(tmp_path) -> None:
    """Non-vacuity: a function returning `dark` blindly would satisfy two tests above."""
    asked = probe("effectiveTheme()", tmp_path, prefers_light=True).asked
    assert [query for query in asked if COLOUR_SCHEME_QUERY in query] == asked
    assert asked != []


def test_an_explicit_choice_is_not_resolved_against_the_machine(tmp_path) -> None:
    """Choosing dark on a machine asking for light is a choice, not a conflict."""
    shown = probe("effectiveTheme()", tmp_path, stored=DARK, prefers_light=True)
    assert shown.answer == DARK
    assert shown.asked == []


# --- the split, which is the regression ---------------------------------------

def test_showing_a_theme_writes_no_storage(tmp_path) -> None:
    """The bug: loading the page turned the `system` default into a stored choice."""
    assert probe(f'showTheme("{LIGHT}")', tmp_path).writes == []


def test_showing_a_theme_stamps_the_attribute(tmp_path) -> None:
    """What makes the test above mean something: showing still shows."""
    assert probe(f'showTheme("{LIGHT}")', tmp_path).attributes == {DATA_THEME: LIGHT}


def test_showing_system_stamps_no_attribute(tmp_path) -> None:
    """`system` sets nothing at all, so `prefers-color-scheme` in the stylesheet decides."""
    assert probe(f'showTheme("{SYSTEM}")', tmp_path).attributes == {}


def test_choosing_a_theme_writes_it_to_storage(tmp_path) -> None:
    """The other half of the split: a choice is the one thing that is remembered."""
    assert probe(f'rememberTheme("{DARK}")', tmp_path).writes == [[storage_key(), DARK]]


def test_choosing_a_theme_stamps_no_attribute(tmp_path) -> None:
    """Remembering does not render: the component's state change is what shows it."""
    assert probe(f'rememberTheme("{DARK}")', tmp_path).attributes == {}


def test_an_unknown_theme_is_never_stored_as_itself(tmp_path) -> None:
    """Both halves validate, so a bad value cannot be written for a later visit to read."""
    writes = probe(f'rememberTheme("{THEME_THAT_DOES_NOT_EXIST}")', tmp_path).writes
    assert writes == [[storage_key(), SYSTEM]]


# --- and the caller that made it a bug ----------------------------------------

def test_the_mount_effect_only_shows_a_theme() -> None:
    """Where the defect actually lived: the effect that runs on every render and mount."""
    found = MOUNT_EFFECT.search(strip_comments(TOGGLE.read_text(encoding="utf-8")))
    assert found, f"{TOGGLE.name} no longer has an effect this test can read"
    assert "showTheme" in found.group(1)
    assert "rememberTheme" not in found.group(1), "a render is not a choice"


def test_choosing_is_remembered_in_the_click_handler() -> None:
    """And the split is only safe if the remaining caller is the one a person drives."""
    found = CLICK_HANDLER.search(strip_comments(TOGGLE.read_text(encoding="utf-8")))
    assert found, f"{TOGGLE.name} no longer has a click handler this test can read"
    assert "rememberTheme" in found.group(1)
