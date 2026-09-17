import Icon from "./Icon.jsx";
import FileViewer, { howToShow } from "./FileViewer.jsx";
import { useState } from "react";
import { artifactUrl, bundleUrl } from "../api.js";
import { bytes } from "../format.js";

/** One file: a control that opens it, its size, and a link that saves it.
 *
 * Its own component because the open/shut branch made the panel's `map` a
 * third level of nesting. Where `howToShow` refuses the name, the eye is
 * **absent rather than disabled** -- nothing to click and nothing that looks
 * clickable.
 */
function DownloadRow({ runId, file, onOpen }) {
  return (
    <div className="download">
      {howToShow(file.name) ? (
        <button type="button" className="download__open" onClick={onOpen}>
          <Icon name="eye" />
          <span className="download__name mono">{file.name}</span>
        </button>
      ) : (
        <span className="download__open download__open--shut">
          <span className="download__name mono">{file.name}</span>
        </span>
      )}
      <span className="download__size">{bytes(file.bytes)}</span>
      <a className="download__save" href={artifactUrl(runId, file.name)}
         download={file.name} aria-label={`Download ${file.name}`}>
        <Icon name="download" />
      </a>
    </div>
  );
}

/** Every file this run left on disk, each as a download.
 *
 * The per-file list is folded away by default. Sixteen links is most of the
 * rail, and the archive below is what a reader usually wants -- the individual
 * files are for someone who came for one of them by name.
 *
 * **Each row is two controls, not one.** The name opens the file on the page;
 * the arrow downloads it. A row that only downloaded meant reading a 300-byte
 * json document took a round trip through the filesystem -- and a row that only
 * viewed would have no answer for a PDF.
 */
export default function DownloadPanel({ runId, listing, current }) {
  const [listed, setListed] = useState(false);
  const [viewing, setViewing] = useState(null);
  if (!listing) return null;
  if (!listing.files.length) {
    return (
      <p className="empty">
        This run wrote no files that are still on disk. Its findings are stored
        and shown in the Findings panel; the artifacts themselves are gone.
      </p>
    );
  }
  const total = listing.files.reduce((sum, file) => sum + file.bytes, 0);
  return (
    <>
      {!current && (
        <p className="notice notice--error">
          <strong>A later run overwrote these files.</strong>
          <span className="notice__detail">
            Artifacts are keyed on the app name, not on the run, so what is on
            disk is no longer what this run produced. The downloads are refused
            rather than serving another run&rsquo;s bytes under this
            run&rsquo;s timestamp.
          </span>
        </p>
      )}
      <button type="button" className="disclose" aria-expanded={listed}
              onClick={() => setListed(!listed)}>
        <Icon name="chevron" className={listed ? "disclose__mark disclose__mark--open"
                                               : "disclose__mark"} />
        {listed ? "Hide the file list" : `List the ${listing.files.length} files`}
      </button>

      {listed && (
      <div className="downloads">
        {listing.files.map((file) => (
          <DownloadRow key={file.name} runId={runId} file={file}
                       onOpen={() => setViewing(file.name)} />
        ))}
      </div>
      )}
      {viewing && (
        <FileViewer runId={runId} name={viewing}
                    onClose={() => setViewing(null)} />
      )}
      <a className="run run--secondary" href={bundleUrl(runId)} download>
        <Icon name="download" />
        Download all {listing.files.length} files ({bytes(total)})
      </a>
    </>
  );
}
