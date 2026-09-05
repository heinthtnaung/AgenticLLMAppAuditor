"""One finding's block in remediation.md, and the note that stands over every snippet.

`ILLUSTRATION_NOTE` is the rendering half of the mechanism that replaced the
outright ban on model-written fixes, so no fenced block may appear without it
directly above. The refused case matters as much: the report says a refusal was
recorded, and shows none of what was refused.

The last group is the `Grounded on` block, which says what an entry's advice
was based on. Its shape is load-bearing rather than cosmetic: `markdown_html.py`
is a deliberate subset that reads a bullet only at column zero, and an indented
one fell through to a paragraph there and shipped its `- ` marks as text into
the HTML and the PDF. So the label is asserted to hold a line of its own and
every citation to be its flat sibling.
"""

from artifacts.remediation import NAMES_APP_IDENTIFIER, UNAVAILABLE, advice_entry
from artifacts.remediation import MODEL_UNAVAILABLE as UNAVAILABLE_REASON
from checks.advise import advise_all
from cli_helpers import stub_model
from findings_fixtures import OWASP_ID, build_document, static_finding
from parsing.languages import PYTHON
from remediation_fixtures import (
    CLEAN_GUIDANCE,
    rejected_entry,
    remediation_document,
    snippet,
    source,
    unavailable_run,
    written_entry,
)
from remediation_report import GROUNDED_ON, ILLUSTRATION_NOTE, render
from retrieval.owasp_reference import reference_for

APP = "vulnerable-support-agent"

# A phrase no finding and no heading contains, so its absence proves the refused
# answer itself was never rendered.
MARKER = "quisquilia"
LEAKING_ANSWER = f"Narrow it, {MARKER}.\n\n```python\nrunner = ShellTool()\n```"

# Fence info strings that would read as "apply this" whatever the note said.
APPLICABLE_INFO_STRINGS = ("diff", "patch")

# The bullet marker the report writes and the converter recognises, at column
# zero and nowhere else.
BULLET = "- "


def findings_document() -> dict:
    """One finding, built through its real producer."""
    return build_document([static_finding()])


def finding_id() -> str:
    """The id both artifacts join on."""
    return findings_document()["findings"][0]["finding_id"]


def render_entries(entries: list[dict], provenance: dict | None = None) -> str:
    """Render a report over the single finding above."""
    return render(APP, remediation_document(entries, provenance), findings_document())


def citations(text: str) -> list[str]:
    """Every bullet under the `Grounded on` label, in order, with its marker stripped."""
    lines = text.splitlines()
    found = []
    for line in lines[lines.index(GROUNDED_ON) + 1:]:
        if line.startswith(BULLET):
            found.append(line[len(BULLET):])
            continue
        if line.strip():
            break
    return found


def opening_fences(text: str) -> list[tuple[int, str]]:
    """Return the line index and info string of every fence that opens a block."""
    opens, inside = [], False
    for index, line in enumerate(text.splitlines()):
        if not line.startswith("```"):
            continue
        if not inside:
            opens.append((index, line[3:]))
        inside = not inside
    return opens


def nearest_line_above(lines: list[str], index: int) -> str:
    """Return the closest non-blank line above the given one."""
    above = [line for line in lines[:index] if line.strip()]
    return above[-1] if above else ""


def test_a_written_entry_shows_the_guidance_the_model_wrote() -> None:
    """Advice a reader cannot see is advice that was not written."""
    assert CLEAN_GUIDANCE in render_entries([written_entry(finding_id())])


def test_a_written_entry_shows_its_snippet_in_a_fenced_block() -> None:
    """The illustration is rendered as code, labelled with the language it claims."""
    text = render_entries([written_entry(finding_id())])
    assert "```python" in text
    assert "checked = approve(value)" in text


def test_every_fenced_block_sits_directly_under_the_illustration_note() -> None:
    """The note is what tells a reader the block is not a patch, so none may skip it."""
    text = render_entries([written_entry(finding_id())])
    lines = text.splitlines()
    fences = opening_fences(text)
    assert fences
    for index, _ in fences:
        assert nearest_line_above(lines, index) == ILLUSTRATION_NOTE


def test_the_note_is_rendered_once_for_each_snippet() -> None:
    """Two illustrations means two notes, not one heading covering both."""
    pair = [snippet(), snippet("value = fetch_text()")]
    text = render_entries([written_entry(finding_id(), snippets=pair)])
    assert text.count(ILLUSTRATION_NOTE) == 2


def test_the_note_says_nothing_here_has_been_applied() -> None:
    """The no-auto-fixing boundary is stated where a reader meets the code."""
    assert "nothing here has been applied" in ILLUSTRATION_NOTE


def test_no_fenced_block_claims_to_be_a_diff_or_a_patch() -> None:
    """An info string of `diff` reads as "apply this" however the note is worded."""
    text = render_entries([written_entry(finding_id())])
    assert all(info not in APPLICABLE_INFO_STRINGS for _, info in opening_fences(text))


def test_a_written_entry_with_no_snippet_renders_no_fence() -> None:
    """Prose alone is a complete answer, and must not produce an empty code block."""
    text = render_entries([written_entry(finding_id(), snippets=[])])
    assert opening_fences(text) == []


def test_a_refused_entry_names_the_reason_it_was_refused() -> None:
    """A refusal is recorded rather than hidden, so the reason is on the page."""
    text = render_entries([rejected_entry(finding_id(), NAMES_APP_IDENTIFIER)])
    assert NAMES_APP_IDENTIFIER in text
    assert "No advice is shown here" in text


def test_a_refused_entry_shows_none_of_the_answer_that_was_refused(monkeypatch) -> None:
    """End to end with a stubbed model: the leaking answer never reaches the page."""
    stub_model(monkeypatch, LEAKING_ANSWER)
    entries = advise_all(findings_document()["findings"], PYTHON)
    text = render_entries(entries)
    assert MARKER not in text
    assert "runner =" not in text
    assert NAMES_APP_IDENTIFIER in text


def test_a_refused_entry_renders_no_fenced_block_at_all() -> None:
    """Nothing survives a refusal, so there is no illustration to stand a note over."""
    text = render_entries([rejected_entry(finding_id(), NAMES_APP_IDENTIFIER)])
    assert opening_fences(text) == []


def test_an_entry_no_model_answered_says_it_was_not_attempted() -> None:
    """An unasked finding must read differently from an answered and refused one."""
    entry = advice_entry(finding_id(), UNAVAILABLE, UNAVAILABLE_REASON)
    text = render_entries([entry], unavailable_run())
    assert "**Not attempted**" in text
    assert UNAVAILABLE_REASON in text


def test_each_block_is_headed_by_the_risk_class_and_the_title() -> None:
    """The reader meets the finding before the advice, in the findings' own words."""
    finding = findings_document()["findings"][0]
    text = render_entries([written_entry(finding_id())])
    assert f"### {finding['owasp_id']} — {finding['title']}" in text


def test_each_block_names_where_the_finding_is_and_which_finding_it_is() -> None:
    """The location comes from the finding, and the id is the join key into findings.json."""
    text = render_entries([written_entry(finding_id())])
    assert "`app/agent.py:12`" in text
    assert f"`{finding_id()}`" in text


def test_the_grounded_on_label_stands_on_a_line_of_its_own() -> None:
    """The converter reads a bullet only at column zero, so the label may share no line."""
    assert GROUNDED_ON in render_entries(
        [written_entry(finding_id(), sources=[source()])]).splitlines()


def test_no_citation_is_rendered_as_an_indented_bullet() -> None:
    """An indented bullet fell through to a paragraph and shipped its marker as text."""
    lines = render_entries([written_entry(finding_id(), sources=[source()])]).splitlines()
    assert not [line for line in lines
                if line.lstrip().startswith(BULLET) and not line.startswith(BULLET)]


def test_the_owasp_reference_is_the_first_thing_the_advice_is_grounded_on() -> None:
    """It is a constant of this tool rather than a passage a run retrieved, so it leads."""
    reference = reference_for(OWASP_ID)
    first = citations(render_entries([written_entry(finding_id(), sources=[source()])]))[0]
    assert first.startswith(reference.source)
    assert reference.url in first


def test_each_retrieved_passage_is_cited_with_its_path_heading_and_link() -> None:
    """A citation a reader cannot open is an attribution in name only."""
    passage = source()
    cited = citations(render_entries([written_entry(finding_id(), sources=[passage])]))[1]
    assert passage["path"] in cited
    assert passage["heading"] in cited
    assert passage["url"] in cited


def test_one_bullet_is_rendered_for_each_passage_that_was_cited() -> None:
    """Two passages rolled into one bullet would hide which text grounded what."""
    passages = [source(), source(heading="Output Encoding")]
    cited = citations(render_entries([written_entry(finding_id(), sources=passages)]))
    assert len(cited) == len(passages) + 1


def test_an_entry_that_retrieved_nothing_still_names_the_risk_class_entry() -> None:
    """The reference is injected whether or not an index exists, so it is never absent."""
    cited = citations(render_entries([written_entry(finding_id())]))
    assert cited == [f"{reference_for(OWASP_ID).source} — {reference_for(OWASP_ID).url}"]
