// What a key claims about itself. `source` says who chose the entries and
// `verified` says whether a human has checked them -- two different facts, so
// two tags rather than one word that would have to mean both.
const DRAFTED = "tool_drafted";

/** A drafted key's standing, as tags beside the button that opens it. */
export default function KeyBadge({ keyDocument }) {
  return (
    <>
      <span className={`tag tag--${keyDocument.source === DRAFTED ? "mid" : "rule"}`}>
        {keyDocument.source}
      </span>
      <span className={`tag tag--${keyDocument.verified ? "low" : "rule"}`}>
        {keyDocument.verified ? "verified" : "unverified"}
      </span>
    </>
  );
}
