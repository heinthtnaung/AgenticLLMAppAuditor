import { useState } from "react";
import { verifyDraft } from "../api.js";

// What verifying does and does not do, in the one place a person is about to do
// it. `source` never moves, so `key_ai_drafted` and `key_drafted_by_scored_system`
// both keep firing on every figure this key bounds; the single qualification
// this clears is `key_unverified`. A reader who thinks they are signing the key
// into independence is the failure this paragraph exists to prevent.
const WHAT_IT_CHANGES = "This clears one qualification, key_unverified, and no "
  + "other. The key stays tool_drafted, so every figure scored against it still "
  + "travels with key_ai_drafted and key_drafted_by_scored_system: checking the "
  + "entries cannot make the tool's own choice of what to include independent "
  + "of the tool.";

/** What a recorded check says once it exists. A fact, with no control beside it. */
function Recorded({ keyDocument }) {
  return (
    <p className="card__hint">
      <span className="tag tag--low">verified</span>{" "}
      Checked by <strong>{keyDocument.verified_by || "someone"}</strong>
      {keyDocument.verified_date ? ` on ${keyDocument.verified_date}` : ""}.
      {" "}{WHAT_IT_CHANGES}{" "}
      Withdrawing it is a hand edit of the file: the page records a check once,
      so a second claim cannot quietly replace the first.
    </p>
  );
}

/** Record that a human checked every entry of a drafted key. */
export default function KeyVerify({ app, keyDocument, onVerified }) {
  const [name, setName] = useState("");
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState(null);

  if (keyDocument.verified) return <Recorded keyDocument={keyDocument} />;

  async function record() {
    setSending(true);
    setFailed(null);
    try {
      onVerified(await verifyDraft(app, name));
    } catch (failure) {
      setFailed(failure.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <p className="card__hint">
        <span className="tag tag--rule">unverified</span>{" "}
        Nobody has recorded checking these entries against the pinned tree.
        {" "}{WHAT_IT_CHANGES}
      </p>
      <label className="field">
        <span className="field__label">Checked by</span>
        <input className="field__input" type="text" value={name}
               placeholder="who read every entry"
               disabled={sending}
               onChange={(event) => setName(event.target.value)} />
        {/* The same rule the auditor name is held to, and the same reason: this
            server has no authentication, so a name here is a claim about who
            checked the key rather than proof that they did. The date is the
            server's own, so a claim cannot be backdated through the page. */}
        <p className="field__note">
          Recorded in the draft with today&rsquo;s date. This endpoint has no
          authentication, so it is a claim about who checked it, not proof.
          That is why <code>promote_key.py</code> needs{" "}
          <code>--accept-verification</code> before a checked draft can bound a
          published figure.
        </p>
      </label>
      {failed && (
        <p className="notice notice--error">
          <strong>That claim was refused.</strong>
          <span className="notice__detail">{failed}</span>
        </p>
      )}
      <div className="form__actions">
        <button className="run" type="button" disabled={sending || !name.trim()}
                onClick={record}>
          {sending ? "Recording…" : "Record that I checked it"}
        </button>
      </div>
    </>
  );
}
