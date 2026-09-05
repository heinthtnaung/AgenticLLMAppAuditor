"""`passages.py`: what a finding asks, what is dropped, and how hits are ordered and cited.

Every case is a hand-made hit; no index and no model. The probe and the
per-finding grounding, which need an index, are in test_retrieve_probe.py.
Renamed with the split that moved these helpers out of `retrieve.py`, so the
file still sits beside the one module it tests.
"""

from artifacts.advice_rules import evidence_line
from artifacts.remediation import MAX_SOURCES_PER_FINDING, OWASP_CHEATSHEETS, SOURCE_FIELDS
from remediation_fixtures import finding_record
from retrieval.chunks import CHUNK_CHARS
from retrieval.manifest import SOURCES
from retrieval.passages import (
    MAX_REFERENCE_CHARS,
    OVERSAMPLE,
    TOP_K,
    as_source,
    drop_foreign_owasp,
    query_text,
    reference_block,
    stable_order,
    within_budget,
)
from retrieval.store import Hit

PATH = "cheatsheets/Alpha_Cheat_Sheet.md"
OWN_ID = "LLM06"

# A full-size chunk, and more of them than the budget can hold. Sized from the
# chunker rather than from the budget, so raising the budget makes this test
# fail instead of quietly scaling with it.
OVERSIZED_TEXT_CHARS = CHUNK_CHARS
OVERSIZED_COUNT = 5


def hit(hit_id: str, text: str = "keep the tool narrow", distance: float = 0.1,
        heading: str = "Mitigation") -> Hit:
    """One hand-made hit from the registered source, other fields fixed."""
    return Hit(hit_id, OWASP_CHEATSHEETS, PATH, heading, text, distance)


def test_top_k_is_the_schemas_per_finding_limit() -> None:
    """One limit, owned by the schema, so the retriever cannot cite more than an entry may carry."""
    assert TOP_K == MAX_SOURCES_PER_FINDING


def test_the_query_is_the_title_and_the_evidence_line() -> None:
    """What a finding asks the knowledge base is what a reader would ask: what, and where."""
    finding = finding_record()
    assert query_text(finding) == f"{finding['title']}. {evidence_line(finding)}"


def test_a_passage_naming_another_risk_class_is_dropped() -> None:
    """Grounding on it would lead the model to re-classify, which the guard then refuses."""
    kept = drop_foreign_owasp([hit("a", "this is LLM01"), hit("b", "plain advice")], OWN_ID)
    assert [one.id for one in kept] == ["b"]


def test_a_passage_naming_the_findings_own_class_is_kept() -> None:
    """Its own class is the one a passage should name."""
    assert len(drop_foreign_owasp([hit("a", f"about {OWN_ID}")], OWN_ID)) == 1


def test_a_longer_id_does_not_count_as_the_shorter_one() -> None:
    """`LLM011` is not `LLM01`; the shared predicate matches whole words."""
    assert len(drop_foreign_owasp([hit("a", "see LLM011")], OWN_ID)) == 1


def test_hits_are_ordered_nearest_first() -> None:
    """Distance decides the order the prompt cites them in."""
    ordered = stable_order([hit("far", distance=0.9), hit("near", distance=0.1)])
    assert [one.id for one in ordered] == ["near", "far"]


def test_equal_distances_are_broken_by_id() -> None:
    """A tie must not depend on the order the database returned, or two runs cite differently."""
    ordered = stable_order([hit("b", distance=0.5), hit("a", distance=0.5)])
    assert [one.id for one in ordered] == ["a", "b"]


def test_the_budget_keeps_the_leading_passages_that_fit_together() -> None:
    """Cumulative length, in order: the first two fit, the third does not."""
    hits = [hit("a", "x" * 10), hit("b", "y" * 10), hit("c", "z" * 10)]
    assert [one.id for one in within_budget(hits, limit=25)] == ["a", "b"]


def test_the_budget_stops_at_the_first_overflow_rather_than_skipping_it() -> None:
    """A later, shorter passage is not pulled ahead of a nearer one: order is the ranking."""
    hits = [hit("a", "x" * 10), hit("b", "y" * 30), hit("c", "z" * 5)]
    assert [one.id for one in within_budget(hits, limit=20)] == ["a"]


def test_the_default_budget_bounds_the_block_when_no_limit_is_named() -> None:
    """The bound is the default, so a caller that names no limit still gets a bounded block.

    Every real caller is `Grounding.passages_for`, which names none. Ollama
    truncates the front of an overrunning prompt -- where the instructions are
    -- so the constant, not the call site, is what keeps the block small.
    """
    assert OVERSIZED_TEXT_CHARS * OVERSIZED_COUNT > MAX_REFERENCE_CHARS, "the input must overrun"
    hits = [hit(str(index), "x" * OVERSIZED_TEXT_CHARS) for index in range(OVERSIZED_COUNT)]
    kept = within_budget(hits)
    assert 0 < len(kept) < OVERSIZED_COUNT
    assert sum(len(one.text) for one in kept) <= MAX_REFERENCE_CHARS


def test_the_retriever_oversamples_so_dropping_still_leaves_top_k() -> None:
    """The candidate count has to exceed what may be cited, or the risk-class drop cites fewer."""
    assert TOP_K * OVERSAMPLE > TOP_K


def test_a_source_carries_exactly_the_schemas_four_fields() -> None:
    """`advice_entry` refuses any other shape, so the producer writes exactly that one."""
    assert set(as_source(hit("a"))) == SOURCE_FIELDS


def test_an_empty_heading_becomes_null_in_the_source() -> None:
    """Chroma refuses None, so the index holds ""; the artifact says null, as SCHEMAS.md promises."""
    assert as_source(hit("a", heading=""))["heading"] is None


def test_the_source_url_is_the_registrys_public_page() -> None:
    """Attribution points at where the passage is published, via the one URL template."""
    assert as_source(hit("a"))["url"] == SOURCES[OWASP_CHEATSHEETS].public_url(PATH)


def test_the_reference_block_labels_each_passage_with_its_origin() -> None:
    """Numbered, with source, path and heading, so the model can say which one it drew on."""
    block = reference_block([hit("a", "first text"), hit("b", "second text", heading="")])
    assert block == (f"[1] {OWASP_CHEATSHEETS} {PATH} - Mitigation\nfirst text\n\n"
                     f"[2] {OWASP_CHEATSHEETS} {PATH}\nsecond text")


def test_no_passages_make_an_empty_reference_block() -> None:
    """An ungrounded prompt carries no block at all, not an empty label."""
    assert reference_block([]) == ""
