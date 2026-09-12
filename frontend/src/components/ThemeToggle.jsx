import { useEffect, useState } from "react";
import Icon from "./Icon.jsx";
import { effectiveTheme, rememberTheme, showTheme, DARK, LIGHT } from "../theme.js";

/** A two-state switch between the light and dark palettes.
 *
 * No visible label, so the accessible name carries the whole meaning -- a bare
 * switch with nothing beside it is unreadable to a screen reader otherwise.
 * `system` stays the stored default until someone moves this: the mount effect
 * only *shows* a theme, and storage is written in the click handler alone. The
 * initial position therefore comes from `effectiveTheme`, so on any visit
 * before a choice is made it shows what the machine asked for.
 */
export default function ThemeToggle() {
  const [theme, setTheme] = useState(() => effectiveTheme());
  const dark = theme === DARK;

  // Shown in an effect, not during render: setting an attribute on
  // documentElement is a side effect on something React does not own. It shows
  // and does not remember, so a render never turns the default into a choice.
  useEffect(() => { showTheme(theme); }, [theme]);

  return (
    <button type="button" role="switch" aria-checked={dark}
            className={`switch${dark ? " switch--on" : ""}`}
            aria-label="Dark theme"
            title={dark ? "Dark theme" : "Light theme"}
            onClick={() => {
              const next = dark ? LIGHT : DARK;
              rememberTheme(next);
              setTheme(next);
            }}>
      <span className="switch__knob">
        <Icon name={dark ? "dark" : "light"} />
      </span>
    </button>
  );
}
