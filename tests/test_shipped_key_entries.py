"""The six entries `docs/REPORT.md` publishes a measurement against, pinned field by field.

`test_shipped_grading_key.py` says the key is well-formed and
`test_shipped_key_join.py` says its join fields can be answered. Neither would
notice an entry being re-anchored, re-classified or dropped -- and every figure
in the report's "A grading key for `damn-vulnerable-llm-agent`" section is a
count of *these* entries. 4 of 6 static, 5 of 6 with the probe, 5 of 6 for the
grep baseline and 0 of 6 for the SBOM-only one are readings of this file, so an
edit to it moves a published number with nothing to catch it.

**The scores themselves are not pinned here, and cannot be.** Reproducing one
means auditing `damn-vulnerable-llm-agent`, a repository this project does not
own and does not ship; a test that needed it on disk could not run on a clean
checkout. What is pinned is the input the published numbers were read from.

**`DVLA-04` is pinned by its absence.** An earlier draft graded
`transaction_db.py:76` -- `get_user`, whose one caller is `db.get_user(1)`, a
literal at `tools.py:18`. No agent-controlled value reaches it, so the entry
graded a code shape rather than a reachable defect, and a key entry nothing can
reach costs recall it never should have measured. It was dropped, and a
re-derivation of the same key would put it straight back.
"""

from grading_keys import GROUND_TRUTH_SUFFIX
from shipped_key_fixtures import SHIPPED_APPS, read

APP = "damn-vulnerable-llm-agent"

# The published key, read off the file: id, file, line, risk class, surface
# kind, surface name, component, detection, code anchor. In the order the key
# lists them, which is `(file, line, id)` and is what a diff of two revisions
# relies on.
PUBLISHED_ENTRIES = (
    ("DVLA-01", "main.py", 21, "LLM01", "PROMPT_TEMPLATE",
     "system_msg", None, "static",
     'system_msg = """Assistant helps the current user retrieve th'),
    ("DVLA-06", "main.py", 60, "LLM01", "DATA_SOURCE",
     "st.chat_input", None, "static",
     'if prompt := st.chat_input(placeholder="Show my recent trans'),
    ("DVLA-05", "main.py", 71, "AUDITABILITY", "AGENT_DEF",
     "AgentExecutor.from_agent_and_tools", None, "static",
     "executor = AgentExecutor.from_agent_and_tools("),
    ("DVLA-02", "tools.py", 40, "LLM06", "TOOL_CALL",
     "GetUserTransactions", None, "static",
     "get_recent_transactions_tool = Tool("),
    ("DVLA-03", "transaction_db.py", 62, "LLM02", "DATA_SOURCE",
     "cursor.execute", None, "static",
     'cursor.execute(f"SELECT * FROM Transactions WHERE userId = \''),
    ("DVLA-07", "utils.py", 75, "LLM03", "DATA_SOURCE",
     "yaml.load", None, "static",
     "yaml_data = yaml.load(f, Loader=yaml.SafeLoader)"),
)

PUBLISHED_COUNT = 6
DROPPED_ID = "DVLA-04"

# The commit every line number above was read at. A key re-anchored against
# another commit would keep all six ids and point at different code.
PUBLISHED_COMMIT = "c0cf9a14adad76e9d6a53c41741f625334bd9971"

# The one entry the auditor reaches and no grep rule can, and the one entry the
# grep baseline reaches and the auditor does not. The report's claim that the
# two systems are near-complementary rests on these two staying in the key.
AUDITOR_ONLY_ID = "DVLA-07"
BASELINE_ONLY_ID = "DVLA-02"


def published_key() -> dict:
    """The shipped key the report's counts were read from."""
    return read(APP, GROUND_TRUTH_SUFFIX)


def entries_by_id() -> dict[str, dict]:
    """The shipped key's entries, keyed by the id the report's tables cite."""
    return {entry["id"]: entry for entry in published_key()["findings"]}


def pinned_field(index: int) -> list[tuple[str, object]]:
    """One column of the pinned table, paired with the id it belongs to."""
    return [(row[0], row[index]) for row in PUBLISHED_ENTRIES]


# --- There is something to pin ----------------------------------------------

def test_the_measured_app_is_one_this_repository_ships_a_key_for() -> None:
    """Guard: with the key gone, every lookup below would raise rather than pass quietly."""
    assert APP in SHIPPED_APPS
    assert len(PUBLISHED_ENTRIES) == PUBLISHED_COUNT


def test_the_key_holds_exactly_the_six_published_entries_in_the_published_order() -> None:
    """Six is the denominator of every count in the report; the order is the key's own."""
    assert [entry["id"] for entry in published_key()["findings"]] == \
        [row[0] for row in PUBLISHED_ENTRIES]


def test_the_key_counts_six_findings() -> None:
    """`finding_count` is what the scorer divides by, so it carries the denominator too."""
    assert published_key()["finding_count"] == PUBLISHED_COUNT


def test_the_key_is_still_anchored_at_the_commit_the_numbers_were_read_at() -> None:
    """Same ids over another commit would be six different defects under six old names."""
    assert published_key()["upstream_commit"] == PUBLISHED_COMMIT


# --- Each pinned field ------------------------------------------------------

def test_every_published_entry_anchors_the_file_it_was_measured_in() -> None:
    """`file` is the first thing the join compares: a moved entry answers a different finding."""
    found = entries_by_id()
    for key_id, file in pinned_field(1):
        assert found[key_id]["file"] == file, key_id


def test_every_published_entry_anchors_the_line_it_was_measured_at() -> None:
    """The match window opens at this line, so moving it moves what can answer the entry."""
    found = entries_by_id()
    for key_id, line in pinned_field(2):
        assert found[key_id]["line"] == line, key_id


def test_every_published_entry_keeps_the_risk_class_it_was_scored_under() -> None:
    """Classification is what Phase 4 scores: re-filing an entry re-writes two rows at once."""
    found = entries_by_id()
    for key_id, owasp_id in pinned_field(3):
        assert found[key_id]["owasp_id"] == owasp_id, key_id


def test_every_published_entry_keeps_the_surface_kind_it_joins_on() -> None:
    """`llm_surface` is compared against the finding's kind, so a change here suppresses it."""
    found = entries_by_id()
    for key_id, kind in pinned_field(4):
        assert found[key_id]["llm_surface"] == kind, key_id


def test_every_published_entry_keeps_the_surface_name_it_joins_on() -> None:
    """The name is what separates two findings on one line, and all six name one."""
    found = entries_by_id()
    for key_id, name in pinned_field(5):
        assert found[key_id]["surface_name"] == name, key_id


def test_no_published_entry_names_a_component() -> None:
    """All six are null, including the supply-chain one, and that is not an oversight.

    `component` is compared against the finding's *purl*. `DVLA-07` is an
    undeclared package, which has no purl at all, so naming `pyyaml` there
    suppressed the one entry the auditor reaches alone.
    """
    found = entries_by_id()
    for key_id, component in pinned_field(6):
        assert component is None
        assert found[key_id]["component"] is None, key_id


def test_every_published_entry_is_declared_reachable_by_a_static_check() -> None:
    """`detection` is what lets a baseline state an achievable ceiling; all six say static."""
    found = entries_by_id()
    for key_id, detection in pinned_field(7):
        assert found[key_id]["detection"] == detection, key_id


def test_every_published_entry_keeps_the_code_anchor_it_was_written_from() -> None:
    """The anchor is what lets a human tell a line that drifted from one that never matched."""
    found = entries_by_id()
    for key_id, anchor in pinned_field(8):
        assert found[key_id]["code_anchor"] == anchor, key_id


# --- The two entries the comparison rests on --------------------------------

def test_the_entry_only_the_auditor_reaches_is_still_in_the_key() -> None:
    """Drop `DVLA-07` and the report's whole supply-chain claim loses its evidence."""
    assert AUDITOR_ONLY_ID in entries_by_id()


def test_the_entry_only_the_grep_baseline_reaches_is_still_in_the_key() -> None:
    """Drop `DVLA-02` and the baseline's 5 of 6 becomes an unearned tie."""
    assert BASELINE_ONLY_ID in entries_by_id()


def test_the_unreachable_entry_that_was_dropped_has_not_come_back() -> None:
    """`DVLA-04` graded a shape no agent-controlled value reaches; see this module's docstring."""
    assert DROPPED_ID not in entries_by_id()
