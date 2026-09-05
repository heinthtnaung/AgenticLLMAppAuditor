"""LLM02: which query texts count as built at runtime, and which are written out.

One of the two halves of `checks/output_handling.py`. This file asks a single
question of the check -- *is this query text assembled while the program runs?*
-- and every test is one spelling of yes or no. Which surface a yes is anchored
to is the other half, in `test_output_handling_join.py`.

The negatives matter as much as the positives, because the narrowings are where
the false positives were: a query written out in three `+` pieces and a
`.format()` given nothing to insert are both text decided before the program
starts, and reporting either is a false alarm a reader has to disprove by hand.

Surfaces come from the real Python detector, so a finding is anchored where an
audit would have anchored it. What this tree cannot show: it is written here,
so it holds no file the walker sizes out, no non-UTF-8 source and no shape
nobody thought of.
"""

from checks.output_handling import CHECK_NAME, OWASP_ID
from output_handling_fixtures import (
    CONSTANT_QUERY, FILE, INTERPOLATED_QUERY, QUERY_LINE, audit_source,
    execute_anchors, surfaces_and_findings)

# The same defect in its other three spellings.
PERCENT_QUERY = '''def read(cursor, user_id):
    cursor.execute("SELECT * FROM t WHERE id = '%s'" % user_id)
'''

CONCATENATED_QUERY = '''def read(cursor, user_id):
    cursor.execute("SELECT * FROM t WHERE id = " + user_id)
'''

FORMATTED_QUERY = '''def read(cursor, user_id):
    cursor.execute("SELECT * FROM t WHERE id = {}".format(user_id))
'''

# The fix for the first snippet -- the driver is handed the value, not the text.
PARAMETERISED_QUERY = '''def read(cursor, user_id):
    cursor.execute("SELECT * FROM t WHERE id = ?", (user_id,))
'''

# A constant query whose *parameter list* is assembled -- two lists joined with
# `+`, which is what the query text being joined with `+` looks like. The
# argument position is the whole difference between this and a finding.
BUILT_PARAMETER_LIST = '''def read(cursor, base_params, extra_params):
    cursor.execute("SELECT * FROM t WHERE id = ?", base_params + extra_params)
'''

# A call with no first argument to judge at all.
NO_ARGUMENT_QUERY = '''def read(cursor):
    cursor.execute()
'''

# An f-string that interpolates a literal: the text is still decided up front.
CONSTANT_INTERPOLATION = '''def read(cursor):
    cursor.execute(f"SELECT {'id'} FROM t")
'''

# --- The two false positives found by the review gate, fixed 2026-09-05 ----

# Written-out text in three pieces. A one-level-deep reading called this
# dynamic, because the left operand of the outer `+` is itself a `+`.
THREE_LITERALS_QUERY = '''def read(cursor):
    cursor.execute("SELECT * " + "FROM t " + "WHERE x = 1")
'''

# The same text in two pieces, the case the one-level reading got right.
TWO_LITERALS_QUERY = '''def read(cursor):
    cursor.execute("SELECT * " + "FROM t")
'''

# `.format()` with nothing to insert: the text is the format string itself.
FORMAT_WITH_NOTHING_TO_INSERT = '''def read(cursor):
    cursor.execute("SELECT 1".format())
'''

# `% (value,)`: the right operand is a tuple, so it is not written-out text.
PERCENT_LITERAL_TUPLE_QUERY = '''def read(cursor):
    cursor.execute("SELECT %s" % ("literal",))
'''

# --- The two verified silent misses, pinned as gaps ------------------------

# The query is assembled one line before the call, so the argument the check
# judges is a bare name. The execute call is on the third line, not the second.
QUERY_BUILT_INTO_A_VARIABLE = '''def read(cursor, user_id):
    query = f"SELECT * FROM t WHERE id = '{user_id}'"
    cursor.execute(query)
'''

# `.format_map(d)` is the fourth spelling of the defect, and is not `.format`.
FORMAT_MAP_QUERY = '''def read(cursor, values):
    cursor.execute("SELECT * FROM t WHERE id = {id}".format_map(values))
'''

# Where `QUERY_BUILT_INTO_A_VARIABLE` puts its execute call.
LATER_QUERY_LINE = 3


def test_an_f_string_query_is_reported(tmp_path) -> None:
    """The motivating case, classified as the grading keys spell it rather than by constant."""
    findings = audit_source(tmp_path, INTERPOLATED_QUERY)
    assert len(findings) == 1
    reported = findings[0]
    assert (reported.owasp_id, reported.rule_id) == ("LLM02", "unsafe_query_construction")
    assert (reported.file, reported.line) == (FILE, QUERY_LINE)


def test_a_percent_formatted_query_is_reported(tmp_path) -> None:
    """`"... '%s'" % user_id` builds the text before the driver sees it."""
    findings = audit_source(tmp_path, PERCENT_QUERY)
    assert [(f.rule_id, f.line) for f in findings] == [(CHECK_NAME, QUERY_LINE)]


def test_a_concatenated_query_is_reported(tmp_path) -> None:
    """`"... id = " + user_id` is the same defect written with `+`."""
    findings = audit_source(tmp_path, CONCATENATED_QUERY)
    assert [(f.rule_id, f.line) for f in findings] == [(CHECK_NAME, QUERY_LINE)]


def test_a_format_call_query_is_reported(tmp_path) -> None:
    """`"... {}".format(user_id)` is the third spelling, and was given something to insert."""
    findings = audit_source(tmp_path, FORMATTED_QUERY)
    assert [(f.rule_id, f.line) for f in findings] == [(CHECK_NAME, QUERY_LINE)]


def test_a_constant_query_is_not_reported(tmp_path) -> None:
    """Nothing is interpolated, so the text is decided before the program runs."""
    assert audit_source(tmp_path, CONSTANT_QUERY) == []


def test_a_parameterised_query_is_not_reported(tmp_path) -> None:
    """The fix for the first case: the value goes to the driver, not into the text."""
    assert audit_source(tmp_path, PARAMETERISED_QUERY) == []


def test_an_assembled_parameter_list_is_not_an_assembled_query(tmp_path) -> None:
    """Only the first argument is the query text: the rest are values the driver escapes.

    Judging every argument would report the fix as the defect. This snippet is
    the shape that would be reported -- a parameterised query whose *parameters*
    are joined with `+`, which is the operator a finding turns on.
    """
    assert audit_source(tmp_path, BUILT_PARAMETER_LIST) == []


def test_an_execute_call_with_no_arguments_reports_nothing(tmp_path) -> None:
    """There is no first argument to judge, and reading one anyway would raise."""
    assert audit_source(tmp_path, NO_ARGUMENT_QUERY) == []


def test_an_f_string_interpolating_only_a_constant_is_not_reported(tmp_path) -> None:
    """A deliberate narrowing: `f"SELECT {'id'}"` puts in no runtime value."""
    assert audit_source(tmp_path, CONSTANT_INTERPOLATION) == []


# --- The two false positives, fixed 2026-09-05 -----------------------------

def test_three_concatenated_literals_are_not_reported(tmp_path) -> None:
    """`"a " + "b " + "c"` is written-out text, however many pieces it is written in.

    The narrowing used to read one level deep, so it called two literals safe
    and three literals dynamic -- the longer the written-out query, the more
    likely a false positive.
    """
    surfaces, findings = surfaces_and_findings(tmp_path, THREE_LITERALS_QUERY)
    assert execute_anchors(surfaces) == [("cursor.execute", QUERY_LINE)]
    assert findings == []


def test_two_concatenated_literals_are_not_reported(tmp_path) -> None:
    """The shallow half of the same narrowing, which had never had a test of its own."""
    surfaces, findings = surfaces_and_findings(tmp_path, TWO_LITERALS_QUERY)
    assert execute_anchors(surfaces) == [("cursor.execute", QUERY_LINE)]
    assert findings == []


def test_a_format_call_given_nothing_to_insert_is_not_reported(tmp_path) -> None:
    """`"SELECT 1".format()` inserts nothing, so the text is the format string itself.

    `test_a_format_call_query_is_reported` above is this test's guard: it is
    the same shape given a value, and it must stay reported, or this narrowing
    has swallowed the rule.
    """
    surfaces, findings = surfaces_and_findings(tmp_path, FORMAT_WITH_NOTHING_TO_INSERT)
    assert execute_anchors(surfaces) == [("cursor.execute", QUERY_LINE)]
    assert findings == []


def test_a_percent_query_interpolating_a_literal_tuple_is_reported(tmp_path) -> None:
    """`"SELECT %s" % ("literal",)` is reported: a tuple is not written-out text.

    Asserted as the check behaves, not as it ideally would. The narrowing reads
    both operands of `%` and a tuple is neither a constant nor a nested
    concatenation, so the query is judged dynamic even though the only value it
    interpolates is a literal. `"SELECT %s" % "literal"`, with no tuple, is
    silent -- the shape decides, not the value.
    """
    findings = audit_source(tmp_path, PERCENT_LITERAL_TUPLE_QUERY)
    assert [(f.rule_id, f.line) for f in findings] == [(CHECK_NAME, QUERY_LINE)]


# --- Two known gaps, pinned so closing one is noticed ----------------------
#
# Neither of these is desired behaviour. Both are verified silent misses filed
# in docs/TODO.md, pinned here because the check is named in
# `coverage.checks_run`, where silence is read as "looked and found nothing".

def test_a_query_built_into_a_variable_one_line_earlier_is_missed(tmp_path) -> None:
    """Known gap: only the argument expression is judged, and here it is a bare name.

    `query = f"SELECT ... {user_id}"` then `cursor.execute(query)` is the same
    defect as the reported case, one line apart. Closing it needs the binding
    the taint trace already builds. If this test starts failing the gap has
    closed -- delete it and the TODO.md entry together.
    """
    surfaces, findings = surfaces_and_findings(tmp_path, QUERY_BUILT_INTO_A_VARIABLE)
    assert execute_anchors(surfaces) == [("cursor.execute", LATER_QUERY_LINE)]
    assert findings == []


def test_a_format_map_query_is_missed(tmp_path) -> None:
    """Known gap: `.format_map(d)` builds the text exactly as `.format(**d)` would.

    The check matches the method name `format` and nothing else, so this fourth
    spelling passes. Closing it is one name in `_formats_a_value`; until then
    the miss is pinned rather than assumed.
    """
    surfaces, findings = surfaces_and_findings(tmp_path, FORMAT_MAP_QUERY)
    assert execute_anchors(surfaces) == [("cursor.execute", QUERY_LINE)]
    assert findings == []


def test_the_check_reports_the_class_the_scorer_grades() -> None:
    """OWASP_ID is what a grading key joins on, so it is pinned rather than derived."""
    assert (OWASP_ID, CHECK_NAME) == ("LLM02", "unsafe_query_construction")
