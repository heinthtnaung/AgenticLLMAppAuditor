"""Splits a Markdown document into passages a retriever can index, by heading.

Pure functions: text in, passages out, so the whole module is testable without
a store or an embedding model. A passage is the prose under one heading, cut
into pieces of bounded size. Fenced code and tables are dropped on purpose --
advice grounded on a code block invites the model to echo it into a snippet the
contract then refuses, and the retriever wants the *mitigation*, which is prose.
"""

import hashlib
import re
from dataclasses import dataclass

# Passage size, in characters. Recorded in the manifest so the passage count
# an index reports can be recomputed from the same files.
CHUNK_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200

# Headings down to four levels; deeper ones are treated as prose.
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
# A fence opens with three or more backticks and closes only on a line with at
# least as many: a block showing Markdown may hold ``` lines inside ````, and
# a plain toggle would close the outer block on the first inner one. A line
# with another backtick after the opener is not a fence but inline code on a
# line of its own -- the same CommonMark rule, and the Cheat Sheets have both.
FENCE = re.compile(r"^\s*(`{3,})[^`]*$")
# Code quoted inline with triple backticks mid-sentence is still code.
INLINE_CODE = re.compile(r"```.*?```")
TABLE_ROW = "|"
# The Cheat Sheets use `---` as a horizontal rule mid-file, never as
# front-matter; either way it carries no prose.
RULE = "---"
PARAGRAPH_BREAK = "\n\n"
ID_CHARS = 32


@dataclass(frozen=True)
class Passage:
    """One indexable piece of prose, and where in the source it came from."""

    source: str
    path: str
    heading: str
    index: int
    text: str

    @property
    def id(self) -> str:
        """A stable id from the passage's place, so a rebuild names it identically."""
        key = f"{self.source}:{self.path}:{self.index}".encode("utf-8")
        return hashlib.sha256(key).hexdigest()[:ID_CHARS]


def strip_code_and_tables(lines: list[str]) -> list[str]:
    """Drop fenced code blocks, table rows and horizontal rules, keeping the prose."""
    kept, open_fence = [], 0
    for line in lines:
        fence = FENCE.match(line)
        if fence and not open_fence:
            open_fence = len(fence.group(1))
            continue
        if fence and len(fence.group(1)) >= open_fence:
            open_fence = 0
            continue
        if open_fence or line.lstrip().startswith(TABLE_ROW) or line.strip() == RULE:
            continue
        kept.append(INLINE_CODE.sub("", line))
    return kept


def sections(lines: list[str]) -> list[tuple[str, str]]:
    """Group prose under its nearest heading: (heading, text) pairs, in order.

    Text before the first heading gets an empty heading rather than being lost.
    """
    grouped: list[tuple[str, list[str]]] = [("", [])]
    for line in lines:
        match = HEADING.match(line)
        if match:
            grouped.append((match.group(2), []))
            continue
        grouped[-1][1].append(line)
    joined = [(heading, "\n".join(body).strip()) for heading, body in grouped]
    return [(heading, body) for heading, body in joined if body]


def split_long(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Cut one section into pieces of at most `size` characters.

    Paragraphs are kept whole while they fit; a lone paragraph longer than the
    size is sliced, with `overlap` characters repeated so a sentence cut in two
    is whole in at least one piece.
    """
    if len(text) <= size:
        return [text]
    pieces, current = [], ""
    for paragraph in text.split(PARAGRAPH_BREAK):
        if len(paragraph) > size:
            pieces += _flush(current) + _slice(paragraph, size, overlap)
            current = ""
        elif len(current) + len(paragraph) + len(PARAGRAPH_BREAK) > size:
            pieces += _flush(current)
            current = paragraph
        else:
            current = f"{current}{PARAGRAPH_BREAK}{paragraph}" if current else paragraph
    return pieces + _flush(current)


def _flush(current: str) -> list[str]:
    """The pending piece as a list, or nothing when there is none."""
    return [current] if current else []


def _slice(paragraph: str, size: int, overlap: int) -> list[str]:
    """Hard-cut an oversized paragraph into overlapping windows."""
    step = size - overlap
    return [paragraph[start:start + size] for start in range(0, len(paragraph), step)
            if paragraph[start:start + size].strip()]


def chunk_markdown(text: str, source: str, path: str) -> list[Passage]:
    """Turn one Markdown file into its passages, numbered in document order."""
    passages, index = [], 0
    for heading, body in sections(strip_code_and_tables(text.splitlines())):
        for piece in split_long(body):
            passages.append(Passage(source, path, heading, index, piece))
            index += 1
    return passages
