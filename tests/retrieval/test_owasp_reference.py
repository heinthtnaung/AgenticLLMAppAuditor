"""The reference table: one entry per risk this project reports, each naming its edition.

A fabricated citation is the worst thing a security report can hold, so every
OWASP-sourced entry must point under the OWASP GenAI site and name the 2025
list, this project's own risk class must cite the project and no URL, and the
one renumbered id must say so in its source line.
"""

import pytest

from artifacts.finding import OWASP_IDS
from retrieval.owasp_reference import (
    OWASP_2025,
    OWASP_SITE,
    REFERENCES,
    THIS_PROJECT,
    Reference,
    reference_for,
)

OUTPUT_HANDLING = "LLM02"
PROJECT_RISK = "AUDITABILITY"


def owasp_sourced() -> list[Reference]:
    """The entries that cite the OWASP list rather than this project."""
    return [ref for ref in REFERENCES.values() if ref.source != THIS_PROJECT]


def test_the_table_covers_exactly_the_reported_risk_ids() -> None:
    """A finding's `owasp_id` is always a key here, and nothing here is a class no finding carries."""
    assert set(REFERENCES) == set(OWASP_IDS)


def test_every_owasp_sourced_entry_links_under_the_owasp_site() -> None:
    """The URL is what a reader follows; it must lead to OWASP and nowhere else."""
    for reference in owasp_sourced():
        assert reference.url is not None and reference.url.startswith(OWASP_SITE), reference.title


def test_every_owasp_sourced_entry_names_the_2025_edition() -> None:
    """Supply chain was LLM05 before 2025; an entry that named no edition would be ambiguous."""
    for reference in owasp_sourced():
        assert "2025" in reference.source, reference.title


def test_the_projects_own_risk_cites_the_project_and_no_url() -> None:
    """AUDITABILITY is not an OWASP entry, so an owasp.org link for it would be invented."""
    assert REFERENCES[PROJECT_RISK].source == THIS_PROJECT
    assert REFERENCES[PROJECT_RISK].url is None


def test_the_project_risk_is_the_only_entry_without_a_url() -> None:
    """The two facts agree in both directions: no URL means this project, and only then."""
    assert [key for key, ref in REFERENCES.items() if ref.url is None] == [PROJECT_RISK]


def test_insecure_output_handling_says_it_keeps_the_2023_numbering() -> None:
    """This project's LLM02 is the 2025 list's LLM05, and the entry says so rather than hiding it."""
    source = REFERENCES[OUTPUT_HANDLING].source
    assert "2023" in source and "LLM05" in source and "2025" in source


def test_insecure_output_handling_cites_the_2025_llm05_page() -> None:
    """The 2025 LLM02 page is a different risk, so the link goes to the renumbered entry."""
    assert "llm05" in REFERENCES[OUTPUT_HANDLING].url


def test_every_entry_has_a_title_a_summary_and_mitigations() -> None:
    """An empty entry would inject nothing and claim to have grounded the prompt."""
    for reference in REFERENCES.values():
        assert reference.title.strip() and reference.summary.strip()
        assert len(reference.mitigations) >= 1


def test_reference_for_returns_the_entry_for_a_known_id() -> None:
    """Deterministic lookup, not search: the id alone decides."""
    assert reference_for("LLM01") is REFERENCES["LLM01"]


def test_reference_for_refuses_an_unknown_id() -> None:
    """An id this project does not report has no entry, and silence would be a fabrication."""
    with pytest.raises(ValueError, match="no reference for 'LLM99'"):
        reference_for("LLM99")


def test_the_prompt_text_carries_title_source_summary_and_every_mitigation() -> None:
    """What the model is shown is the whole entry, each mitigation numbered."""
    reference = REFERENCES["LLM06"]
    text = reference.prompt_text()
    assert reference.title in text and OWASP_2025 in text and reference.summary in text
    for number, mitigation in enumerate(reference.mitigations, 1):
        assert f"({number}) {mitigation}" in text


def test_a_reference_is_immutable() -> None:
    """A constant of the tool, not a passage a run retrieved: nothing may edit it."""
    with pytest.raises(AttributeError):
        REFERENCES["LLM01"].url = "https://elsewhere.example"
