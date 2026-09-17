"""What the comparison's summary says a key is, read off the key rather than spelled.

The last line of a `--compare-models` run names the drafted key it scored both
arms against and, in brackets, that key's standing. It used to print the literal
`(tool_drafted, verified: false)` -- true by construction while the two fields
were not independent, because `harness.check_key` refused the only pairing that
would have made it false.

They are independent now. `POST /api/keys/{app}/verify` records a human check on
a drafted key, so `tool_drafted` + `verified: true` is a document that exists on
disk, and a hardcoded "verified: false" would have summarised it as unchecked --
quietly, in the one line a reader takes the run's standing from.

`_standing` is a pure function over a file, so this is the whole of it: no
model, no clone, no socket, no arm run. The key documents are built by
`key_drafting.key_document`, the producer, rather than hand-written, so a field
renamed at the source reaches this file instead of passing it.

Every key here is one this function can read. The three ways a hand-editable
file stops being readable -- half-saved, not an object, nobody can open it --
are `test_compare_run_standing_read.py`, because they are a claim about the
guard and not about what the summary says.
"""

import json
from pathlib import Path

import compare_run
from drafted_key_fixtures import APP, COMMIT, ENTRY, fit_key
from keys import key_drafting
from keys.grading_keys import MANUAL_REVIEW, TOOL_DRAFTED

# The two words the second half can be. Spelled here so a change to either fails
# loudly rather than being read as a different key.
VERIFIED = "verified"
UNVERIFIED = "unverified"

# What a human recorded through the verify route, which is the state this
# function had to stop spelling for itself.
CHECKED_BY = "Quokka Reviewer"
CHECKED_ON = "2026-09-16"


def written(tmp_path: Path, **fields) -> Path:
    """One grading key on disk, built by the producer and corrected by `fields`."""
    document = {**key_drafting.key_document(APP, [ENTRY], COMMIT), **fields}
    path = tmp_path / "a-key.ground_truth.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return path



# --- both halves are read ------------------------------------------------------

def test_a_drafted_unverified_key_reads_as_both(tmp_path) -> None:
    """The ordinary case: what every drafted key says about itself the moment it is written."""
    assert compare_run._standing(written(tmp_path)) == f"{TOOL_DRAFTED}, {UNVERIFIED}"


def test_a_drafted_key_a_human_checked_reads_as_verified(tmp_path) -> None:
    """The case the literal got wrong: the pairing is legal, and the summary must say so."""
    standing = compare_run._standing(
        written(tmp_path, verified=True, verified_by=CHECKED_BY, verified_date=CHECKED_ON))
    assert standing == f"{TOOL_DRAFTED}, {VERIFIED}"


def test_a_hand_written_key_reads_as_its_own_source(tmp_path) -> None:
    """`source` is read too, not assumed: three pairings exist and this is the third."""
    standing = compare_run._standing(written(tmp_path, source=MANUAL_REVIEW, verified=True))
    assert standing == f"{MANUAL_REVIEW}, {VERIFIED}"


def test_the_two_halves_move_independently(tmp_path) -> None:
    """The whole point of the change, as one comparison: same source, different answer."""
    drafted = compare_run._standing(written(tmp_path))
    checked = compare_run._standing(written(tmp_path, verified=True))
    assert drafted != checked
    assert drafted.startswith(TOOL_DRAFTED) and checked.startswith(TOOL_DRAFTED)


def test_the_producer_really_writes_an_unverified_drafted_key(tmp_path) -> None:
    """Guard: a producer that wrote something else would make the first test a coincidence."""
    document = json.loads(written(tmp_path).read_text(encoding="utf-8"))
    assert (document["source"], document["verified"]) == (TOOL_DRAFTED, False)


def test_a_key_fit_for_promotion_reads_the_same_way(tmp_path) -> None:
    """The document a promotion actually reads, not only the one drafting writes."""
    path = tmp_path / "fit.ground_truth.json"
    path.write_text(json.dumps(fit_key()), encoding="utf-8")
    assert compare_run._standing(path) == f"{TOOL_DRAFTED}, {UNVERIFIED}"

