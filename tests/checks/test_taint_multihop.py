"""What following a value past its first hop buys the trace, and what it over-claims.

**Buys:** the trace used to taint a name only where it was bound *at* a source,
so a chain died at its second hop -- `response = requests.get(url)` was followed
and `page_text = response.text` was not. Real code parses, slices and formats a
value before it hands it over, so one hop followed almost nothing. Now a scope's
tainted names are extended to everything derived from them, and the chain below
is one traced flow.

**Over-claims:** the trace has no notion of a sanitiser. A name derived from a
tainted one is tainted, so `safe = sanitise(question)` taints `safe` exactly as
`copy = question` would, and the finding that follows is titled *"Untrusted
input reaches the model without validation"* over a value a validator was called
on. That title is a positive claim the trace cannot back, and the last three
tests here assert it rather than leaving a reader of findings.json to discover
it. Over-approximating is the direction this project chose for a tool that
reports and never patches -- a missed flow is silent, an extra one is on the
page and arguable -- and `docs/TODO.md` carries it under Known defects.

The propagation itself is pinned in `tests/parsing/test_taint_propagation.py`.
What is here is the check around it: the finding, its anchor, and its title.
Every snippet is written in this file, and the surfaces beside it are the ones
the extractor would have reported.
"""

from artifacts.surface import AGENT_DEF, DATA_SOURCE
from checks.taint import TITLE
from test_taint import AGENT_NAME, FILE, SOURCE_NAME, surface, trace

SOURCE_LINE = 1
AGENT_LINE = 2

# A real spelling from `detectors/detector_names.py`: an outbound http read is
# the indirect-injection shape, where the untrusted text is a fetched page.
HTTP_SOURCE_NAME = "requests.get"
HTTP_SOURCE_ID = f"{FILE}:{SOURCE_LINE}:{DATA_SOURCE}:{HTTP_SOURCE_NAME}"

# Read, take the body, cut it down, hand it over: three hops from the source to
# the model, none of which the trace could follow before.
MULTI_HOP = ('response = requests.get(feed_url)\n'
             'agent = AgentExecutor.from_agent_and_tools(tools=tools)\n'
             'page_text = response.text\n'
             'summary = page_text[:200]\n'
             'answer = agent.invoke(summary)\n')

# The same three hops, with the model asked something hardcoded instead. The
# derived names exist and reach nothing, which is a clean result and not a gap.
CHAIN_STOPS_SHORT = ('response = requests.get(feed_url)\n'
                     'agent = AgentExecutor.from_agent_and_tools(tools=tools)\n'
                     'page_text = response.text\n'
                     'summary = page_text[:200]\n'
                     'answer = agent.invoke("what are your opening hours?")\n')

# A validator called on the value, and the same value handed straight over. The
# two differ by one line, and the trace cannot tell them apart.
SANITISED = ('question = st.chat_input("ask")\n'
             'agent = AgentExecutor.from_agent_and_tools(tools=tools)\n'
             'safe = sanitise(question)\n'
             'answer = agent.invoke(safe)\n')

UNSANITISED = ('question = st.chat_input("ask")\n'
               'agent = AgentExecutor.from_agent_and_tools(tools=tools)\n'
               'answer = agent.invoke(question)\n')


def trace_fetched_page(snippet: str) -> tuple:
    """Trace a snippet whose untrusted value is an http response read on line 1."""
    return trace(snippet, [surface(DATA_SOURCE, HTTP_SOURCE_NAME, SOURCE_LINE),
                           surface(AGENT_DEF, AGENT_NAME, AGENT_LINE)])


def trace_chat_input(snippet: str) -> tuple:
    """Trace a snippet whose untrusted value is typed by a user on line 1."""
    return trace(snippet, [surface(DATA_SOURCE, SOURCE_NAME, SOURCE_LINE),
                           surface(AGENT_DEF, AGENT_NAME, AGENT_LINE)])


def only_finding(snippet: str) -> object:
    """The single finding a sanitiser snippet produces, so the two can be compared."""
    findings, _probes = trace_chat_input(snippet)
    assert len(findings) == 1
    return findings[0]


def test_a_value_three_hops_from_its_source_reaches_the_model() -> None:
    """`response.text`, sliced, then invoked: the flow that used to die at hop one."""
    findings, _probes = trace_fetched_page(MULTI_HOP)
    assert [(finding.file, finding.line) for finding in findings] == [(FILE, SOURCE_LINE)]


def test_the_finding_is_anchored_on_the_source_and_not_on_the_last_hop() -> None:
    """The derived name is how it was followed; the source is what is reported."""
    findings, _probes = trace_fetched_page(MULTI_HOP)
    assert findings[0].surface_id == HTTP_SOURCE_ID


def test_a_chain_that_never_reaches_the_model_is_not_reported() -> None:
    """The guard: derived names are not findings, only derived names that arrive are."""
    findings, probes = trace_fetched_page(CHAIN_STOPS_SHORT)
    assert findings == []
    assert probes == []


def test_a_value_a_sanitiser_was_called_on_is_still_reported() -> None:
    """`safe = sanitise(question)` taints `safe`: nothing here knows what that call did.

    The cost of following a value past its first hop, stated as a test so it is
    met here rather than in an argument about a finding.
    """
    findings, _probes = trace_chat_input(SANITISED)
    assert [(finding.file, finding.line) for finding in findings] == [(FILE, SOURCE_LINE)]


def test_that_finding_still_claims_the_value_reached_the_model_unvalidated() -> None:
    """The exact sentence the artifact publishes over a value a validator was called on."""
    assert only_finding(SANITISED).title == TITLE == \
        "Untrusted input reaches the model without validation"


def test_the_sanitised_flow_is_reported_exactly_like_the_unsanitised_one() -> None:
    """Same anchor, same rule, same title: the trace draws no distinction at all."""
    sanitised = only_finding(SANITISED)
    unsanitised = only_finding(UNSANITISED)
    assert (sanitised.surface_id, sanitised.rule_id, sanitised.title) == \
        (unsanitised.surface_id, unsanitised.rule_id, unsanitised.title)
