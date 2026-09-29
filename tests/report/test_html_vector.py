"""Guards on a vector shown metric by metric: named tooltips, differing ones marked.

The split is deterministic from the string and the highlight comes from the
caller (the record's differing metrics), so the page never recomputes which
metrics disagree, and the vector's visible text is exactly what was published.
"""

import re

from report.html_vector import vector_markup

CONF = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"
TEMPORAL = "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N/E:H"


def visible(markup: str) -> str:
    """Give the text a reader sees, with the metric spans stripped away."""
    return re.sub(r"<[^>]+>", "", markup)


def test_the_version_prefix_and_separators_are_their_own_spans():
    markup = vector_markup(CONF)
    assert '<span class="vp">CVSS:3.1</span>' in markup
    assert '<span class="vs">/</span>' in markup


def test_each_metric_is_a_span_with_its_name_and_value_in_a_tooltip():
    markup = vector_markup(CONF)
    assert '<span class="vm" title="Attack Vector: Network">AV:N</span>' in markup
    assert '<span class="vm" title="Confidentiality: High">C:H</span>' in markup


def test_the_differing_metrics_are_marked_and_come_from_the_caller():
    markup = vector_markup(CONF, ("C", "A"))
    assert '<span class="vm diff" title="Confidentiality: High">C:H</span>' in markup
    assert '<span class="vm diff" title="Availability: None">A:N</span>' in markup
    assert '<span class="vm" title="Integrity: None">I:N</span>' in markup


def test_a_temporal_metric_is_named_and_the_base_score_never_reads_it():
    assert 'title="Exploit Code Maturity: High">E:H</span>' in vector_markup(TEMPORAL)


def test_the_visible_text_is_the_vector_exactly_as_published():
    # The quotation is never edited or reordered; splitting it must not change it.
    assert visible(vector_markup(CONF)) == CONF


def test_a_pair_the_vocabulary_does_not_name_gets_no_tooltip():
    # An environmental metric is not a readable one, so it is shown without a name.
    assert '<span class="vm">CR:H</span>' in vector_markup("CVSS:3.1/CR:H")
