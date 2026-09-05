"""`reproduce.sh`'s hardcoded constants, held to what the repository ships.

The script is the examiner's single entry point -- `./reproduce.sh` regenerates
every figure in `docs/REPORT.md` -- and it clones the app itself, so `APP`,
`PIN` and `URL` are a second copy of provenance whose first copy is
`grading_keys/<app>.manifest.json`. Nothing reconciles the two: move the key's
pin and the script keeps cloning the old commit, then publishes figures
measured against a tree the key does not describe. The `--system` names it
passes to `src/evaluate.py` are a third such copy, of `SCORED_SYSTEMS`.

Only files this repository owns are read: the script, and the manifest beside
the key. The audited app is not on disk and is not needed.
"""

import re

from conftest import REPO_ROOT
from evaluate import build_parser
from evaluation.document import AGENTIC_AUDITOR, SCORED_SYSTEMS
from grading_keys import MANIFEST_SUFFIX
from shipped_key_fixtures import SHIPPED_APPS, read

SCRIPT_PATH = REPO_ROOT / "reproduce.sh"

# A top-level `NAME="value"` assignment, and a `${NAME}` reference inside one.
ASSIGNMENT = re.compile(r'^\s*([A-Z_]+)="([^"]*)"\s*$', re.MULTILINE)
REFERENCE = re.compile(r"\$\{(\w+)\}")

# `python src/evaluate.py --system <name>`, the third copy of `SCORED_SYSTEMS`.
SYSTEM_ARGUMENT = re.compile(r"--system\s+(\S+)")

# The constants asserted below, each of which the script assigns exactly once.
# `COMPARISON` is assigned twice, which is why "once" is checked rather than
# assumed: a second assignment would make the value read here the wrong one.
PINNED_NAMES = ("APP", "PIN", "URL")

# The clone and checkout the constants exist for. Asserted verbatim, because
# constants that agree with the manifest buy nothing if the commands stopped
# reading them -- a hardcoded URL or a `checkout main` leaves every assertion
# below true and the script cloning something else.
CLONE_COMMAND = 'git clone --quiet "$URL" "$TREE"'
CHECKOUT_COMMAND = 'checkout --quiet "$PIN"'


def script_text() -> str:
    """The reproduction script's source, read from the repository root."""
    return SCRIPT_PATH.read_text(encoding="utf-8")


def assignments() -> dict[str, str]:
    """Every `NAME="value"` in the script, with any `${NAME}` reference resolved."""
    literal = dict(ASSIGNMENT.findall(script_text()))
    # Subscripted, not `.get`: an unassigned `${NAME}` must name itself in a
    # KeyError rather than resolve to "" and surface as a confusing URL diff.
    return {name: REFERENCE.sub(lambda match: literal[match.group(1)], value)
            for name, value in literal.items()}


def assignment_counts() -> dict[str, int]:
    """How many times the script assigns each name, so one value can be trusted."""
    counts: dict[str, int] = {}
    for name, _ in ASSIGNMENT.findall(script_text()):
        counts[name] = counts.get(name, 0) + 1
    return counts


def script_manifest() -> dict:
    """The provenance manifest of the app the script names."""
    return read(assignments()["APP"], MANIFEST_SUFFIX)


# --- There is a script, and it says what this test reads ---------------------

def test_the_reproduction_script_ships_at_the_repository_root() -> None:
    """The guard: with the script gone, every parse below would read an empty string."""
    assert SCRIPT_PATH.is_file()


def test_every_pinned_constant_is_assigned_exactly_once() -> None:
    """A second assignment would silently override the value the rest of this file checks."""
    counts = assignment_counts()
    assert [counts.get(name) for name in PINNED_NAMES] == [1] * len(PINNED_NAMES)


# --- The constants agree with the shipped key --------------------------------

def test_the_script_audits_an_app_this_repository_ships_a_key_for() -> None:
    """`evaluate.py` scores by artifact directory name, so an unknown app scores nothing."""
    assert assignments()["APP"] in SHIPPED_APPS


def test_the_script_clones_the_commit_the_grading_key_was_read_at() -> None:
    """A drifted pin publishes figures measured against a tree the key does not describe."""
    assert assignments()["PIN"] == script_manifest()["upstream_commit"]


def test_the_script_clones_the_repository_the_manifest_names() -> None:
    """The script builds the URL from `${APP}`; the manifest is where it is recorded."""
    assert assignments()["URL"] == script_manifest()["upstream_url"]


def test_the_script_clones_the_repository_the_url_constant_names() -> None:
    """A hardcoded URL here would leave every constant above correct and unused."""
    assert CLONE_COMMAND in script_text()


def test_the_script_checks_out_the_pin_constant() -> None:
    """`checkout main` would leave the pin correct and the tree at whatever HEAD is."""
    assert CHECKOUT_COMMAND in script_text()


# --- The systems it scores ---------------------------------------------------

def test_the_no_flag_run_scores_the_auditor_itself() -> None:
    """The script's first `evaluate.py` carries no `--system`, so the default is a third name."""
    assert build_parser().parse_args([]).system == AGENTIC_AUDITOR


def test_the_script_scores_every_system_the_report_compares() -> None:
    """Each of the three: two by flag, the auditor by default. A dropped run publishes no figure.

    An unknown name would also abort the run -- `build_evaluation` raises on
    one -- so equality covers both directions at once.
    """
    scored = set(SYSTEM_ARGUMENT.findall(script_text())) | {AGENTIC_AUDITOR}
    assert scored == set(SCORED_SYSTEMS)
