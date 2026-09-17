import { useState } from "react";
import KeyVerify from "./KeyVerify.jsx";
import { saveDraft } from "../api.js";

// Per-entry fields a person may correct. Everything else on an entry either
// anchors it to source — which this page has not seen, so it may not type one —
// or belongs to the key's standing, which an edit never moves.
const EDITABLE = ["owasp_id", "title", "description"];

/** One entry's correctable fields. */
function Entry({ entry, onChange, onDelete }) {
  return (
    <div className="entry">
      <div className="entry__where mono">
        {entry.id} — {entry.file}:{entry.line}
      </div>
      {EDITABLE.map((field) => (
        <label className="field" key={field}>
          <span className="field__label">{field.replace("_", " ")}</span>
          <input className="field__input" type="text" value={entry[field] ?? ""}
                 onChange={(event) => onChange(field, event.target.value)} />
        </label>
      ))}
      <button type="button" className="filter" onClick={onDelete}>Remove this entry</button>
    </div>
  );
}

/** Correct one drafted key. Its standing is shown, never offered. */
export default function KeyEditor({ draft, onClose, onSaved }) {
  const [key, setKey] = useState(draft.key);
  const [refusals, setRefusals] = useState(draft.refusals);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(null);

  function change(index, field, value) {
    const findings = key.findings.map((entry, at) =>
      at === index ? { ...entry, [field]: value } : entry);
    setKey({ ...key, findings });
  }

  async function save() {
    setSaving(true);
    setFailed(null);
    try {
      const saved = await saveDraft(draft.app, key);
      setKey(saved.key);
      setRefusals(saved.refusals);
      // The page above shows this key's standing beside the button that opened
      // it, so it is handed what was actually written rather than guessing.
      onSaved?.({ ...draft, key: saved.key, refusals: saved.refusals });
    } catch (failure) {
      setFailed(failure.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="card">
        <h2 className="card__title">{draft.app}</h2>
        {/* Two fields, and only one of them can ever move here. `source` is
            shown as a fact: a drafted key stays tool_drafted however much of it
            a person corrects, because the qualification is about validity, not
            quality — checking the entries cannot make the tool's own choice of
            what to include independent of the tool, and promotion leaves it
            alone too. `verified` is the one a human can move, through its own
            route below rather than through a save, so the pair can never be
            flipped together into a key that reads as human-authored. */}
        <p className="card__hint">
          <span className="tag tag--mid">{key.source}</span>{" "}
          Who chose these entries, and it stays that way however much of them
          you correct: a drafted key is qualified by <em>who chose them</em>,
          not by how good they are. <code>promote_key.py</code> publishes it and
          leaves this exactly as it is.
        </p>
        <KeyVerify app={draft.app} keyDocument={key}
                   onVerified={(checked) => {
                     setKey(checked.key);
                     setRefusals(checked.refusals);
                     onSaved?.({ ...draft, key: checked.key,
                                 refusals: checked.refusals });
                   }} />
        {refusals.length > 0 && (
          <p className="notice notice--error">
            <strong>Still blocking promotion.</strong>
            <span className="notice__detail">{refusals.join("; ")}</span>
          </p>
        )}
        {failed && (
          <p className="notice notice--error">
            <strong>That edit was refused.</strong>
            <span className="notice__detail">{failed}</span>
          </p>
        )}
        <div className="form__actions">
          <button className="run" type="button" disabled={saving} onClick={save}>
            {saving ? "Saving…" : "Save the draft"}
          </button>{" "}
          <button className="run run--secondary" type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="card__title">
          {key.findings.length} entries
        </h2>
        <p className="card__hint">
          A file, a line and an anchor are quotations from source this page has
          not read, so they are shown and not editable — redraft against the
          pinned tree to move one.
        </p>
        {key.findings.map((entry, index) => (
          <Entry key={entry.id} entry={entry}
                 onChange={(field, value) => change(index, field, value)}
                 onDelete={() => setKey({
                   ...key,
                   findings: key.findings.filter((_, at) => at !== index),
                 })} />
        ))}
      </div>
    </>
  );
}
