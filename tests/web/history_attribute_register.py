"""The register itself: every attribute the three history components write.

Data, not a test -- which is why it is here rather than in
`test_jsx_history_attributes.py`, the way `icon_tables.py` and `css_rules.py`
hold what their own guards compare against. That file holds the parser, the
checks and the argument for enumerating at all; this holds the forty-four lines
being enumerated, so neither file is doing two jobs.

**Read it as four lists in source order**, one per region of markup: the row and
its cells, the group header, the options cell, and the table. A multiset is
built from them at the foot, because multiplicity is part of the claim -- four
`(td, className, "nowrap")` entries are four cells, and one of them turning into
something else already registered is exactly what a set could not see.

Every entry is a `(element, attribute, value)` triple with the value spelled as
the source spells it, quotes and braces included. Changing markup means changing
a line here, and then answering the question
`test_jsx_history_attributes.py::ADVICE` asks about it.
"""

from collections import Counter

from .jsx_sweep import FRONTEND_SRC

GROUP = FRONTEND_SRC / "components" / "HistoryGroup.jsx"
OPTIONS = FRONTEND_SRC / "components" / "RunOptions.jsx"
TABLE = FRONTEND_SRC / "components" / "HistoryTable.jsx"

# --- the register -------------------------------------------------------------
# Every attribute the row and its cells write.
THE_ROW = (
    ("tr", "className", '"row--clickable"'),
    ("tr", "onClick", "{() => navigate(runPath(run.run_id))}"),
    ("td", "className", '"nowrap"'),
    ("td", "className", '"nowrap"'),
    ("span", "className", '{`dot dot--${TONE[run.status] ?? "none"}`}'),
    ("RunOptions", "options", "{run.options}"),
    ("td", "className", '"nowrap"'),
    ("td", "className", '"nowrap"'),
)

# Every attribute the group header writes: the disclosure, the counts, the
# forget control, and the table it wraps.
THE_HEADER = (
    ("div", "className", '"group"'),
    ("button", "type", '"button"'),
    ("button", "className", '"group__open"'),
    ("button", "aria-expanded", "{open}"),
    ("button", "onClick", "{onToggle}"),
    ("Icon", "name", '"chevron"'),
    ("Icon", "className",
     '{open ? "disclose__mark disclose__mark--open" : "disclose__mark"}'),
    ("span", "className", '"group__name mono"'),
    ("span", "className", '"group__count"'),
    ("span", "className", '"tag tag--crit"'),
    ("button", "type", '"button"'),
    ("button", "className", '"filter group__forget"'),
    ("button", "disabled", "{forgetting}"),
    ("button", "onClick", "{() => confirmed(failed) && onForget(failed)}"),
    ("div", "className", '"table-scroll"'),
    ("table", "className", '"table"'),
    ("Row", "key", "{run.run_id}"),
    ("Row", "run", "{run}"),
)

# Every attribute the options cell writes.
THE_OPTIONS = (
    ("div", "className", '"run-options"'),
    ("span", "className", '"tag tag--rule"'),
    ("span", "key", "{key}"),
    ("span", "className", '"tag tag--mid"'),
    ("span", "className", '"run-options__model"'),
    ("span", "className", '"mono"'),
    ("span", "className", '"run-options__model"'),
    ("span", "className", '"mono"'),
)

# And every attribute the table writes: its empty notice, the open-everything
# control that nothing else pins, and what it hands one group.
THE_TABLE = (
    ("p", "className", '"empty"'),
    ("button", "type", '"button"'),
    ("button", "className", '"disclose disclose--inline"'),
    ("button", "onClick", "{open.toggleAll}"),
    ("HistoryGroup", "key", "{group.key}"),
    ("HistoryGroup", "group", "{group}"),
    ("HistoryGroup", "open", "{open.isOpen(group.key)}"),
    ("HistoryGroup", "onToggle", "{() => open.toggle(group.key)}"),
    ("HistoryGroup", "onForget", "{(failed) => forget(group, failed)}"),
    ("HistoryGroup", "forgetting", "{forgetting === group.key}"),
)

REGISTERED = Counter((*THE_ROW, *THE_HEADER, *THE_OPTIONS, *THE_TABLE))

# The three files and what each contributes, so a shortfall names its file.
BY_FILE = ((GROUP, len(THE_ROW) + len(THE_HEADER)), (OPTIONS, len(THE_OPTIONS)),
           (TABLE, len(THE_TABLE)))
