"""Writing a run's artifacts, and the one model call an audit makes.

`build_remediation` is the only place in the auditor that talks to a model, so
it is also the only place a server being down can change what is produced. It
degrades the artifact rather than failing the audit, exactly as a missing Syft
yields no bill of materials, and these tests hold that degradation to a shape.

There are two absences here, not one: the model server and the knowledge index
go missing independently, so each is stubbed on its own and two tests below
hold the crossed case -- an index present and no model reached.

The last tests hold the case where neither is absent, which is the only place
in the suite where `sources` are produced by the real chain -- retriever to
prompt to entry to document -- rather than handed to a builder. The index they
retrieve from is a fake store, because a real one would make these tests depend
on what this machine has indexed. Two of them use a store that records what it
was asked for, which is how the two retrieval bounds -- oversample the
candidates, cite at most TOP_K -- are held to a number rather than assumed.
"""

import json

import outputs
from artifacts.findings_document import MODEL_UNAVAILABLE, MODEL_USED
from artifacts.remediation import (
    KNOWLEDGE_INDEXED,
    MODEL_UNAVAILABLE as UNAVAILABLE_REASON,
    OWASP_CHEATSHEETS,
    SOURCE_FIELDS,
    UNAVAILABLE,
    WRITTEN,
)
from artifacts.surface import TOOL_CALL, Surface
from cli_helpers import STUB_MODEL_DIGEST, stub_knowledge, stub_model, stub_model_unavailable
from findings_fixtures import build_document, static_finding
from parsing.languages import JAVASCRIPT, PYTHON, TYPESCRIPT
from remediation_fixtures import SOURCE_PATH, indexed_knowledge
from retrieval.passages import OVERSAMPLE, TOP_K
from retrieval.store import Hit

MODULE_NAMES = ("tools", "utils")


def surface(language: str, name: str = "lookup") -> Surface:
    """One tool-call surface in the given language."""
    return Surface(TOOL_CALL, name, "app/agent.py", 1, language, "tool defined")


def test_the_declared_language_is_the_one_most_surfaces_are_written_in() -> None:
    """A snippet's fence has to claim one language, so the app's majority is chosen."""
    surfaces = [surface(PYTHON), surface(PYTHON, "second"), surface(JAVASCRIPT, "third")]
    assert outputs.declared_language(surfaces) == PYTHON


def test_the_declared_language_follows_the_surfaces_rather_than_a_default() -> None:
    """A TypeScript app must not be advised in Python."""
    assert outputs.declared_language([surface(TYPESCRIPT)]) == TYPESCRIPT


def test_an_app_with_no_surfaces_declares_python() -> None:
    """The reference implementation's language is the fallback, not an error."""
    assert outputs.declared_language([]) == PYTHON


def remediation_for(monkeypatch, findings: dict) -> dict:
    """Build the remediation document the way a run does, and parse it back.

    The knowledge base is stubbed for the same reason Syft is: left real, these
    tests would pass or fail on whether the person running them has built an
    index, and a grounded run would call the embedding server.
    """
    stub_knowledge(monkeypatch)
    return json.loads(outputs.build_remediation(findings, PYTHON, MODULE_NAMES))


def one_finding_document() -> dict:
    """A findings document with a single finding to advise on."""
    return build_document([static_finding()])


def test_a_reachable_model_is_recorded_as_used_with_its_digest(monkeypatch) -> None:
    """Provenance is what makes the prose repeatable, so it is written from the client."""
    stub_model(monkeypatch)
    run = remediation_for(monkeypatch, one_finding_document())["model_run"]
    assert run["status"] == MODEL_USED
    assert run["model_digest"] == STUB_MODEL_DIGEST
    assert run["model_settings"]


def test_a_reachable_model_produces_advice(monkeypatch) -> None:
    """The stub answers cleanly, so the accepted path is what a normal run produces."""
    stub_model(monkeypatch)
    document = remediation_for(monkeypatch, one_finding_document())
    assert document["status_counts"][WRITTEN] == 1


def test_an_unreachable_model_degrades_rather_than_failing_the_audit(monkeypatch) -> None:
    """Producing less is a normal outcome here; the file is still written."""
    stub_model_unavailable(monkeypatch)
    document = remediation_for(monkeypatch, one_finding_document())
    assert document["model_run"]["status"] == MODEL_UNAVAILABLE
    assert document["status_counts"][UNAVAILABLE] == 1
    assert document["advice"][0]["reason"] == UNAVAILABLE_REASON


def test_an_unreachable_model_still_leaves_one_entry_per_finding(monkeypatch) -> None:
    """Omitting entries would make "the server was down" look like "never run"."""
    stub_model_unavailable(monkeypatch)
    findings = build_document([static_finding(), static_finding(rule_id="other_rule")])
    document = remediation_for(monkeypatch, findings)
    assert document["advice_count"] == findings["finding_count"] == 2


def test_the_document_records_which_findings_schema_it_was_written_from(monkeypatch) -> None:
    """What invalidates the file, in place of a timestamp that would break byte-identity."""
    stub_model(monkeypatch)
    findings = one_finding_document()
    document = remediation_for(monkeypatch, findings)
    assert document["findings_schema_version"] == findings["schema_version"]


def test_two_unreachable_runs_write_byte_identical_files(monkeypatch) -> None:
    """With no model reached the derived tier is a constant, so the whole file repeats."""
    stub_model_unavailable(monkeypatch)
    stub_knowledge(monkeypatch)
    findings = one_finding_document()
    first = outputs.build_remediation(findings, PYTHON, MODULE_NAMES)
    second = outputs.build_remediation(findings, PYTHON, MODULE_NAMES)
    assert first == second


def test_an_index_present_run_that_reached_no_model_is_byte_identical(monkeypatch) -> None:
    """Task 6.3's acceptance criterion: a grounded skeleton repeats as an ungrounded one does."""
    stub_model_unavailable(monkeypatch)
    stub_knowledge(monkeypatch, indexed_knowledge())
    findings = one_finding_document()
    first = outputs.build_remediation(findings, PYTHON, MODULE_NAMES)
    second = outputs.build_remediation(findings, PYTHON, MODULE_NAMES)
    assert first == second


def test_a_missing_model_and_a_built_index_are_recorded_on_their_own_blocks(monkeypatch) -> None:
    """Two absences, two blocks: an unreachable server must not read as an unbuilt index."""
    stub_model_unavailable(monkeypatch)
    stub_knowledge(monkeypatch, indexed_knowledge())
    document = json.loads(outputs.build_remediation(
        one_finding_document(), PYTHON, MODULE_NAMES))
    assert document["knowledge_base"]["status"] == KNOWLEDGE_INDEXED
    assert document["model_run"]["status"] == MODEL_UNAVAILABLE


def test_the_serialised_document_ends_in_a_newline(monkeypatch) -> None:
    """The on-disk form is fixed, so a diff shows content rather than formatting."""
    stub_model(monkeypatch)
    stub_knowledge(monkeypatch)
    assert outputs.build_remediation(one_finding_document(), PYTHON, MODULE_NAMES).endswith("\n")


def test_write_all_writes_every_document_and_both_reports(tmp_path, monkeypatch) -> None:
    """The count it returns is the documents plus the two rendered reports."""
    stub_model(monkeypatch)
    stub_knowledge(monkeypatch)
    findings = one_finding_document()
    documents = {
        outputs.SURFACES_NAME: json.dumps({"surfaces": [], "skipped_files": [],
                                           "schema_version": 3, "surface_count": 0,
                                           "skipped_count": 0}),
        outputs.FINDINGS_NAME: json.dumps(findings),
        outputs.REMEDIATION_NAME: outputs.build_remediation(findings, PYTHON, MODULE_NAMES),
    }
    written = outputs.write_all(tmp_path / "app", documents, "app")
    assert written == len(documents) + 2
    assert (tmp_path / "app" / outputs.REPORT_NAME).is_file()
    assert (tmp_path / "app" / outputs.REMEDIATION_REPORT_NAME).is_file()


# One passage a fake index answers with. It names no risk class, because a
# passage naming a foreign one is dropped before it can be cited.
PASSAGE_TEXT = "Treat every retrieved text as data, never as instruction."
PASSAGE_HEADING = "Mitigation"


class FakeStore:
    """A stand-in for the ChromaDB store, holding the one method the retriever calls."""

    def query(self, vector: list[float], k: int) -> list[Hit]:
        """Answer any query with one passage from the registered source."""
        return [Hit("alpha-0", OWASP_CHEATSHEETS, SOURCE_PATH, PASSAGE_HEADING,
                    PASSAGE_TEXT, 0.1)]


# What the retriever asks a store for: more candidates than a finding may cite,
# because a passage naming another risk class is dropped before citing.
CANDIDATES = TOP_K * OVERSAMPLE


class RecordingStore:
    """A fake store that notes the candidate count it was asked for and answers with that many."""

    def __init__(self) -> None:
        """Start with nothing asked for."""
        self.asked_for: list[int] = []

    def query(self, vector: list[float], k: int) -> list[Hit]:
        """Record k, and answer with `CANDIDATES` distinct passages, nearest first."""
        self.asked_for.append(k)
        return [Hit(f"alpha-{index}", OWASP_CHEATSHEETS,
                    f"cheatsheets/Passage_{index}_Cheat_Sheet.md", PASSAGE_HEADING,
                    PASSAGE_TEXT, 0.1 * (index + 1)) for index in range(CANDIDATES)]


def recorded_remediation(monkeypatch) -> tuple[dict, RecordingStore]:
    """Build a grounded remediation from a recording store, and hand back both."""
    recording = RecordingStore()
    stub_model(monkeypatch)
    stub_knowledge(monkeypatch, indexed_knowledge(), recording)
    document = json.loads(outputs.build_remediation(
        one_finding_document(), PYTHON, MODULE_NAMES))
    return document, recording


def test_a_grounded_finding_asks_the_store_for_more_candidates_than_it_may_cite(monkeypatch) -> None:
    """The oversample is the headroom the risk-class drop needs, so the store is asked for all of it."""
    _document, recording = recorded_remediation(monkeypatch)
    assert recording.asked_for == [CANDIDATES]
    assert CANDIDATES > TOP_K


def test_a_grounded_finding_cites_only_top_k_of_the_candidates_it_retrieved(monkeypatch) -> None:
    """Every candidate here survives the drop and the budget, so the cut to TOP_K is what bounds it."""
    document, recording = recorded_remediation(monkeypatch)
    assert len(recording.query([], CANDIDATES)) == CANDIDATES
    assert len(document["advice"][0]["sources"]) == TOP_K


def grounded_remediation_for(monkeypatch, findings: dict) -> dict:
    """Build the remediation of a run that really retrieved, and parse it back.

    Everything but the index is what a run does: the retriever embeds the
    finding's query text, queries the store, drops and orders and cites the
    hits, and `advise_one` records what came back. Only the store and the two
    server calls are stubbed.
    """
    stub_model(monkeypatch)
    stub_knowledge(monkeypatch, indexed_knowledge(), FakeStore())
    return json.loads(outputs.build_remediation(findings, PYTHON, MODULE_NAMES))


def test_a_grounded_run_records_the_passage_its_advice_was_grounded_on(monkeypatch) -> None:
    """End to end through the real producers: the entry cites the passage the store answered."""
    entry = grounded_remediation_for(monkeypatch, one_finding_document())["advice"][0]
    assert entry["status"] == WRITTEN
    [attribution] = entry["sources"]
    assert set(attribution) == SOURCE_FIELDS
    assert (attribution["source"], attribution["path"]) == (OWASP_CHEATSHEETS, SOURCE_PATH)
    assert attribution["heading"] == PASSAGE_HEADING
    assert attribution["url"].startswith("https://")


def test_a_grounded_run_says_on_its_own_block_that_it_was_indexed(monkeypatch) -> None:
    """The pair the builder cross-checks: an entry may cite a passage only if a run says indexed."""
    document = grounded_remediation_for(monkeypatch, one_finding_document())
    assert document["knowledge_base"]["status"] == KNOWLEDGE_INDEXED
    assert document["advice"][0]["sources"]
