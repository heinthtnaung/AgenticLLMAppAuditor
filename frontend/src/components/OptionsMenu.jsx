import { useEffect, useState } from "react";
import { fetchModelStatus } from "../api.js";

// Each option costs something -- a model call, a network round trip, a file
// written -- and the tags still carry that, because these are off by default
// for reasons a reader should be able to see rather than guess. As three tags
// the reason moves to the tooltip and the note below; it is not dropped.
const OPTIONS = [
  {
    key: "semantic_probe",
    name: "Semantic probe",
    // One line, and it names the cost rather than the feature: that is what a
    // reader is deciding about, and it is why these are off by default.
    why: "Asks the local model to judge each prompt template. Slower, and needs "
       + "Ollama running.",
  },
  {
    key: "draft_key",
    name: "Draft a grading key",
    why: "Drafts a key for a human to correct. Measured: it finds real defects "
       + "and misclassifies them, so read it before scoring anything.",
  },
  {
    key: "compare_models",
    name: "Compare models",
    why: "Audits twice, local against hosted. Sends the audited source to a "
       + "third party and needs an API key.",
  },
];

/** Which pulled model this run uses, or the configured one. */
function ModelField({ value, onChange, disabled }) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let watching = true;
    fetchModelStatus()
      .then((found) => { if (watching) setStatus(found); })
      .catch(() => { if (watching) setStatus(null); });
    return () => { watching = false; };
  }, []);

  const models = status?.models ?? [];
  const offline = status !== null && !status.reachable;

  return (
    <label className="field field--last">
      <span className="field__label">Local model</span>
      <select className="field__input" value={value} disabled={disabled || offline}
              onChange={(event) => onChange("model", event.target.value)}>
        <option value="">
          {status ? `${status.configured_model} (configured)` : "the configured model"}
        </option>
        {models
          .filter((model) => model.name !== status?.configured_model)
          .map((model) => (
            <option key={model.name} value={model.name}>{model.name}</option>
          ))}
      </select>
      <p className="field__note">
        {offline
          ? "The local model server is not answering, so the models it holds "
            + "cannot be listed. The audit will use the configured model."
          : "Only models this machine has already pulled. findings.json records "
            + "whichever answered. Each run keeps its own artifacts directory, "
            + "so auditing one app twice with different models leaves both "
            + "runs' files on disk."}
      </p>
    </label>
  );
}

/** Which model the hosted arm uses. Only meaningful with comparison on. */
function CloudModelField({ value, onChange, disabled }) {
  return (
    <label className="field field--last">
      <span className="field__label">Cloud model (optional)</span>
      <input className="field__input" type="text" placeholder="z-ai/glm-5.2"
             value={value} disabled={disabled}
             onChange={(event) => onChange("cloud_model", event.target.value)} />
      <p className="field__note">
        Leave blank to use OPENROUTER_MODEL from the backend&rsquo;s environment.
      </p>
    </label>
  );
}

/** The three options as tags, and the fields the chosen ones need. */
export default function OptionsMenu({ values, onChange, disabled }) {
  // A model is only consulted by one of these, so the picker appears with them
  // rather than standing alone offering something nothing would use.
  const consultsAModel = OPTIONS.some((option) => values[option.key]);

  return (
    <div className="options">
      <span className="field__label">Options</span>
      <div className="tags">
        {OPTIONS.map((option) => (
          // `data-tip` rather than `title`: the native tooltip waits about a
          // second and this is the sentence the choice turns on. The same text
          // rides in `aria-label`, since a CSS tooltip is not announced.
          <button key={option.key} type="button" data-tip={option.why}
                  disabled={disabled}
                  aria-pressed={Boolean(values[option.key])}
                  aria-label={`${option.name}. ${option.why}`}
                  className={`pick${values[option.key] ? " pick--on" : ""}`}
                  onClick={() => onChange(option.key, !values[option.key])}>
            {option.name}
          </button>
        ))}
      </div>
      <p className="field__note">
        All off by default: an ordinary audit calls no model and opens no
        socket. Hover a tag for what it costs.
      </p>

      {consultsAModel && (
        <div className="options__fields">
          <ModelField value={values.model} onChange={onChange} disabled={disabled} />
          {values.compare_models && (
            <CloudModelField value={values.cloud_model} onChange={onChange}
                             disabled={disabled} />
          )}
        </div>
      )}
    </div>
  );
}
