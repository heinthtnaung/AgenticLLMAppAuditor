"""Guards on the markup the page shares: escaping, and a number that never changes.

Everything a scanner read reaches the page through `text`, so a summary carrying
a `<` cannot close a tag; and every figure reaches it through `number`, which
formats and refuses rather than rounding. Both are one function precisely so
there is one place to hold.
"""

from report.html_layout import listing, number, scored_chip, section, separated, tag, text

CLOSING_TAG = "</style><script>alert(1)</script>"


def test_anything_a_scanner_read_is_escaped_before_it_reaches_the_page():
    # An advisory summary, a vector and a component path all arrive from outside
    # this tool, and any of them can carry a `<`.
    assert text(CLOSING_TAG) == "&lt;/style&gt;&lt;script&gt;alert(1)&lt;/script&gt;"


def test_a_quotation_mark_is_escaped_so_nothing_can_open_an_attribute():
    assert text('" onload="x') == "&quot; onload=&quot;x"


def test_an_ampersand_is_escaped_once_and_not_twice():
    assert text("a & b") == "a &amp; b"


def test_a_number_is_written_exactly_as_the_record_carries_it():
    assert number(7.5) == "7.5"
    assert number(0.0) == "0.0"
    assert number(46.85) == "46.85"
    assert number(-15) == "-15"


def test_a_number_that_is_not_a_number_is_refused_rather_than_printed():
    # The refusal is the guard against a figure arriving as prose somebody
    # formatted elsewhere, which would be a second place a score is written.
    for wrong in ("7.5", None, [7.5]):
        try:
            number(wrong)
        except TypeError as refusal:
            assert "must be a number" in str(refusal)
            continue
        raise AssertionError(f"{wrong!r} was rendered as a figure instead of refused")


def test_a_boolean_is_refused_because_true_is_not_the_figure_one():
    try:
        number(True)
    except TypeError as refusal:
        assert "bool" in str(refusal)
        return
    raise AssertionError("True was rendered as a figure instead of refused")


def test_a_section_with_nothing_in_it_is_not_put_on_the_page():
    assert section("Council", "a lede", "") == ""


def test_a_section_carries_its_title_and_the_line_saying_what_it_holds():
    rendered = section("Council", "what it settled", "<p>body</p>")
    assert "<h2>Council</h2>" in rendered
    assert '<p class="lede">what it settled</p>' in rendered


def test_a_list_wraps_each_item_so_no_caller_loops_inside_a_loop():
    assert listing(["a", "b"], "sources") == '<ul class="sources"><li>a</li><li>b</li></ul>'


def test_joining_fragments_drops_the_ones_that_are_empty():
    assert separated(["a", "", "b"]).count("separator") == 1


def test_a_chip_says_which_scale_it_is_on_as_well_as_which_band():
    # Two bare numbers in two bands read as one number somebody got wrong, so
    # the scale is on the chip and not only in the heading above it.
    chip = scored_chip("cvss", "9.8", "Critical", "cvss")
    assert '<span class="scale">cvss</span>' in chip
    assert '<span class="value">9.8</span>' in chip
    assert 'class="cvss band-critical"' in chip


def test_an_element_with_no_class_is_written_without_an_empty_one():
    assert tag("p", "said") == "<p>said</p>"
