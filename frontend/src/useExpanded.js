// Which rows of a table are open, and the one control that opens them all.
//
// Shared by the findings and the surfaces because both grew the same three
// behaviours -- a row toggles, a button toggles every row, and the button has
// to say which it will do. Two copies of that had already started to differ.

import { useState } from "react";

/** Open/closed state for a list of row ids. */
export function useExpanded(ids) {
  const [open, setOpen] = useState(() => new Set());

  // Measured against the rows on screen, not every row ever seen: a filtered
  // list must be able to say "all of these are open" without the ones the
  // filter is hiding making that false.
  const allOpen = ids.length > 0 && ids.every((id) => open.has(id));

  return {
    allOpen,
    isOpen: (id) => open.has(id),
    toggle: (id) => setOpen((was) => {
      const next = new Set(was);
      if (!next.delete(id)) next.add(id);
      return next;
    }),
    toggleAll: () => setOpen((was) => {
      const next = new Set(was);
      ids.forEach((id) => (allOpen ? next.delete(id) : next.add(id)));
      return next;
    }),
  };
}
