import { useEffect } from "react";
import { createPortal } from "react-dom";
import Icon from "./Icon.jsx";

/** A fixed scrim with one card on it, and whatever the caller puts inside.
 *
 * Its own component because two things need it -- the run overlay and the file
 * viewer -- and a second copy of a scrim is a second `z-index` to keep in step
 * with the rest of the stylesheet.
 *
 * `onClose` is optional, and its absence is meaningful rather than a default:
 * the run overlay passes none, because an audit cannot be cancelled and a
 * dismiss would hide a run that carries on. So Escape is bound only when there
 * is something for it to do.
 *
 * **Portalled to `document.body`, and that is load-bearing.** `position: fixed`
 * resolves against the viewport only while no ancestor establishes a containing
 * block -- and `transform`, `filter`, `backdrop-filter`, `perspective`,
 * `will-change` and `contain` all establish one. `.card` declares
 * `backdrop-filter: blur(14px)`, and the file viewer is opened from the
 * download list *inside* a card, so the scrim was laid out from that card's
 * top-left corner instead of the window's: a modal hanging off to the right,
 * measured from the rail. A portal is the fix rather than removing the blur,
 * because any card this ever opens from would do the same thing again.
 */
export default function Modal({ title, titleId, onClose, wide, children }) {
  useEffect(() => {
    if (!onClose) return undefined;
    const close = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  return createPortal((
    <div className="overlay" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      {/* Width as a data attribute, not a second class: a braced `className`
          leaves the source-to-bundle freshness join. See
          `tests/web/test_built_page_shipped.py`. */}
      <div className="overlay__card card" data-wide={wide || undefined}>
        <div className="overlay__head">
          <h2 className="card__title" id={titleId}>{title}</h2>
          {onClose && (
            <button type="button" className="overlay__close" onClick={onClose}
                    aria-label="Close">
              <Icon name="close" />
            </button>
          )}
        </div>
        {children}
      </div>
    </div>
  ), document.body);
}
