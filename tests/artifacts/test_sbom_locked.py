"""Where `locked` comes from: a lockfile was read, and nothing else.

The provenance is the whole point of the vocabulary. `locked` and `pinned` may
reach a purl; `inferred` may not, because a guessed version in an advisory
lookup claims a vulnerability the app may not have. So the predicate must be
"the caller read a lockfile" -- not "the ecosystem is npm", which would leave a
Python app shipping a poetry.lock mislabelled, and not "the generator reported
something", which would relabel every guess as a fact.

`version_source_of` takes that judgement as a boolean; `build_sbom` makes it,
per component, from the generator's record of which file it read the component
out of. test_sbom_lockfile_evidence.py owns the second half.
"""

from artifacts.sbom import (
    INFERRED,
    LOCKED,
    PINNED,
    UNCONSTRAINED,
    UNKNOWN,
    build_sbom,
    version_source_of,
)
from dependency_fixtures import (
    GENERATOR_NAME,
    GENERATOR_VERSION,
    JS_NOT_IN_THE_LOCKFILE,
    NPM_MANIFEST,
    POETRY_LOCK,
    PYPI_MANIFEST,
    YARN_LOCK,
    located_in,
    pypi_sbom,
    js_sbom,
)
from deps.package_names import NPM, PYPI

# The two lockfile names and the two manifest names come from the modules that
# own their spelling, imported above: the rule under test is about which file
# was read, not which ecosystem read it.

# The recorded PyPI SBOM, component by component. Recorded before `locked`
# existed and unchanged by it: if the predicate ever widened, `langchain`'s
# guessed 0.3.25 would turn up here as `locked` with a versioned purl.
PYPI_COMPONENTS = [
    ("langchain", "0.3.25", INFERRED, "pkg:pypi/langchain"),
    ("langchain-community", None, UNCONSTRAINED, "pkg:pypi/langchain-community"),
    ("langchain-litellm", "0.2.0", PINNED, "pkg:pypi/langchain-litellm@0.2.0"),
    ("openai", "1.78.0", INFERRED, "pkg:pypi/openai"),
    ("streamlit", None, UNCONSTRAINED, "pkg:pypi/streamlit"),
]

# The version the schema went to when `locked` joined the vocabulary.
EXPECTED_SCHEMA_VERSION = 3


def generator_component(version: str, location: str | None) -> dict:
    """One library component as the generator reports it, with its location if it has one."""
    component = {"type": "library", "name": "widget", "version": version}
    if location:
        component["properties"] = located_in(location)
    return component


def build_widget(constraint: str, version: str | None, manifests: list[str],
                 ecosystem: str = PYPI, location: str | None = None) -> dict:
    """Build the SBOM component for one declared package, for a given set of manifests.

    `location` is the file the generator says it read the component from. It is
    what earns `locked`; `manifests` only says which files the scan saw.
    """
    components = [generator_component(version, location)] if version is not None else []
    document = build_sbom({"components": components}, {"widget": constraint},
                          GENERATOR_NAME, GENERATOR_VERSION, manifests,
                          version_guessing_enabled=True, ecosystem=ecosystem)
    return document["components"][0]


def test_a_lockfile_and_a_version_make_the_version_locked() -> None:
    """The two facts `locked` asserts: a lockfile was read and it resolved a version."""
    assert version_source_of("^1.2.3", "1.2.3", NPM, from_lockfile=True) == LOCKED


def test_the_same_version_without_a_lockfile_is_only_inferred() -> None:
    """Drop the lockfile and the identical version becomes a guess again."""
    assert version_source_of("^1.2.3", "1.2.3", NPM, from_lockfile=False) == INFERRED


def test_a_generator_reporting_a_version_does_not_make_it_locked() -> None:
    """`locked` is not "the generator said something"; that is exactly `inferred`.

    This is the one substitution that would corrupt the Python app: every
    version Syft guesses for an unpinned requirement would become a fact.
    """
    assert version_source_of("~=0.3.25", "0.3.25", PYPI) == INFERRED


def test_a_lockfile_that_resolved_nothing_leaves_the_version_unknown() -> None:
    """A declared package absent from the lockfile has a range and no version."""
    assert version_source_of("^5.5.4", None, NPM, from_lockfile=True) == UNKNOWN


def test_a_lockfile_beats_an_empty_constraint() -> None:
    """An unconstrained package that the lockfile resolved is locked, not unconstrained.

    Order matters: the empty-constraint test comes after the lockfile test, or a
    real resolved version would be thrown away as "nothing was declared".
    """
    assert version_source_of("", "1.2.3", NPM, from_lockfile=True) == LOCKED


def test_an_exact_pin_beats_a_lockfile() -> None:
    """The manifest pinning a version is checked first, so `pinned` still wins."""
    assert version_source_of("==1.2.3", "1.2.3", PYPI, from_lockfile=True) == PINNED


def test_a_lockfile_with_no_version_at_all_stays_unconstrained() -> None:
    """No constraint and no resolved version leaves nothing for `locked` to assert."""
    assert version_source_of("", None, PYPI, from_lockfile=True) == UNCONSTRAINED


def test_a_version_read_out_of_a_poetry_lock_is_locked() -> None:
    """Synthetic, and the point of the whole test: the rule is not "npm".

    No fixture pairs a requirements.txt with a poetry.lock, so if `locked` were
    keyed on the ecosystem nothing in these fixtures would catch it.
    """
    component = build_widget("~=1.2.0", "1.2.3", [PYPI_MANIFEST, POETRY_LOCK],
                             location=f"/{POETRY_LOCK}")
    assert component["version_source"] == LOCKED
    assert component["purl"] == "pkg:pypi/widget@1.2.3"


def test_the_same_python_app_without_the_lockfile_reaches_no_purl_version() -> None:
    """Remove poetry.lock and the identical range and version give a bare purl."""
    component = build_widget("~=1.2.0", "1.2.3", [PYPI_MANIFEST])
    assert component["version_source"] == INFERRED
    assert component["purl"] == "pkg:pypi/widget"


def test_an_npm_app_without_a_lockfile_gets_no_locked_version() -> None:
    """The mirror image: npm alone does not earn `locked` either."""
    component = build_widget("^1.2.3", "1.2.3", [NPM_MANIFEST], NPM)
    assert component["version_source"] == INFERRED
    assert component["purl"] == "pkg:npm/widget"


def test_a_version_read_out_of_a_yarn_lock_is_a_fact() -> None:
    """The generator read this one from the lockfile, so the purl may state it."""
    component = build_widget("^1.2.3", "1.2.3", [NPM_MANIFEST, YARN_LOCK], NPM,
                             location=f"/{YARN_LOCK}")
    assert component["version_source"] == LOCKED
    assert component["purl"] == "pkg:npm/widget@1.2.3"


def test_the_recorded_npm_app_locks_every_version_its_lockfile_resolved() -> None:
    """yarn.lock was read, so each resolved component states its version in its purl."""
    locked = [c for c in js_sbom()["components"] if c["version_source"] == LOCKED]
    assert len(locked) == 8, "the recorded sample holds eight resolved components"
    for component in locked:
        assert component["purl"].endswith(f"@{component['version']}"), component["name"]


def test_a_js_package_missing_from_the_lockfile_is_unknown_not_locked() -> None:
    """typescript is declared and absent from yarn.lock, so no version was locked."""
    components = {c["name"]: c for c in js_sbom()["components"]}
    for name in JS_NOT_IN_THE_LOCKFILE:
        assert components[name]["version_source"] == UNKNOWN, name
        assert components[name]["version"] is None, name


def test_the_recorded_pypi_sbom_states_the_new_schema_version() -> None:
    """The version tracks what a reader may conclude: `locked` took it to 2, and a
    bare declaration keeping its resolved version took it to 3."""
    assert pypi_sbom()["schema_version"] == EXPECTED_SCHEMA_VERSION


def test_the_recorded_pypi_sbom_is_otherwise_exactly_what_it_was() -> None:
    """Component for component, the Python app did not move when npm arrived.

    Recorded as whole tuples rather than a count, so a component silently
    turning `locked` -- and gaining a version in its purl -- fails here.
    """
    built = [(c["name"], c["version"], c["version_source"], c["purl"])
             for c in pypi_sbom()["components"]]
    assert built == PYPI_COMPONENTS


def test_no_recorded_pypi_component_is_locked() -> None:
    """Said directly, so the reason the tuples above must not change is on the record."""
    sources = [c["version_source"] for c in pypi_sbom()["components"]]
    assert LOCKED not in sources
