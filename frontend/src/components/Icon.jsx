// Hand-written line icons, because the alternative is an icon package and the
// README claims React with no other runtime dependency. Each is a 16-unit
// viewBox drawn with `currentColor`, so a token change recolours every one.
const PATHS = {
  audit: "M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z",
  history: "M10 5v5l4 2M10 2a8 8 0 100 16 8 8 0 000-16z",
  shield: "M10 2l6 3v5c0 4-3 7-6 8-3-1-6-4-6-8V5z",
  finding: "M10 3l7 13H3zM10 8v4M10 14h.01",
  surface: "M10 3l7 4-7 4-7-4zM3 11l7 4 7-4",
  package: "M10 2l7 4v8l-7 4-7-4V6zM3 6l7 4 7-4M10 10v8",
  download: "M10 3v9M6 9l4 4 4-4M4 16h12",
  chevron: "M6 8l4 4 4-4",
  check: "M4 10l4 4 8-8",
  light: "M10 6a4 4 0 100 8 4 4 0 000-8zM10 1v2M10 17v2M1 10h2M17 10h2M4 4l1.5 1.5M14.5 14.5L16 16M16 4l-1.5 1.5M5.5 14.5L4 16",
  dark: "M15 12a6 6 0 01-7-9 7 7 0 107 9z",
};

/** One icon, sized in ems so it scales with the text beside it.
 *
 * A name with no path draws a dotted square rather than nothing: an icon that
 * is silently invisible is a typo nobody finds, and this is the one place a
 * missing name can be reported without taking the page down.
 */
export default function Icon({ name, className = "" }) {
  if (!(name in PATHS)) {
    return <span className={`icon icon--unknown ${className}`} title={`no icon: ${name}`} />;
  }
  return (
    <svg className={`icon ${className}`} viewBox="0 0 20 20" aria-hidden="true"
         fill="none" stroke="currentColor" strokeWidth="1.6"
         strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[name]} />
    </svg>
  );
}
