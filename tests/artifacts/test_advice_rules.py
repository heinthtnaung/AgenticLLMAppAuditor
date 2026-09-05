"""The one predicate that says which *other* risk classes a text names.

`foreign_owasp_ids` is shared: the guidance guard refuses prose that names another
class, and the retriever drops a passage that would lead the model to. Both
depend on the same two edges -- a finding's own id is not foreign, and an id is
matched as a whole word, so `LLM011` is not `LLM01`. The rest of the judging
(identifiers, snippets, guidance) has its own test files and is not repeated here.
"""

from artifacts import advice_rules
from artifacts.advice_rules import evidence_line, foreign_owasp_ids
from artifacts.finding import OWASP_IDS

OWN_ID = "LLM06"


def test_ids_come_back_in_vocabulary_order_not_text_order() -> None:
    """Sorted as OWASP_IDS lists them, so two runs write the same list for the same prose."""
    text = "AUDITABILITY first, then LLM06, then LLM01"
    assert foreign_owasp_ids(text, "LLM03") == ["LLM01", "LLM06", "AUDITABILITY"]


def test_the_findings_own_id_is_not_foreign() -> None:
    """Naming its own class is what advice is for; only another class re-classifies."""
    assert foreign_owasp_ids(f"This is a {OWN_ID} weakness.", OWN_ID) == []


def test_a_longer_id_does_not_match_a_shorter_one() -> None:
    """`LLM011` is not `LLM01`: the match is a whole word, not a prefix."""
    assert foreign_owasp_ids("filed under LLM011", OWN_ID) == []


def test_an_id_embedded_in_a_word_is_not_named() -> None:
    """A word character on either side makes it a different token."""
    assert foreign_owasp_ids("see xLLM01y and LLM01x", OWN_ID) == []


def test_an_id_followed_by_punctuation_is_still_named() -> None:
    """A full stop is a boundary, not an escape, or the guard is walked by punctuation."""
    assert foreign_owasp_ids("This is really LLM01.", OWN_ID) == ["LLM01"]


def test_text_naming_no_class_yields_an_empty_list() -> None:
    """The common case: ordinary advice names nothing and is not refused for it."""
    assert foreign_owasp_ids("Keep the tool narrow and check who asked.", OWN_ID) == []


def test_every_vocabulary_id_is_foreign_to_some_other_finding() -> None:
    """The predicate covers the whole vocabulary, not a hard-coded few."""
    for owasp_id in OWASP_IDS:
        others = [one for one in OWASP_IDS if one != owasp_id]
        assert foreign_owasp_ids(" ".join(others), owasp_id) == others


def test_the_evidence_line_is_defined_by_the_rules_module() -> None:
    """It moved here with the guard; the retriever imports it from here, not from `remediation`."""
    assert evidence_line.__module__ == advice_rules.__name__
