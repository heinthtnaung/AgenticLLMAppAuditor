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
  close: "M5 5l10 10M15 5L5 15",
  eye: "M10 4c4 0 7 3 8 6-1 3-4 6-8 6s-7-3-8-6c1-3 4-6 8-6zM10 8a2 2 0 100 4 2 2 0 000-4z",
  light: "M10 6a4 4 0 100 8 4 4 0 000-8zM10 1v2M10 17v2M1 10h2M17 10h2M4 4l1.5 1.5M14.5 14.5L16 16M16 4l-1.5 1.5M5.5 14.5L4 16",
  // A crescent whose bounding box is centred on (10,10): the previous one
  // sat low and left in its viewBox, so `place-items: center` centred a box
  // whose contents were off-centre -- the knob was right, the glyph was not.
  dark: "M17.5 10.66A7.5 7.5 0 119.34 2.5 5.83 5.83 0 0017.5 10.66z",
};

// Brand marks, which are not line icons: they are filled, they are drawn in
// their own box, and their shape is not ours to redraw. Kept apart from `PATHS`
// so the difference is in the data rather than in a branch someone has to
// notice -- every entry above is a 20-unit stroke, every entry here is a filled
// path with the viewBox its author drew it in.
const MARKS = {
  github: {
    viewBox: "0 0 24 24",
    d: "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577"
     + " 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7"
     + " 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07"
     + " 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93"
     + " 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267"
     + " 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24"
     + " 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81"
     + " 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24"
     + " 12.297c0-6.627-5.373-12-12-12",
  },
};

/** One icon, sized in ems so it scales with the text beside it.
 *
 * A name with no path draws a dotted square rather than nothing: an icon that
 * is silently invisible is a typo nobody finds, and this is the one place a
 * missing name can be reported without taking the page down.
 */
export default function Icon({ name, className = "" }) {
  const mark = MARKS[name];
  if (mark) {
    return (
      <svg className={`icon ${className}`} viewBox={mark.viewBox} aria-hidden="true"
           fill="currentColor">
        <path d={mark.d} />
      </svg>
    );
  }
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
