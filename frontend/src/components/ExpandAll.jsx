import Icon from "./Icon.jsx";

/** One control that opens or closes every row currently shown. */
export default function ExpandAll({ allOpen, onToggle, noun }) {
  // Right-aligned in a row of its own: it acts on the table below it, and the
  // left edge there belongs to the filter pills.
  return (
    <div className="row-actions">
      <button type="button" className="disclose disclose--inline"
              aria-expanded={allOpen} onClick={onToggle}>
        <Icon name="chevron"
              className={allOpen ? "disclose__mark disclose__mark--open"
                                 : "disclose__mark"} />
        {/* Names what it will do, not what it shows: a control labelled with
            its current state reads as a claim about the rows. */}
        {allOpen ? `Hide every ${noun}` : `Show every ${noun}`}
      </button>
    </div>
  );
}
