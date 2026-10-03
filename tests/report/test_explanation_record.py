"""Guards on the explanation record: no explanation without an item, a reason, or its model."""

import pytest

from council.explanation_prompt import EXPLANATION_PROMPT_VERSION
from report.explanation_record import DroppedMetric, SourcesExplained, SourcesNotExplained

DROPPED = DroppedMetric("C", "It is bad.", "the whole disk", False, "unverified quotation")


def test_an_explanation_with_no_item_kept_is_refused():
    with pytest.raises(ValueError, match="kept no item"):
        SourcesExplained("CVE-1", "big:27b", "sources-differ-1", ())


def test_a_finding_not_explained_must_say_why():
    with pytest.raises(ValueError, match="no reason why"):
        SourcesNotExplained("CVE-1", "")


@pytest.mark.parametrize("model, version", [("big:27b", ""), ("", EXPLANATION_PROMPT_VERSION)])
def test_a_model_is_named_with_its_prompt_version_or_neither_is(model, version):
    with pytest.raises(ValueError, match="not both"):
        SourcesNotExplained("CVE-1", "failed", model=model, prompt_version=version)


def test_dropped_items_that_name_no_model_are_refused():
    with pytest.raises(ValueError, match="names no model"):
        SourcesNotExplained("CVE-1", "none was kept", (DROPPED,))


def test_a_record_names_a_model_only_where_one_was_asked():
    asked = SourcesNotExplained("CVE-1", "x", (DROPPED,), "big:27b", EXPLANATION_PROMPT_VERSION)
    assert (asked.asked, SourcesNotExplained("CVE-1", "the sources agree").asked) == (True, False)
