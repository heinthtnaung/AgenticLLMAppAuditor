"""The live check writes an answer file only for a run that is handed one.

A page whose runs take no answers need not print an answer file, and a run that
is handed one on a page printing none is refused by name. Both pages checked
today print one, so only a page built here can show it. The scan itself is
replaced by a recorder: what is asked is which command the check would run, and
no Syft, Trivy or corpus is needed to say that.
"""

from pathlib import Path

import pytest

import doc_live
from doc_markers import MARKER_NAME, RUN_DIRECTIVE
from doc_pages import Document, Page
from doc_runs import ANSWERS_FLAG, ELIDED_TOKEN, REPOSITORY, printed_runs

PRINTED = f"```\nAudit of {REPOSITORY}\n```\n"
UNANSWERED_RUN = f"<!-- {MARKER_NAME}: {RUN_DIRECTIVE} {ELIDED_TOKEN} -->\n{PRINTED}"
ANSWERED_RUN = f"<!-- {MARKER_NAME}: {RUN_DIRECTIVE} {ANSWERS_FLAG} -->\n{PRINTED}"
NO_ANSWER_BLOCK = "marks 0 'answers' blocks"


class RecordedAudits:
    """Stand in for the scan, keeping each command the check would have run."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], tmp_path: Path) -> list[str]:
        """Keep one command and print nothing, as a scan that found nothing would."""
        self.commands.append(command)
        return []


def one_run_page(tmp_path: Path, text: str) -> Page:
    """Give a page marking one run and printing no answer file."""
    document = Document(tmp_path / "PAGE.md", run_blocks=1, unmarked_tool_output=0)
    return Page(document, text)


def test_a_run_handed_no_answer_file_runs_on_a_page_that_prints_none(tmp_path, monkeypatch):
    recorded = RecordedAudits()
    monkeypatch.setattr(doc_live, "audited", recorded)
    page = one_run_page(tmp_path, UNANSWERED_RUN)
    (run,) = printed_runs(page)
    doc_live.output_of(run, page, tmp_path)
    assert ANSWERS_FLAG not in recorded.commands[0]


def test_a_run_handed_an_answer_file_on_a_page_that_prints_none_is_refused(tmp_path, monkeypatch):
    recorded = RecordedAudits()
    monkeypatch.setattr(doc_live, "audited", recorded)
    page = one_run_page(tmp_path, ANSWERED_RUN)
    (run,) = printed_runs(page)
    with pytest.raises(ValueError, match=NO_ANSWER_BLOCK):
        doc_live.output_of(run, page, tmp_path)
    assert recorded.commands == []
