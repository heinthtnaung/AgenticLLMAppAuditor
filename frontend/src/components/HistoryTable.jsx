import HistoryGroup from "./HistoryGroup.jsx";
import { useState } from "react";
import { groupRuns } from "../repoGroup.js";
import { useExpanded } from "../useExpanded.js";

/** Every past run, gathered by repository, each group opening on a click. */
export default function HistoryTable({ runs, onForget }) {
  const groups = groupRuns(runs);
  // The same hook the findings and surfaces tables use, so "which rows are
  // open" is one behaviour in this page rather than three.
  const open = useExpanded(groups.map((group) => group.key));
  const [forgetting, setForgetting] = useState(null);

  if (!runs.length) {
    return (
      <p className="empty">
        No audits yet. Every run started from this page is kept here until
        someone forgets it, and a failed one is the only kind that can be
        forgotten.
      </p>
    );
  }

  async function forget(group, failed) {
    setForgetting(group.key);
    try {
      // One primitive, called once per run, rather than a bulk endpoint: there
      // is one rule to reason about on the server and the page decides how many
      // to apply it to.
      await onForget(failed);
    } finally {
      setForgetting(null);
    }
  }

  return (
    <>
      {groups.length > 1 && (
        <button type="button" className="disclose disclose--inline"
                onClick={open.toggleAll}>
          {open.allOpen ? "Close every repository" : "Open every repository"}
        </button>
      )}
      {groups.map((group) => (
        <HistoryGroup key={group.key} group={group}
                      open={open.isOpen(group.key)}
                      onToggle={() => open.toggle(group.key)}
                      onForget={(failed) => forget(group, failed)}
                      forgetting={forgetting === group.key} />
      ))}
    </>
  );
}
