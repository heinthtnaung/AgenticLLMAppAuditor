import { useEffect, useState } from "react";
import Modal from "./Modal.jsx";
import { artifactUrl, fetchArtifactText } from "../api.js";

// How each kind of file is shown. Keyed on the suffix rather than on a name, so
// a file `artifacts/names.py` adds later is viewable without a second table to
// remember -- and the pair `findings.sarif.json` / `findings.openvex.json` are
// json to a reader whatever their middle word says.
const JSON_TEXT = "json";
const PLAIN_TEXT = "text";
const RENDERED = "html";

const HOW = [
  [".json", JSON_TEXT],
  [".md", PLAIN_TEXT],
  [".txt", PLAIN_TEXT],
  [".html", RENDERED],
];

/** How to show this file, or null when it is not something to read on a page. */
export function howToShow(name) {
  const found = HOW.find(([suffix]) => name.endsWith(suffix));
  return found ? found[1] : null;
}

/** The bytes as they are, pretty-printed when they parse as json.
 *
 * Reformatted only on success: a document that will not parse is shown exactly
 * as it sits on disk, because the thing a reader needs then is the broken text
 * and not a viewer's opinion of it.
 */
function readable(text, how) {
  if (how !== JSON_TEXT) return text;
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

/** One artifact, shown on the page rather than only downloadable.
 *
 * **HTML goes in a frame that grants nothing.** `sandbox=""` means no scripts
 * and no same-origin access. The markdown converter escapes all HTML today and
 * a test pins that with a real script tag, so this is not load-bearing against
 * the reports as they are; it is load-bearing against that escaping being
 * relaxed one module away, which is the kind of change nobody would think to
 * re-check this page for.
 *
 * Everything else is text in a `<pre>`, which React escapes, so a json document
 * carrying markup is shown and never run.
 */
export default function FileViewer({ runId, name, arm, onClose }) {
  const how = howToShow(name);
  const [text, setText] = useState(null);
  const [failed, setFailed] = useState(null);

  useEffect(() => {
    if (!how) return undefined;
    let watching = true;
    setText(null);
    setFailed(null);
    fetchArtifactText(runId, name, arm)
      .then((body) => { if (watching) setText(body); })
      .catch((error) => { if (watching) setFailed(error.message); });
    return () => { watching = false; };
  }, [runId, name, arm, how]);

  return (
    <Modal title={name} titleId="file-viewer-title" onClose={onClose} wide>
      {/* Refused by suffix before a byte is fetched. A PDF or an archive read
          as text is a screenful of mojibake, which looks like a corrupt file
          rather than a viewer that was asked the wrong question. */}
      {!how && (
        <p className="empty">
          {name} is not a document this page can show. Download it and open it
          in something that reads its format.
        </p>
      )}
      {failed !== null && (
        <p className="notice notice--error">
          <strong>That file could not be read.</strong>
          <span className="notice__detail">{failed}</span>
        </p>
      )}
      {how && text === null && failed === null && <p className="empty">Reading {name}…</p>}
      {how === RENDERED && text !== null && (
        <iframe className="viewer__frame" sandbox="" srcDoc={text} title={name} />
      )}
      {how && how !== RENDERED && text !== null && (
        <pre className="viewer__text mono">{readable(text, how)}</pre>
      )}
      <div className="form__actions overlay__actions">
        <a className="run run--secondary" href={artifactUrl(runId, name, arm)}
           download={name}>
          Download {name}
        </a>
      </div>
    </Modal>
  );
}
