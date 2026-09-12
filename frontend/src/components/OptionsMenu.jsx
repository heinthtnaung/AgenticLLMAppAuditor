import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";

// Each option costs something -- a model call, a network round trip, a file
// written -- and the menu still says what, because these are off by default for
// reasons a user should be able to see rather than guess. Folding them into a
// dropdown shortens the form; it must not shorten the reasons.
const OPTIONS = [
  {
    key: "semantic_probe",
    name: "Semantic probe",
    why: "Asks the local model to judge each prompt template for injection. " +
         "The only check that consults a model about a finding; off by default " +
         "so an ordinary audit is fast and produces the same artifacts either way.",
  },
  {
    key: "draft_key",
    name: "Draft a grading key",
    why: "Has the local model draft a grading key for a human to correct. " +
         "Measured: it locates real defects and misclassifies them, so read it " +
         "before scoring anything against it.",
  },
  {
    key: "compare_models",
    name: "Compare models",
    why: "Audits twice, local against hosted, and scores both. Sends the " +
         "audited repository's source to a third party and needs an API key.",
  },
];

/** Which model the hosted arm uses. Only meaningful with comparison on. */
function CloudModelField({ value, onChange, disabled }) {
  return (
    <div className="menu__nested">
      <label className="field field--last">
        <span className="field__label">Cloud model (optional)</span>
        <input
          className="field__input field__input--small"
          type="text"
          placeholder="z-ai/glm-5.2"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange("cloud_model", event.target.value)}
        />
        <p className="field__note">
          Leave blank to use OPENROUTER_MODEL from the backend&rsquo;s environment.
        </p>
      </label>
    </div>
  );
}

/** What the closed button says: never a bare count with nothing chosen. */
function summarise(chosen) {
  if (!chosen.length) return "All off";
  if (chosen.length === 1) return chosen[0].name;
  return `${chosen.length} options`;
}

/** The three flags as a multi-select dropdown beside the repository field. */
export default function OptionsMenu({ values, onChange, disabled }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  // A dropdown that only closes by pressing its own button is a trap. Both
  // listeners are removed with the panel, so nothing is bound while it is shut.
  useEffect(() => {
    if (!open) return undefined;
    const away = (event) => {
      if (!box.current?.contains(event.target)) setOpen(false);
    };
    const escape = (event) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const chosen = OPTIONS.filter((option) => values[option.key]);

  return (
    <div className="menu" ref={box}>
      <span className="field__label">Options</span>
      <button type="button" className="menu__button" disabled={disabled}
              aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="menu__summary">{summarise(chosen)}</span>
        {chosen.length > 0 && <span className="menu__count">{chosen.length}</span>}
        <Icon name="chevron" className={open ? "menu__mark menu__mark--open" : "menu__mark"} />
      </button>

      {open && (
        <div className="menu__panel" role="group" aria-label="Audit options">
          {OPTIONS.map((option) => (
            <label className="option" key={option.key}>
              <input
                type="checkbox"
                checked={values[option.key]}
                disabled={disabled}
                onChange={(event) => onChange(option.key, event.target.checked)}
              />
              <span>
                <span className="option__name">{option.name}</span>
                <p className="option__why">{option.why}</p>
              </span>
            </label>
          ))}
          {/* After the list, not inside it: the list is one checkbox per flag,
              and a branch on one member's key would make it something else. */}
          {values.compare_models && (
            <CloudModelField value={values.cloud_model} onChange={onChange}
                             disabled={disabled} />
          )}
        </div>
      )}
    </div>
  );
}
