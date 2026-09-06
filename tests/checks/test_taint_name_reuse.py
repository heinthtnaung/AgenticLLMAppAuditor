"""One variable name bound in two scopes, and the probe that used to lie about it.

`_unfollowed` reports a data source this file never bound to a name. Which
sources counted as followed used to be read off a single name-to-surface map
merged across every scope, so two scopes binding the same name kept only the
last -- and the earlier source was published as *"the value was not bound to a
name in this file"*, which was false. It was bound; another function reused the
name. Found on a real repository where two methods of two classes each wrote
`response = requests.get(url)`, and `response` is about as common a name as
Python has, so the false probe fires constantly on real code.

The fix keys the followed set by **surface id**. Both halves of that are held
here, because either alone is passable by a wrong implementation:

* a source whose name another scope reuses gets **no** probe -- the regression;
* a source genuinely never bound still gets one, in a file of the same two-scope
  shape -- without which "emit no probes ever" would pass everything else.

The last test is the guard on the other side: findings were never affected,
because they are judged from the scope-local map, so it passes on both sides of
the fix and would go red if the change had disturbed the per-scope judgement.

Separate from `test_taint.py`, which pins the trace itself and whose scope tests
ask the opposite question (a name reused across scopes must not be *joined*),
and from `test_taint_defect.py`, which is the strict-xfail record of what the
trace still cannot follow. This defect is fixed, so it belongs with the decided
behaviour, not with the recorded holes.

Every snippet is written here rather than read from a repository: what the check
sees is an `ast` tree plus the surfaces the extractor reported, and both are
built in the test.
"""

from artifacts.finding import INCONCLUSIVE, SURFACE_SUBJECT
from artifacts.surface import AGENT_DEF, DATA_SOURCE
from checks.taint import LEFT_THE_FILE
from test_taint import AGENT_NAME, FILE, surface, trace

# Real data-source spellings from `detectors/detector_names.py`, so the snippets
# are shapes the extractor would actually report surfaces for.
HTTP_SOURCE_NAME = "requests.get"
UPLOAD_SOURCE_NAME = "st.file_uploader"

# The published sentence the bug made untrue. Pinned because it is what a reader
# of findings.json sees, and its truth is the whole point of the fix.
NOT_BOUND_DETAIL = "the value was not bound to a name in this file"

# Where each snippet's surfaces sit. Two sources in every file, one per scope.
FIRST_SOURCE_LINE = 2
SECOND_SOURCE_LINE = 6
METHOD_SOURCE_LINES = (3, 8)
AGENT_LINE = 7

SECOND_SOURCE_ID = f"{FILE}:{SECOND_SOURCE_LINE}:{DATA_SOURCE}:{HTTP_SOURCE_NAME}"

# The regression, reduced: two functions, one name, two separate bindings of it.
TWO_FUNCTIONS = '''def fetch_profile(url):
    response = requests.get(url)
    return response.json()

def fetch_orders(url):
    response = requests.get(url)
    return response.json()
'''

# The same shape as it was met in the wild: one `response` per method, and the
# two methods on two different classes.
TWO_METHODS = '''class ProfileClient:
    def fetch(self, url):
        response = requests.get(url)
        return response.json()

class OrderClient:
    def fetch(self, url):
        response = requests.get(url)
        return response.json()
'''

# One scope binds the read to a name; the other throws the value away. The
# second source really is unfollowable, and the probe about it is true.
ONE_SOURCE_UNBOUND = '''def fetch_profile(url):
    response = requests.get(url)
    return response.json()

def ping(url):
    requests.get(url)
'''

# The reused name plus a sink: the second scope hands its own `response` to an
# agent, which is a finding, while the first scope's source reaches nothing.
REUSED_NAME_REACHES_SINK = '''def fetch_profile(url):
    response = requests.get(url)
    return response.json()

def answer(url):
    response = requests.get(url)
    agent = AgentExecutor.from_agent_and_tools(tools=tools)
    agent.invoke(response)
'''

# One name, two *different* sources: an http read and an upload. Same collision
# under a name-keyed set, none at all under an id-keyed one.
TWO_DIFFERENT_SOURCES = '''def fetch_orders(url):
    payload = requests.get(url)
    return payload.json()

def read_upload():
    payload = st.file_uploader("file")
    return payload
'''


def trace_http_reads(source: str, lines: tuple[int, int]) -> tuple:
    """Trace a two-scope snippet that reads an outbound http response at each given line."""
    return trace(source, [surface(DATA_SOURCE, HTTP_SOURCE_NAME, line) for line in lines])


def test_two_functions_binding_the_same_source_name_leave_no_probe() -> None:
    """Both bindings of `response` were followed, so neither source is unexplained."""
    findings, probes = trace_http_reads(TWO_FUNCTIONS,
                                        (FIRST_SOURCE_LINE, SECOND_SOURCE_LINE))
    assert probes == []
    assert findings == []


def test_two_methods_of_two_classes_binding_the_same_name_leave_no_probe() -> None:
    """The shape the bug was found on: a class body is not a scope its methods share."""
    findings, probes = trace_http_reads(TWO_METHODS, METHOD_SOURCE_LINES)
    assert probes == []
    assert findings == []


def test_a_source_the_file_never_named_still_gets_its_probe() -> None:
    """The truthful case, in the same two-scope file: only the unbound source is reported.

    The guard for the two tests above -- without it, a check that emitted no
    probe at all would pass them.
    """
    findings, probes = trace_http_reads(ONE_SOURCE_UNBOUND,
                                        (FIRST_SOURCE_LINE, SECOND_SOURCE_LINE))
    assert findings == []
    assert [(p.subject_kind, p.subject_id, p.outcome, p.reason) for p in probes] == [
        (SURFACE_SUBJECT, SECOND_SOURCE_ID, INCONCLUSIVE, LEFT_THE_FILE)]


def test_that_probe_still_says_the_value_was_never_bound() -> None:
    """The sentence itself: true here, and the thing the collision published falsely."""
    probes = trace_http_reads(ONE_SOURCE_UNBOUND,
                              (FIRST_SOURCE_LINE, SECOND_SOURCE_LINE))[1]
    assert probes[0].detail == NOT_BOUND_DETAIL


def test_two_different_sources_sharing_one_name_are_both_followed() -> None:
    """An http read and an upload both called `payload`: the followed set is keyed by id.

    Keyed by name, these two would still collide even though they are different
    surfaces on different lines.
    """
    findings, probes = trace(TWO_DIFFERENT_SOURCES,
                             [surface(DATA_SOURCE, HTTP_SOURCE_NAME, FIRST_SOURCE_LINE),
                              surface(DATA_SOURCE, UPLOAD_SOURCE_NAME, SECOND_SOURCE_LINE)])
    assert probes == []
    assert findings == []


def test_the_finding_from_the_scope_that_reaches_a_sink_is_unchanged() -> None:
    """Findings were never affected: one finding, anchored on the source in the reaching scope.

    Passes on both sides of the fix by design. The per-scope judgement is not
    what changed, and this is what says so.
    """
    findings, _ = trace(REUSED_NAME_REACHES_SINK,
                        [surface(DATA_SOURCE, HTTP_SOURCE_NAME, FIRST_SOURCE_LINE),
                         surface(DATA_SOURCE, HTTP_SOURCE_NAME, SECOND_SOURCE_LINE),
                         surface(AGENT_DEF, AGENT_NAME, AGENT_LINE)])
    assert [(f.surface_id, f.file, f.line) for f in findings] == [
        (SECOND_SOURCE_ID, FILE, SECOND_SOURCE_LINE)]
