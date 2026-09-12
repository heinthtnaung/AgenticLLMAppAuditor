import OptionsMenu from "./OptionsMenu.jsx";

/** The target, the flags beside it, and the button that runs them. */
export default function AuditForm({ values, onChange, onSubmit, running }) {
  const ready = values.url.trim().length > 0;

  return (
    <form
      className="card"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready && !running) onSubmit();
      }}
    >
      <h2 className="card__title">Target</h2>
      <p className="card__hint">
        An https:// link is fetched and pinned at its current commit. A
        filesystem path is refused: it would resolve against the server's own
        disk, which is a far larger permission than cloning a public repository.
      </p>

      {/* The options sit beside the field rather than under it, so the whole
          request is one row. The menu keeps its own width; the repository takes
          the rest. */}
      <div className="target">
        <label className="field field--grow">
          <span className="field__label">Repository</span>
          <input
            className="field__input field__input--large"
            type="text"
            placeholder="https://github.com/owner/app.git"
            value={values.url}
            disabled={running}
            onChange={(event) => onChange("url", event.target.value)}
          />
        </label>
        <OptionsMenu values={values} onChange={onChange} disabled={running} />
      </div>

      <div className="form__actions form__actions--centre">
        <button className="run run--large" type="submit" disabled={!ready || running}>
          {running && <span className="spinner" aria-hidden="true" />}
          {running ? "Auditing…" : "Audit"}
        </button>
      </div>
    </form>
  );
}
