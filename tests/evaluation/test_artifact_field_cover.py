"""Every artifact field the scorer reads is named by a tuple in `harness.py`.

Split from `test_artifact_check.py`, which is about the refusals
`_check_artifact` produces; nothing here calls it. This file scans source,
because a read added to `scorer.py` and not to a field tuple reaches the scorer
unguarded and raises exactly the bare `KeyError` that check exists to prevent.
That direction is what the first version of the check lacked, and four fields
-- `coverage`, `model_run`, `schema_version` and `skipped_files` -- were missing
from the tuples while every test passed.

A sibling of `test_entry_field_cover.py` rather than part of it, because the two
scans answer different questions about different documents. This one reads the
tool's *own* artifacts, each under one uniform name (`findings_document`,
`surfaces_document`), in one module -- so a plain subset assertion is the whole
job. A grading-key entry is read under three names across two modules, and
splits into crashable and `.get()`-guarded reads that `subscript_keys` cannot
tell apart; that file's union and intersection scans exist for a distinction
this one does not have.

Limit: `subscript_keys` matches a constant string key, so a field reached
through a variable -- `document[name]` in a loop over field names -- is not
seen. Every read in `scorer.py` is a literal today, under both names, and a
test cannot assert what it cannot see; the gap is written down instead.
"""

from ast_scan import parse, subscript_keys
from conftest import SRC_DIR
from evaluation.harness import FINDINGS_FIELDS, SURFACES_FIELDS

# The module that reads both artifacts, and the names it reads them through.
SCORER_SOURCE = SRC_DIR / "evaluation" / "scorer.py"
READERS = (("findings_document", FINDINGS_FIELDS), ("surfaces_document", SURFACES_FIELDS))

# A read of a field no artifact has, planted to prove the scan really looks.
PLANTED_FIELD = "invented_artifact_field"
PLANTED_SOURCE = f'def read(findings_document):\n    return findings_document["{PLANTED_FIELD}"]\n'


def test_every_artifact_field_the_scorer_reads_is_listed_here() -> None:
    """The direction that catches a hole: an unlisted field reaches the scorer unguarded.

    This is what the first version of the artifact check lacked, and four
    fields were missing from the lists because of it.
    """
    for variable, fields in READERS:
        read = subscript_keys(parse(SCORER_SOURCE), variable)
        assert read <= set(fields), f"{variable}: {sorted(read - set(fields))}"


def test_the_scorer_reads_both_artifacts_by_subscript_at_all() -> None:
    """Guard: a scan that found nothing would make the subset above vacuously true."""
    for variable, _fields in READERS:
        assert len(subscript_keys(parse(SCORER_SOURCE), variable)) >= 2


def test_the_scan_sees_a_planted_read_of_an_unlisted_artifact_field(tmp_path) -> None:
    """Mutation check: a field read off an artifact must really be picked up."""
    planted = tmp_path / "planted_scorer.py"
    planted.write_text(PLANTED_SOURCE, encoding="utf-8")
    assert subscript_keys(parse(planted), "findings_document") == {PLANTED_FIELD}
