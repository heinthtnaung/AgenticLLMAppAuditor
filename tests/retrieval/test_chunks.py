"""Markdown in, passages out: what is kept, what is dropped, and how it is cut.

Pure functions, so every case is a string. The fence rule follows CommonMark:
a fence of four backticks can hold lines of three, and a line with a backtick
after the opener is inline code, not a fence -- the Cheat Sheets have both.
"""

from artifacts.remediation import OWASP_CHEATSHEETS
from retrieval.chunks import (
    CHUNK_CHARS,
    ID_CHARS,
    Passage,
    chunk_markdown,
    sections,
    split_long,
    strip_code_and_tables,
)

PATH = "cheatsheets/Example_Cheat_Sheet.md"

FENCED = ["prose before", "```python", "os.system(cmd)", "```", "prose after"]
NESTED_FENCE = ["````markdown", "```", "shown code", "```", "````", "prose after"]
INLINE_ON_ITS_OWN_LINE = ["```rm -rf /```", "prose after"]
TABLE = ["| Risk | Fix |", "|------|-----|", "| A    | B   |", "prose"]

DOCUMENT = "\n".join([
    "Preamble before any heading.",
    "",
    "# Title",
    "",
    "Under the title.",
    "",
    "## Mitigation ##",
    "",
    "Under the mitigation heading.",
    "",
])


def test_text_before_the_first_heading_keeps_an_empty_heading() -> None:
    """Preamble is prose too; it is kept under `""` rather than lost."""
    assert sections(["intro", "# A", "body"]) == [("", "intro"), ("A", "body")]


def test_a_heading_is_captured_without_its_hashes() -> None:
    """Leading and closing hashes are Markdown syntax, not part of the title."""
    assert sections(["## Mitigation ##", "body"]) == [("Mitigation", "body")]


def test_a_heading_deeper_than_four_levels_is_prose() -> None:
    """Five hashes is below the cut, so it stays inside the section above it."""
    assert sections(["# A", "##### deep", "body"]) == [("A", "##### deep\nbody")]


def test_a_heading_with_no_body_yields_no_section() -> None:
    """An empty passage would embed to noise and cite nothing."""
    assert sections(["# A", "", "# B", "body"]) == [("B", "body")]


def test_a_fenced_code_block_is_dropped_with_its_fences() -> None:
    """Advice grounded on a code block invites a snippet the contract then refuses."""
    assert strip_code_and_tables(FENCED) == ["prose before", "prose after"]


def test_a_four_backtick_fence_holds_three_backtick_lines() -> None:
    """A block showing Markdown closes on its own fence, not on the first inner one."""
    assert strip_code_and_tables(NESTED_FENCE) == ["prose after"]


def test_an_inline_span_on_its_own_line_is_not_a_fence() -> None:
    """CommonMark: a backtick after the opener makes it inline code, so the prose after survives."""
    assert strip_code_and_tables(INLINE_ON_ITS_OWN_LINE) == ["", "prose after"]


def test_inline_code_mid_sentence_is_removed() -> None:
    """Code quoted inline is still code, and is cut out of the sentence."""
    assert strip_code_and_tables(["run ```rm -rf /``` never"]) == ["run  never"]


def test_table_rows_are_dropped() -> None:
    """A table row is a cell grid, not a sentence to retrieve."""
    assert strip_code_and_tables(TABLE) == ["prose"]


def test_a_horizontal_rule_is_dropped() -> None:
    """`---` is a rule in these files, never front-matter; either way it carries no prose."""
    assert strip_code_and_tables(["a", "---", "b"]) == ["a", "b"]


def test_text_within_the_size_is_one_piece() -> None:
    """Nothing to cut, so nothing is."""
    assert split_long("short", size=100) == ["short"]


def test_paragraphs_are_kept_whole_while_they_fit() -> None:
    """The cut falls between paragraphs, never inside one that would fit."""
    first, second = "a" * 50, "b" * 50
    assert split_long(f"{first}\n\n{second}", size=80) == [first, second]


def test_paragraphs_that_fit_together_stay_together() -> None:
    """Two short paragraphs in one piece keep their context for the model."""
    first, second, third = "a" * 30, "b" * 30, "c" * 60
    assert split_long(f"{first}\n\n{second}\n\n{third}", size=80) == [f"{first}\n\n{second}", third]


def test_an_oversized_paragraph_is_sliced_with_overlap() -> None:
    """Each window repeats the tail of the last, so a sentence cut in two is whole somewhere."""
    paragraph = "abcdefghij" * 30
    pieces = split_long(paragraph, size=100, overlap=20)
    assert [len(piece) for piece in pieces] == [100, 100, 100, 60]
    assert pieces[1][:20] == pieces[0][-20:]


def test_every_piece_of_a_long_paragraph_fits_the_default_size() -> None:
    """The default size is the bound the manifest records, so no piece may exceed it."""
    pieces = split_long("word " * 2000)
    assert pieces and all(len(piece) <= CHUNK_CHARS for piece in pieces)


def test_a_passage_id_is_stable_for_its_place() -> None:
    """The id names where a passage sits, not what it says, so a rebuild names it identically."""
    one = Passage(OWASP_CHEATSHEETS, PATH, "A", 0, "first wording")
    same_place = Passage(OWASP_CHEATSHEETS, PATH, "A", 0, "second wording")
    assert one.id == same_place.id


def test_passage_ids_differ_by_index() -> None:
    """Two passages from one file are two ids, or the store would keep only the first."""
    ids = {Passage(OWASP_CHEATSHEETS, PATH, "A", index, "text").id for index in range(3)}
    assert len(ids) == 3


def test_a_passage_id_is_a_fixed_length_hex_string() -> None:
    """A stable width, so ids sort and print the same wherever they appear."""
    passage_id = Passage(OWASP_CHEATSHEETS, PATH, "A", 0, "text").id
    assert len(passage_id) == ID_CHARS
    assert int(passage_id, 16) >= 0


def test_chunk_markdown_numbers_passages_in_document_order() -> None:
    """Preamble first with an empty heading, then each section, indices counting up."""
    passages = chunk_markdown(DOCUMENT, OWASP_CHEATSHEETS, PATH)
    assert [(p.index, p.heading) for p in passages] == [(0, ""), (1, "Title"), (2, "Mitigation")]


def test_chunk_markdown_stamps_every_passage_with_its_origin() -> None:
    """Source and path are what the attribution and the public URL are built from."""
    passages = chunk_markdown(DOCUMENT, OWASP_CHEATSHEETS, PATH)
    assert {(p.source, p.path) for p in passages} == {(OWASP_CHEATSHEETS, PATH)}


def test_a_file_holding_only_code_yields_no_passages() -> None:
    """Nothing to ground on is an empty list, not an empty passage."""
    assert chunk_markdown("```\ncode()\n```\n", OWASP_CHEATSHEETS, PATH) == []
