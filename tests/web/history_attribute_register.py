"""The register itself: every attribute the three history components write.

Data, not a test -- which is why it is here rather than in
`test_jsx_history_attributes.py`, the way `icon_tables.py` and `css_rules.py`
hold what their own guards compare against. That file holds the parser, the
checks and the argument for enumerating at all; this holds the fifty-eight lines
being enumerated, so neither file is doing two jobs.

**Read it as five lists in source order**, one per region of markup: the model
cell, the row and its cells, the group header, the options cell, and the table.
A multiset is built from them at the foot, because multiplicity is part of the
claim -- `(td, className, "nowrap")` appearing five times is five cells, and one
of them turning into something else already registered is exactly what a set
could not see.

It was forty-four across four lists until 2026-09-18. What moved: every row
gained a select box and the header gained the `<th>` over it; the two model
names left the options cell for `ModelCell`, which is a region of its own
because it writes the `<td>` its callers do not; `.table-scroll` became
`.group__runs` and `.group` became conditional as the open group folded into one
panel; and `HistoryTable` gained the two props the selection rides on.

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
# One arm's model as a cell. Its own region because it writes the `<td>` that
# the row does not: `<ModelCell />` in the row is one attribute there and three
# more here, which is why the row's cell count and this file's line count for
# `HistoryGroup.jsx` are two different numbers.
THE_MODEL_CELL = (
    ("td", "className", '"nowrap"'),
    ("span", "className", '"mono"'),
    ("span", "className", '"model--none"'),
)

# Every attribute the row and its cells write.
THE_ROW = (
    ("tr", "className", '"row--clickable"'),
    ("tr", "onClick", "{() => navigate(runPath(run.run_id))}"),
    # The select box. A real `<label>` with hidden text rather than an
    # `aria-label`, because some browsers render the latter as hover text on a
    # bare form control -- which is where a stray tooltip here came from.
    ("td", "className", '"pick"'),
    ("td", "onClick", "{(event) => event.stopPropagation()}"),
    ("label", "className", '"pick__label"'),
    ("span", "className", '"visually-hidden"'),
    ("input", "type", '"checkbox"'),
    ("input", "className", '"pick__box"'),
    ("input", "checked", "{picked}"),
    ("input", "onChange", "{() => onPick(run.run_id)}"),
    ("td", "className", '"nowrap"'),
    ("td", "className", '"nowrap"'),
    ("span", "className", '{`dot dot--${TONE[run.status] ?? "none"}`}'),
    ("RunOptions", "options", "{run.options}"),
    # The whole run, not its options: what answered is served beside the record.
    ("ModelCell", "shown", "{localModel(run)}"),
    ("ModelCell", "shown", "{cloudModel(run)}"),
    ("td", "className", '"nowrap"'),
    ("td", "className", '"nowrap"'),
)

# Every attribute the group header writes: the disclosure, the counts, the
# forget control, and the table it wraps.
THE_HEADER = (
    # Conditional since the open group became one panel with its header.
    ("div", "className", '{open ? "group group--open" : "group"}'),
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
    ("div", "className", '"group__runs"'),
    ("table", "className", '"table"'),
    # The heading over the select column, which carries no text of its own --
    # `test_jsx_history_columns.py` is where that absence is accounted for.
    ("th", "className", '"pick"'),
    ("Row", "key", "{run.run_id}"),
    ("Row", "run", "{run}"),
    ("Row", "picked", "{picked.has(run.run_id)}"),
    ("Row", "onPick", "{onPick}"),
)

# Every attribute the options cell writes. The two `run-options__model` spans
# and their `mono` children left on 2026-09-18: this cell renders flags only
# now, and the names are two columns fed by the helpers it still exports.
THE_OPTIONS = (
    ("div", "className", '"run-options"'),
    ("span", "className", '"tag tag--rule"'),
    ("span", "key", "{key}"),
    ("span", "className", '"tag tag--mid"'),
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
    ("HistoryGroup", "picked", "{picked}"),
    ("HistoryGroup", "onPick", "{onPick}"),
)

REGISTERED = Counter((*THE_MODEL_CELL, *THE_ROW, *THE_HEADER, *THE_OPTIONS, *THE_TABLE))

# The three files and what each contributes, so a shortfall names its file.
# `HistoryGroup.jsx` holds three of the five lists.
BY_FILE = ((GROUP, len(THE_MODEL_CELL) + len(THE_ROW) + len(THE_HEADER)),
           (OPTIONS, len(THE_OPTIONS)), (TABLE, len(THE_TABLE)))
