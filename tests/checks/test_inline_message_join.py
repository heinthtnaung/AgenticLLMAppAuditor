"""The detector and the probe describing the same inline chat message.

The change shipped in two halves that only work together.
`detectors._prompt_from_inline_message` reports the message dict as a surface,
and `semantic_probe._message_text` reads the `content` value back off the same
line. Nothing in either module checks the other, and both read the key from one
constant precisely because a second copy is how they would drift apart.

Drift has a direction, and both ways are bad:

* the detector reports a message the probe cannot read, so the surface comes
  back inconclusive forever -- reported and never judged;
* the probe reads text at a line the detector reported for something else, so a
  model is asked about one thing and the finding is filed against another.

So this file asserts the join rather than either side: for one app holding one
untrusted message, every prompt surface the detector reports is a message the
probe reads text for, that text is the text written on the line the surface
names, and the finding lands on that line.

The app is the shape this was measured on -- an OpenAI-style call whose user
message interpolates scraped page text -- reduced and written into `tmp_path`.
Note what it does *not* contain: no `ChatPromptTemplate`, no prompt-shaped
variable, nothing the extractor saw before. Every prompt surface below exists
because of the new extractor, so an app like this reported no LLM01 at all.

A synthetic app is weaker than the real one: one small file, no oversized
source, no shape nobody thought of, and no repository this project does not own.
"""

from artifacts.finding import CONFIRMED, PROBE, REFUTED
from artifacts.surface import AGENT_DEF, PROMPT_TEMPLATE
from checks.semantic_probe import prompt_surfaces, run_over_repo, template_text
from parsing.extractor_python import parse_file
from semantic_probe_fixtures import FILE, Answering, app_and_surfaces

# The measured shape: a page is fetched elsewhere and its text is dropped into
# the user message. `OpenAI()` is an AGENT_DEF, so the app is a real one and the
# surface count below cannot be met by the prompts alone.
INLINE_MESSAGE_APP = '''from openai import OpenAI

client = OpenAI()


def summarise(page_text):
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You summarise web pages."},
            {"role": "user", "content": f"Summarise this page: {page_text}"},
        ],
    )
'''

# Where everything is, spelled out so a finding on the wrong line cannot pass.
CLIENT_LINE = 3
SYSTEM_MESSAGE_LINE = 10
USER_MESSAGE_LINE = 11
APP_SURFACES = 3

INLINE_NAME = "inline_message"

# What the probe must read at each of those lines, character for character.
SYSTEM_TEXT = "You summarise web pages."
USER_TEXT = "Summarise this page: {page_text}"

USER_SURFACE_ID = f"{FILE}:{USER_MESSAGE_LINE}:{PROMPT_TEMPLATE}:{INLINE_NAME}"

# What a model answers when it is asked. Fixed here, because what the model
# decides is not the subject: where the answer is filed is.
VULNERABLE_REPLY = "VULNERABLE\nThe page text is dropped into the instructions."
VULNERABLE_RATIONALE = "The page text is dropped into the instructions."


def probe_the_app(tmp_path) -> tuple[list, list, Answering]:
    """Audit the app with a stand-in model that flags whatever it is shown."""
    repo, surfaces = app_and_surfaces(tmp_path, INLINE_MESSAGE_APP)
    ask = Answering(VULNERABLE_REPLY)
    findings, probes = run_over_repo(str(repo), surfaces, ask)
    return findings, probes, ask


def test_every_prompt_surface_in_the_app_is_an_inline_message(tmp_path) -> None:
    """Non-vacuity, and the point of the change: nothing here was a prompt surface before.

    The counts are literals. An extraction that found nothing, or that found the
    client twice, cannot satisfy them.
    """
    _repo, surfaces = app_and_surfaces(tmp_path, INLINE_MESSAGE_APP)
    assert len(surfaces) == APP_SURFACES
    # By line, because the extractor returns them per detector, not per line.
    assert sorted((s.kind, s.name, s.line) for s in surfaces) == [
        (AGENT_DEF, "OpenAI", CLIENT_LINE),
        (PROMPT_TEMPLATE, INLINE_NAME, SYSTEM_MESSAGE_LINE),
        (PROMPT_TEMPLATE, INLINE_NAME, USER_MESSAGE_LINE),
    ]


def test_the_probe_reads_the_text_written_on_the_line_each_surface_names(tmp_path) -> None:
    """The join itself: same line, same text, so both halves describe one message.

    The second assertion is the drift guard. It does not trust the expected
    strings above: it takes the text the probe read and looks for it in the
    source line the *detector* anchored the surface on.
    """
    repo, surfaces = app_and_surfaces(tmp_path, INLINE_MESSAGE_APP)
    tree = parse_file(repo / FILE)
    written = INLINE_MESSAGE_APP.splitlines()
    read = {s.line: template_text(tree, s.line) for s in prompt_surfaces(surfaces, FILE)}
    assert read == {SYSTEM_MESSAGE_LINE: SYSTEM_TEXT, USER_MESSAGE_LINE: USER_TEXT}
    for line, text in read.items():
        assert text in written[line - 1]


def test_every_message_the_detector_reported_was_actually_judged(tmp_path) -> None:
    """No surface comes back "not written literally at this line", which is what drift looks like.

    A probe with a reason is one that concluded nothing. Both of these concluded
    -- one by the model, one from the text alone -- so the two halves agreed
    about every surface in the file.
    """
    _findings, probes, _ask = probe_the_app(tmp_path)
    assert sorted((p.subject_id, p.outcome, p.reason) for p in probes) == [
        (f"{FILE}:{SYSTEM_MESSAGE_LINE}:{PROMPT_TEMPLATE}:{INLINE_NAME}", REFUTED, None),
        (USER_SURFACE_ID, CONFIRMED, None),
    ]


def test_the_message_carrying_page_text_is_confirmed_as_llm01_at_its_own_line(tmp_path) -> None:
    """One finding, on the line where outside text reaches the model, citing the probe for it."""
    findings, probes, _ask = probe_the_app(tmp_path)
    assert len(findings) == 1
    finding = findings[0]
    confirmed = [probe for probe in probes if probe.outcome == CONFIRMED]
    assert len(confirmed) == 1
    assert (finding.owasp_id, finding.detection) == ("LLM01", PROBE)
    assert (finding.file, finding.line) == (FILE, USER_MESSAGE_LINE)
    assert (finding.surface_kind, finding.surface_name) == (PROMPT_TEMPLATE, INLINE_NAME)
    assert finding.surface_id == USER_SURFACE_ID
    assert finding.probe_id == confirmed[0].id
    assert confirmed[0].detail == VULNERABLE_RATIONALE


def test_the_model_is_asked_about_the_interpolating_message_and_no_other(tmp_path) -> None:
    """The static message is settled without a request, so exactly one prompt is sent.

    Without this, a check that asked about everything and filed one finding by
    luck would pass the test above.
    """
    _findings, _probes, ask = probe_the_app(tmp_path)
    assert len(ask.prompts) == 1
    assert USER_TEXT in ask.prompts[0]
    assert SYSTEM_TEXT not in ask.prompts[0]
