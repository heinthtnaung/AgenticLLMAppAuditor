"""LLM02: which surface a query built at runtime is reported against.

The other half of `checks/output_handling.py`. Whether a query is interpolated
is settled in `test_output_handling.py`; this file asks the second question --
*given a call the check dislikes, which surface does the finding land on?* A
finding is anchored on a `DATA_SOURCE` surface because that is what a grading
key records, so anchoring it on the wrong one is a false positive with a real
file and line attached, which is the expensive kind.

The join is on the file, the line and the full dotted name. It was on the bare
method until 2026-09-05, and joining on `execute` alone let `cursor.execute`'s
verdict be anchored on `audit.execute`'s surface as well;
`test_a_constant_query_beside_an_interpolated_one_is_not_reported` is the only
test in either file that catches the join widening back.

Surfaces come from the real Python detector wherever the detector emits one, so
what a finding is anchored to is what an audit would actually have had. Two
tests hand-build a surface instead, because the case they pin -- `db.preexecute`
-- is one the detector will never produce. Those two now assert the behaviour
only: the full-name join refuses that name before `_method_of` is consulted, so
the segment rule is tested directly on the helper instead.

What this tree cannot show: it is written here, so it holds no file the walker
sizes out and no non-UTF-8 source. The unparseable file below is the one I/O
edge it does reproduce.
"""

from artifacts.surface import DATA_SOURCE, Surface
from checks.output_handling import (
    EXECUTE_METHODS, _method_of, find_in_tree, run_over_repo)
from detectors.detector_names import DATA_SOURCE_METHODS
from output_handling_fixtures import (
    CONSTANT_QUERY, FILE, INTERPOLATED_QUERY, QUERY_LINE, audit_source,
    execute_anchors, findings_anchored_on, surfaces_and_findings)
from parsing.extractor_python import extract_file, parse_file
from parsing.languages import PYTHON

OTHER_FILE = "other.py"
BROKEN_FILE = "bad.py"

# Two interpolated execute calls sharing one line, and so one surface identity.
TWO_QUERIES_ONE_LINE = '''def read(cursor, first, second):
    cursor.execute(f"SELECT {first}"); cursor.execute(f"SELECT {second}")
'''

# Two execute calls on one line on *different* receivers, only one of which
# builds its text. Joining on the bare method reported both.
CONSTANT_QUERY_BESIDE_INTERPOLATED = '''def read(cursor, audit, user_id):
    cursor.execute(f"SELECT {user_id}"); audit.execute("SELECT 1")
'''

# A method whose name merely ends in `execute`. `endswith` reads it as one.
PREEXECUTE_QUERY = '''def read(db, user_id):
    db.preexecute(f"SELECT * FROM t WHERE id = '{user_id}'")
'''

# The same name sharing a line with a genuine interpolated `execute`, so there
# is something at that line for a wrong match to borrow.
PREEXECUTE_BESIDE_EXECUTE = '''def read(db, cursor, user_id):
    db.preexecute(f"SELECT {user_id}"); cursor.execute(f"SELECT {user_id}")
'''

# An interpolated query the detector reports no surface for: the receiver is not
# a name, so there is nothing for a finding to be anchored on.
RECEIVERLESS_QUERY = '''def read(user_id):
    execute(f"SELECT * FROM t WHERE id = '{user_id}'")
'''

# Parameterised rows around a table name that is not: still built at runtime.
EXECUTEMANY_QUERY = '''def write(cursor, table, rows):
    cursor.executemany(f"INSERT INTO {table} VALUES (?)", rows)
'''

# Python the extractor already recorded as unparseable in surfaces.json.
BROKEN_SOURCE = "def oops(:\n"

# The surface the detector emits for `db.preexecute(...)` -- which it does not,
# which is why the two tests using it build it by hand.
PREEXECUTE_SURFACE = Surface(
    DATA_SOURCE, "db.preexecute", FILE, QUERY_LINE, PYTHON, "database query")

# The spellings EXECUTE_METHODS must keep: without them the subset test below
# would also pass over an emptied set.
ANCHOR_EXECUTE_METHODS = frozenset({"execute", "executemany"})


def test_the_finding_is_anchored_on_the_execute_surface(tmp_path) -> None:
    """A grading key records the finding at the surface, so the surface is copied whole."""
    reported = audit_source(tmp_path, INTERPOLATED_QUERY)[0]
    assert (reported.surface_kind, reported.surface_name) == (DATA_SOURCE, "cursor.execute")
    assert reported.surface_id == f"{FILE}:{QUERY_LINE}:{DATA_SOURCE}:cursor.execute"


def test_a_constant_query_beside_an_interpolated_one_is_not_reported(tmp_path) -> None:
    """Two receivers on one line: only the call that builds its text is reported.

    This is why the join is on the whole dotted name. On `execute` alone,
    `cursor.execute(f"...")` put `execute` in the line's set and `audit.execute`
    matched it, so a query written out in full was reported as "built by string
    interpolation". Both surfaces exist here, so a wrong match has somewhere to
    land -- without the second surface the test would prove nothing.
    """
    surfaces, findings = surfaces_and_findings(tmp_path, CONSTANT_QUERY_BESIDE_INTERPOLATED)
    assert execute_anchors(surfaces) == [("audit.execute", QUERY_LINE),
                                         ("cursor.execute", QUERY_LINE)]
    assert [(f.surface_name, f.line) for f in findings] == [("cursor.execute", QUERY_LINE)]


def test_two_interpolated_queries_on_one_line_are_one_finding(tmp_path) -> None:
    """One surface identity is one finding: a second would share its id and be refused.

    `Finding.id` is `surface_id:rule_id`, and two findings sharing an id make
    `build_findings_document` raise, so the whole audit would be lost to it.
    """
    findings = audit_source(tmp_path, TWO_QUERIES_ONE_LINE)
    assert len(findings) == 1
    assert len({f.id for f in findings}) == 1


def test_a_method_whose_name_merely_ends_in_execute_is_not_matched(tmp_path) -> None:
    """`db.preexecute` reports nothing, which is the contract however it is enforced.

    The detector emits no surface for this name, so the anchor is built by hand
    -- otherwise the test would pass for want of a surface rather than because
    the name was refused.

    What this no longer proves: since the join moved to the full dotted name,
    `_method_of` reading a suffix instead of a segment cannot change this
    result, because `db.preexecute` still matches no name in the line's set.
    The segment rule itself is pinned by `test_the_method_of_a_surface_name_is_
    its_last_segment` below -- verified by mutation, this test passes with
    `_method_of` broken.
    """
    assert findings_anchored_on(tmp_path, PREEXECUTE_QUERY, [PREEXECUTE_SURFACE]) == []


def test_a_preexecute_surface_does_not_borrow_the_execute_call_on_its_line(tmp_path) -> None:
    """The twin of the test above, with a real interpolated `execute` at the same line.

    This shape used to be the only one that could catch a suffix match, back
    when the line's set held bare methods and `execute` was in it. The set now
    holds `cursor.execute`, which `db.preexecute` cannot match under either
    rule, so what is left here is the behaviour, not the mechanism.
    """
    findings = findings_anchored_on(
        tmp_path, PREEXECUTE_BESIDE_EXECUTE, [PREEXECUTE_SURFACE])
    assert findings == []


def test_the_method_of_a_surface_name_is_its_last_segment() -> None:
    """The segment rule, tested where it can still be discriminated: on the helper itself.

    `_method_of` is now a pre-filter that the full-name join stands behind, so
    no end-to-end test fails when it reads a suffix. Called directly, it does.
    """
    assert _method_of("db.preexecute") == "preexecute"
    assert _method_of("cursor.execute") == "execute"
    assert _method_of("execute") == "execute"


def test_an_execute_call_with_no_surface_at_its_line_is_not_reported(tmp_path) -> None:
    """A finding is anchored on a surface, so a call the detector never reported has none."""
    path = tmp_path / FILE
    path.write_text(RECEIVERLESS_QUERY, encoding="utf-8")
    surfaces = extract_file(path, FILE)
    assert [s for s in surfaces if s.kind == DATA_SOURCE] == []
    assert find_in_tree(parse_file(path), FILE, surfaces) == []


def test_an_interpolated_executemany_is_reported(tmp_path) -> None:
    """Parameterising the rows does not parameterise the table name in the query text."""
    findings = audit_source(tmp_path, EXECUTEMANY_QUERY)
    assert len(findings) == 1
    assert (findings[0].surface_name, findings[0].line) == ("cursor.executemany", QUERY_LINE)


def test_every_execute_method_is_one_the_detector_can_report() -> None:
    """A method outside `DATA_SOURCE_METHODS` yields no surface, so it could anchor nothing.

    The module raises at import if this is broken; the assertion states the
    invariant here so a reader sees it without opening the source.
    """
    assert ANCHOR_EXECUTE_METHODS <= EXECUTE_METHODS
    assert EXECUTE_METHODS <= set(DATA_SOURCE_METHODS)


def test_a_surface_is_only_joined_to_a_call_in_its_own_file(tmp_path) -> None:
    """Two files with an execute call at the same line: the clean one borrows nothing."""
    (tmp_path / OTHER_FILE).write_text(CONSTANT_QUERY, encoding="utf-8")
    interpolated = tmp_path / FILE
    interpolated.write_text(INTERPOLATED_QUERY, encoding="utf-8")
    surfaces = extract_file(interpolated, FILE) + extract_file(tmp_path / OTHER_FILE, OTHER_FILE)
    findings = run_over_repo(str(tmp_path), surfaces)
    assert [(f.file, f.line) for f in findings] == [(FILE, QUERY_LINE)]


def test_a_file_that_cannot_be_parsed_does_not_stop_the_run(tmp_path) -> None:
    """One unreadable file is already a recorded skip; it must not cost the rest of the audit."""
    (tmp_path / BROKEN_FILE).write_text(BROKEN_SOURCE, encoding="utf-8")
    findings = audit_source(tmp_path, INTERPOLATED_QUERY)
    assert [(f.file, f.line) for f in findings] == [(FILE, QUERY_LINE)]


def test_a_repository_with_no_python_reports_nothing(tmp_path) -> None:
    """Nothing to read is a clean result, not an error."""
    assert run_over_repo(str(tmp_path), []) == []
