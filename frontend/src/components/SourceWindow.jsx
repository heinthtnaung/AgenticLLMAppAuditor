import { useEffect, useState } from "react";
import { fetchSource } from "../api.js";

/** The lines around the one a surface names, read from the tree on disk. */
export default function SourceWindow({ runId, file, line }) {
  const [window, setWindow] = useState(null);
  const [failed, setFailed] = useState(null);

  useEffect(() => {
    let watching = true;
    fetchSource(runId, file, line)
      .then((found) => { if (watching) setWindow(found); })
      .catch((error) => { if (watching) setFailed(error.message); });
    return () => { watching = false; };
  }, [runId, file, line]);

  if (failed) return <p className="advice__none">{failed}</p>;
  if (!window) return <p className="empty">Reading {file}…</p>;

  return (
    <div className="source">
      <ol className="source__lines" start={window.first_line}>
        {window.lines.map((text, at) => {
          const number = window.first_line + at;
          return (
            <li key={number} className={number === window.line ? "source__line--named" : ""}>
              <code>{text || " "}</code>
            </li>
          );
        })}
      </ol>
      {/* Said, never implied. The clone drops `.git` after pinning, so a fetched
          tree has no history to diff against -- this is the line as the file
          reads *now*, and if anything edited the tree since the audit that is
          what you are looking at. */}
      {window.unchecked && (
        <p className="source__caveat">
          Read from the tree on disk just now, not from the audit. {window.unchecked}
        </p>
      )}
    </div>
  );
}
