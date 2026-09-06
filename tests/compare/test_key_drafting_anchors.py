"""`code_anchor` is quoted from the source on disk, or it is empty.

An anchor is a quotation: it lets a human open the file the entry names and see
the line it is about, and it lets a later reader tell whether the key still
describes the code. So it is **read**, never asked of the model -- a model asked
to quote source it was not shown invents something plausible, and invented text
in that field is worse than none, because it reads exactly like a real one.

The two ways reading can fail are the two tests at the bottom: a line past the
end of the file, and a file that cannot be read at all. Both answer `""`, which
is a fact a human can act on.

Every file here is written into `tmp_path` by the test that reads it. The
lengths are asserted as literals, because "the first 60 characters" and "the
whole line" are the same assertion on any line shorter than 60.
"""

from key_drafting import CODE_ANCHOR_LENGTH, anchored

FILE = "agent.py"

# An indented line 80 characters long once trimmed, so both halves of
# `line.strip()[:60]` have something to do.
LONG_LINE = '    prompt = ChatPromptTemplate.from_template("You are a support agent. {question}")'
LONG_LINE_NUMBER = 2
LONG_ANCHOR = 'prompt = ChatPromptTemplate.from_template("You are a support'

# A short line, to show the anchor is a prefix and never a padding.
SHORT_LINE = "    shell = ShellTool()"
SHORT_LINE_NUMBER = 3
SHORT_ANCHOR = "shell = ShellTool()"

# Exactly one character too long, which is where an off-by-one lives.
BOUNDARY_LINE = "y" * (CODE_ANCHOR_LENGTH + 1)
BOUNDARY_LINE_NUMBER = 4

SOURCE = f"import os\n{LONG_LINE}\n{SHORT_LINE}\n{BOUNDARY_LINE}\n"
LINE_COUNT = 4


def entry(line: int, file: str = FILE) -> dict:
    """One drafted entry naming a file and a line, and nothing about the source there."""
    return {"id": "K-01", "file": file, "line": line, "owasp_id": "LLM01",
            "title": "t", "description": "d"}


def anchor_for(tmp_path, line: int, file: str = FILE) -> str:
    """Write the source file, anchor one entry against it, and return the anchor."""
    (tmp_path / FILE).write_text(SOURCE, encoding="utf-8")
    return anchored([entry(line, file)], tmp_path)[0]["code_anchor"]


# --- what it quotes -----------------------------------------------------------

def test_the_anchor_is_the_trimmed_start_of_the_line_it_names(tmp_path) -> None:
    """Trimmed and cut to sixty: an anchor identifies a line, it does not reproduce it."""
    assert anchor_for(tmp_path, LONG_LINE_NUMBER) == LONG_ANCHOR


def test_the_anchor_of_a_long_line_is_exactly_sixty_characters(tmp_path) -> None:
    """The literal above is what it is; this is the length claim, stated on its own."""
    assert len(anchor_for(tmp_path, LONG_LINE_NUMBER)) == CODE_ANCHOR_LENGTH == 60


def test_a_short_line_is_quoted_whole(tmp_path) -> None:
    """The off position: sixty is a cap, not a width, so nothing is padded to it."""
    assert anchor_for(tmp_path, SHORT_LINE_NUMBER) == SHORT_ANCHOR


def test_a_line_one_character_too_long_loses_exactly_that_character(tmp_path) -> None:
    """Where an off-by-one would hide: sixty-one in, sixty out."""
    assert anchor_for(tmp_path, BOUNDARY_LINE_NUMBER) == "y" * CODE_ANCHOR_LENGTH


def test_the_last_line_of_the_file_is_still_in_range(tmp_path) -> None:
    """Guard for the refusal below: the bound is the line count, not one less."""
    assert anchor_for(tmp_path, LINE_COUNT) != ""


# --- the entry it is added to -------------------------------------------------

def test_the_rest_of_the_entry_is_carried_through(tmp_path) -> None:
    """Anchoring adds one field; the entry the model wrote is otherwise untouched."""
    (tmp_path / FILE).write_text(SOURCE, encoding="utf-8")
    given = entry(SHORT_LINE_NUMBER)
    filled = anchored([given], tmp_path)[0]
    assert {name: filled[name] for name in given} == given


def test_the_entry_handed_in_is_not_modified(tmp_path) -> None:
    """A new dict per entry, so the caller's list is input and not also output."""
    (tmp_path / FILE).write_text(SOURCE, encoding="utf-8")
    given = entry(SHORT_LINE_NUMBER)
    anchored([given], tmp_path)
    assert "code_anchor" not in given


def test_every_entry_is_anchored(tmp_path) -> None:
    """Guard: a document where only the first entry carries an anchor would pass the rest."""
    (tmp_path / FILE).write_text(SOURCE, encoding="utf-8")
    filled = anchored([entry(SHORT_LINE_NUMBER), entry(LONG_LINE_NUMBER)], tmp_path)
    assert [one["code_anchor"] for one in filled] == [SHORT_ANCHOR, LONG_ANCHOR]


# --- when the source cannot be quoted -----------------------------------------

def test_a_line_past_the_end_of_the_file_anchors_nothing(tmp_path) -> None:
    """The model named a line the file does not have; an invented quotation is the alternative."""
    assert anchor_for(tmp_path, LINE_COUNT + 1) == ""


def test_a_file_that_is_not_there_anchors_nothing(tmp_path) -> None:
    """A moved or deleted file is a missing anchor, never a raised OSError mid-draft."""
    assert anchor_for(tmp_path, 1, file="gone.py") == ""


def test_a_file_that_cannot_be_read_anchors_nothing(tmp_path) -> None:
    """A directory where a file was named: unreadable is unreadable, whatever the reason."""
    (tmp_path / "package").mkdir()
    assert anchor_for(tmp_path, 1, file="package") == ""
