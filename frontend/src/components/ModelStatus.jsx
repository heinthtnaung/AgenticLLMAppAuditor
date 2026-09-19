import { useEffect, useState } from "react";
import { fetchModelStatus } from "../api.js";

// Four states, and the label only speaks about the server. "asking" is not
// "offline": a page that has not heard back yet must not claim the server is
// stopped. And a server that is up while the configured model is missing is
// still *online* -- that is a fact about the model, so it changes the colour
// and the tooltip rather than the word.
const ASKING = "asking";
const UP = "up";
const INCOMPLETE = "incomplete";
const DOWN = "down";

const TONE = { [ASKING]: "none", [UP]: "low", [INCOMPLETE]: "mid", [DOWN]: "crit" };
const SERVER = "Ollama server";

/** What the pill says, and the detail behind it. */
function reading(status) {
  if (!status) {
    return { state: ASKING, label: `${SERVER}: checking`,
             detail: "Asking the local model server." };
  }
  if (!status.reachable) {
    return {
      state: DOWN,
      label: `${SERVER}: offline`,
      // The server's own sentence names the fix, so it is shown rather than
      // replaced with a friendlier one that says less.
      detail: status.error ?? "The local model server did not answer.",
    };
  }
  // Up, but missing the model an audit would ask for. Still online -- the word
  // stays true -- and worth a warning, because that failure lands mid-run,
  // after the repository has already been cloned.
  if (!status.configured_model_pulled) {
    return {
      state: INCOMPLETE,
      label: `${SERVER}: model not pulled`,
      detail: `${status.configured_model} is configured but not pulled. `
            + `Run: ollama pull ${status.configured_model}`,
    };
  }
  // Bare when it is working. The states below keep their word, because a
  // coloured dot on its own is not something every reader can act on -- and a
  // server that is up is the case where there is nothing to act on.
  return {
    state: UP,
    label: SERVER,
    detail: `${status.configured_model}, and ${(status.models ?? []).length} `
          + `model(s) pulled. Embeddings: ${status.embed_model}`
          + (status.embed_model_pulled ? "." : ", configured but not pulled."),
  };
}

/** Whether an audit that needs the local model could run right now. */
export default function ModelStatus() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let watching = true;
    fetchModelStatus()
      .then((found) => { if (watching) setStatus(found); })
      // The endpoint answers 200 even when Ollama is down, so reaching here
      // means *this* server did not answer -- a different fact, and one the
      // pill should not report as a stopped model server.
      .catch(() => { if (watching) setStatus(null); });
    return () => { watching = false; };
  }, []);

  const said = reading(status);
  return (
    // The label goes bare when all is well, so the state is named here for a
    // reader who cannot see the dot's colour.
    <span className={`model model--${said.state}`} title={said.detail}
          aria-label={`${said.label}. ${said.detail}`}>
      <span className={`dot dot--${TONE[said.state]}`} />
      <span className="model__label">{said.label}</span>
    </span>
  );
}
