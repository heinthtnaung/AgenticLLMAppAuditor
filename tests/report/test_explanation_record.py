"""Guards on the explanation record: nothing that says it explained without an item, or why not."""

import pytest

from report.explanation_record import SourcesExplained, SourcesNotExplained


def test_an_explanation_with_no_item_kept_is_refused():
    with pytest.raises(ValueError, match="kept no item"):
        SourcesExplained("CVE-1", "big:27b", "sources-differ-1", ())


def test_a_finding_not_explained_must_say_why():
    with pytest.raises(ValueError, match="no reason why"):
        SourcesNotExplained("CVE-1", "")
