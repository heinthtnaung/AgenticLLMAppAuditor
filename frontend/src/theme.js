// Which palette the page shows, and remembering the choice.
//
// Three states, not two. "system" is the default and sets no attribute at all,
// so `prefers-color-scheme` in tokens.css decides -- which is what a viewer who
// has never touched the toggle should get. Choosing light or dark stamps
// `data-theme` on the root element, and those blocks are written to win over
// the media query in both directions.

export const SYSTEM = "system";
export const LIGHT = "light";
export const DARK = "dark";

// The values a stored choice may hold. Anything else falls back to `system`.
export const THEMES = [SYSTEM, LIGHT, DARK];

const STORED_UNDER = "auditor-theme";

/** The remembered choice, or system when there is none or storage is barred. */
export function storedTheme() {
  // A private window, cleared site data or a browser set to block storage all
  // reach here, and two of the three throw rather than returning null.
  try {
    const found = localStorage.getItem(STORED_UNDER);
    return THEMES.includes(found) ? found : SYSTEM;
  } catch {
    return SYSTEM;
  }
}

/** Show a theme. Writes no storage: rendering is not a choice. */
export function showTheme(theme) {
  const wanted = THEMES.includes(theme) ? theme : SYSTEM;
  if (wanted === SYSTEM) {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", wanted);
  }
  return wanted;
}

/** Remember a theme. Called when someone chooses one, never on a render. */
export function rememberTheme(theme) {
  const wanted = THEMES.includes(theme) ? theme : SYSTEM;
  try {
    localStorage.setItem(STORED_UNDER, wanted);
  } catch {
    // Remembering is a convenience; not being allowed to is not a failure.
  }
  return wanted;
}

/** Which palette is actually showing, resolving `system` against the machine.
 *
 * The control is a two-state switch, so it needs to know what is on screen
 * rather than what was chosen -- and `system` is still the stored default, so a
 * first visit follows the machine before anyone has touched anything.
 */
export function effectiveTheme(theme = storedTheme()) {
  if (theme !== SYSTEM) return theme;
  // `matchMedia` is absent in some embedded webviews, and a page that cannot
  // ask should show the palette `tokens.css` defines on bare `:root`.
  const asks = window.matchMedia?.("(prefers-color-scheme: light)");
  return asks?.matches ? LIGHT : DARK;
}
