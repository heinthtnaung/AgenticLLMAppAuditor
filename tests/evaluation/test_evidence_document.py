"""The evidence blocks as `evaluation.json` actually holds them, per app and pooled.

Split from `test_evidence.py`, which owns the three predicates and the counting
functions in isolation. This file owns only what reaches the document: that
every app entry carries its own block, that the totals carry the pooled one, and
that nothing under either is anything but an int.

That last one is the refusal the whole evidence design rests on. The proposal
asks for the *share* of findings carrying each kind of link and this artifact
will not hold one, so a count and its denominator travel together and the
division stays the reader's. Asserting the counts are ints is what stops a
`pct_*` field being added later, in any spelling.

The document is round-tripped through `json.dumps`/`json.loads` before it is
read, so what is asserted is the serialised artifact rather than the objects the
builder happened to return.
"""

import json

from evaluation.document import build_evaluation
from test_evidence import EVIDENCE_KEYS, scored_app, serialised, unreportable_app

from advisory_fixtures import advisory_finding
from findings_fixtures import OWASP_ID, RULE_ID, static_finding


def document_with_evidence() -> dict:
    """The evaluation two scored apps produce, serialised as it is written to disk."""
    apps = [scored_app("second-app", [static_finding(), advisory_finding()]),
            unreportable_app("first-app")]
    return json.loads(json.dumps(build_evaluation(apps)))


def evidence_blocks(document: dict) -> list[dict]:
    """Every evidence block in the document: one per app, and the pooled one."""
    return [app["evidence"] for app in document["apps"]] + [document["totals"]["evidence"]]


def test_every_app_entry_carries_its_own_evidence_block() -> None:
    """Per-app, so a share is never quoted across apps that were never named."""
    document = document_with_evidence()
    assert len(document["apps"]) == 2
    for app in document["apps"]:
        assert set(app["evidence"]) == EVIDENCE_KEYS


def test_the_totals_carry_the_pooled_evidence_block() -> None:
    """The pool is the per-app counts added up, and it names its two apps."""
    pooled = document_with_evidence()["totals"]["evidence"]
    assert pooled["apps_included"] == ["first-app", "second-app"]
    assert pooled["findings_considered"] == 3
    assert (pooled["with_code_evidence"], pooled["with_sbom_evidence"]) == (3, 1)
    assert pooled["with_vex_evidence"] == 1


def test_every_count_in_every_evidence_block_is_an_int() -> None:
    """The rule the whole design exists for, asserted where it would be broken first.

    Stricter than refusing floats, and it is the strictness that has teeth: a
    share added as `pct_code_evidence` fails here whether it is written as a
    float or dressed up as the string `"75.0%"`. `set(counts) == EVIDENCE_KEYS`
    is what makes that hold -- a fifth key is refused before its type matters.
    """
    blocks = evidence_blocks(document_with_evidence())
    assert len(blocks) == 3
    for block in blocks:
        counts = {key: value for key, value in block.items() if key != "apps_included"}
        assert set(counts) == EVIDENCE_KEYS
        assert [key for key, value in counts.items() if not isinstance(value, int)] == []


def test_the_scorer_counts_only_the_findings_that_app_produced() -> None:
    """Per-app rather than derived from the key: the block describes the tool's output.

    Guard against the pooled tests above passing over a document where every
    app's block is the same: these two differ.
    """
    document = document_with_evidence()
    by_app = {app["app"]: app["evidence"] for app in document["apps"]}
    assert by_app["second-app"]["findings_considered"] == 2
    assert by_app["first-app"]["findings_considered"] == 1
    assert by_app["second-app"]["with_vex_evidence"] == 1
    assert by_app["first-app"]["with_vex_evidence"] == 0


def test_the_scored_app_reads_the_same_rule_ids_the_fixture_produced() -> None:
    """Guard: the counts above are only meaningful if real findings reached the scorer."""
    document = document_with_evidence()
    assert document["apps"][1]["produced_finding_count"] == 2
    assert {f["rule_id"] for f in serialised(static_finding(), advisory_finding())} == {
        RULE_ID, "known_advisory"}
    assert serialised(static_finding())[0]["owasp_id"] == OWASP_ID
