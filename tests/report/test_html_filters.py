"""Guards on the filter controls the script wires: the tags, the search box, the toggle-all.

These hold the data attributes the script reads, so the markup and the script
cannot drift apart on the name of a control.
"""

from report.html_filters import (
    Segment, empty_line, search_box, segmented, toggle_all_button, toolbar,
)

SEGMENTS = (Segment("all", "All", 3), Segment("disagree", "Disagree", 1))


def test_the_toolbar_names_the_host_the_script_filters():
    assert 'class="toolbar" data-filter-for="findings-table"' in toolbar("findings-table", "")


def test_the_toolbar_carries_a_result_count_the_script_fills():
    assert '<span class="result-count"></span>' in toolbar("host", "")


def test_the_first_segment_is_pressed_and_each_carries_its_tag_and_count():
    seg = segmented(SEGMENTS)
    assert '<button type="button" data-filter="all" aria-pressed="true">All' in seg
    assert '<button type="button" data-filter="disagree" aria-pressed="false">Disagree' in seg
    assert seg.count('<span class="n">') == len(SEGMENTS)


def test_the_search_box_carries_the_data_search_the_script_reads():
    box = search_box("Search findings")
    assert "data-search" in box
    assert '<span class="sr">Search findings</span>' in box


def test_the_toggle_all_button_names_its_host_and_both_labels():
    button = toggle_all_button("council-list", "Expand all metrics", "Collapse all metrics")
    assert 'data-toggle-all="council-list"' in button
    assert 'data-open="false"' in button
    assert 'data-more="Expand all metrics"' in button
    assert 'data-less="Collapse all metrics"' in button


def test_the_empty_note_is_hidden_until_a_filter_empties_the_list():
    assert empty_line("No finding matches.") == '<p class="empty" hidden>No finding matches.</p>'
