"""An artifact missing a field the scorer reads is refused at the edge, not inside it.

`KeyError` is not one of `evaluate.py`'s expected failures, so a field the
scorer subscripts and the artifact lacks leaves the CLI as a traceback rather
than a message. `_check_artifact` converts that into a sentence naming the file.

What this file holds is the refusal behaviour, in both of its directions: that
every listed field is really written by the real producer, so the list cannot
refuse a genuine artifact, and that a document short of any one field is
refused by name and path all the way through the loader.

The other half of the check -- that every field the scorer *reads* is listed at
all -- is a scan of the source, and lives in `test_artifact_field_cover.py`. It
was split out for being a second job, not for length; the first draft of the
check asserted only the direction above, and four fields (`coverage`,
`model_run`, `schema_version` and `skipped_files`) were missing from the lists
while their tests passed.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from evaluation.harness import (
    FINDINGS_FIELDS,
    FINDINGS_NAME,
    SURFACES_FIELDS,
    SURFACES_NAME,
    _check_artifact,
)
from evaluation_fixtures import APP, findings_document, surfaces_document
from test_harness import load, stage, write_json

# Stands in for the paths the artifacts were read from; nothing here opens them.
FINDINGS_FILE = Path("artifacts/agentic_auditor/an-app") / FINDINGS_NAME
SURFACES_FILE = Path("artifacts/agentic_auditor/an-app") / SURFACES_NAME

# Each artifact, its field list, and the builder that writes a complete one.
ARTIFACTS = (
    (FINDINGS_NAME, FINDINGS_FIELDS, findings_document),
    (SURFACES_NAME, SURFACES_FIELDS, surfaces_document),
)


def refuse(document: object, fields: tuple[str, ...], path: Path) -> str:
    """Check one artifact and return the refusal it raises."""
    with pytest.raises(ValueError) as raised:
        _check_artifact(document, fields, path)
    return str(raised.value)


def refuse_through_load(tmp_path: Path, name: str, document: dict) -> tuple[str, Path]:
    """Stage one app with a short artifact; return the refusal and that file's path."""
    artifacts_dir = stage(tmp_path)
    path = artifacts_dir / APP / name
    write_json(path, document)
    with pytest.raises(ValueError) as raised:
        load(tmp_path)
    return str(raised.value), path


def test_a_real_findings_document_is_accepted() -> None:
    """Guard for the refusals below: what the tool writes really does pass."""
    document = findings_document()
    assert _check_artifact(document, FINDINGS_FIELDS, FINDINGS_FILE) is document


def test_a_real_surfaces_document_is_accepted() -> None:
    """The same for the scan, built by the real serialiser rather than hand-written."""
    document = surfaces_document()
    assert _check_artifact(document, SURFACES_FIELDS, SURFACES_FILE) is document


def test_every_field_required_of_a_findings_document_is_really_written() -> None:
    """A field the producer never writes would refuse every genuine artifact."""
    assert set(FINDINGS_FIELDS) <= set(findings_document())


def test_every_field_required_of_a_surfaces_document_is_really_written() -> None:
    """The same guard on the other artifact, so neither list can drift from the tool."""
    assert set(SURFACES_FIELDS) <= set(surfaces_document())


def test_a_findings_document_with_no_probes_is_refused() -> None:
    """The regression: this used to raise `KeyError: 'probes'` from inside the scorer."""
    document = findings_document()
    del document["probes"]
    assert "is missing probes" in refuse(document, FINDINGS_FIELDS, FINDINGS_FILE)


def test_a_findings_document_with_no_findings_is_refused() -> None:
    """An empty list is a result; an absent field is a file that cannot be scored."""
    document = findings_document()
    del document["findings"]
    assert "is missing findings" in refuse(document, FINDINGS_FIELDS, FINDINGS_FILE)


def test_a_surfaces_document_with_no_surfaces_is_refused() -> None:
    """Misses are attributed against what the scan saw, so the field is not optional."""
    document = surfaces_document()
    del document["surfaces"]
    assert "is missing surfaces" in refuse(document, SURFACES_FIELDS, SURFACES_FILE)


def test_the_refusal_names_the_file_that_is_short_of_a_field() -> None:
    """Two systems and several apps write this filename, so the path is the whole answer."""
    document = findings_document()
    del document["probes"]
    assert str(FINDINGS_FILE) in refuse(document, FINDINGS_FIELDS, FINDINGS_FILE)


def test_the_refusal_says_to_regenerate_it_rather_than_to_edit_it() -> None:
    """An artifact is produced, not written by hand -- unlike the key, which cites the schema."""
    document = findings_document()
    del document["probes"]
    assert "regenerate it" in refuse(document, FINDINGS_FIELDS, FINDINGS_FILE)


def test_an_artifact_that_is_not_an_object_is_refused_with_what_it_is() -> None:
    """A JSON file holding a list parses fine and would fail much later, on a field lookup."""
    assert "must hold an object, got list" in refuse(
        [findings_document()], FINDINGS_FIELDS, FINDINGS_FILE)


def test_a_findings_document_short_of_probes_is_refused_by_load_app(tmp_path) -> None:
    """The named regression the parametrized loop below generalises: `probes`, via the loader.

    It is kept under its own name because the `KeyError: 'probes'` in the
    docstring above is the bug that put `_check_artifact` in the read path at
    all; the loop covers this case and every other field alongside it.
    """
    document = findings_document()
    del document["probes"]
    refusal, _ = refuse_through_load(tmp_path, FINDINGS_NAME, document)
    assert "is missing probes" in refusal


@pytest.mark.parametrize("name, fields, build", ARTIFACTS,
                         ids=[artifact[0] for artifact in ARTIFACTS])
def test_every_listed_artifact_field_is_refused_by_name_and_path(
        tmp_path: Path, name: str, fields: tuple[str, ...],
        build: Callable[[], dict]) -> None:
    """One artifact per field, each short of exactly that one, all the way through the loader.

    The three hand-written refusals above name `probes`, `findings` and
    `surfaces` only; `coverage`, `model_run`, `schema_version` and
    `skipped_files` were covered by the AST subset alone, so no test said what
    a reader sees when one of them is absent. This says it for all of them.
    """
    assert fields, "an empty field list would make the loop below assert nothing"
    for field in fields:
        document = build()
        del document[field]
        refusal, path = refuse_through_load(tmp_path, name, document)
        assert f"is missing {field}" in refusal
        assert str(path) in refusal
