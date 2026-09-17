import ExpandAll from "./ExpandAll.jsx";
import SourceWindow from "./SourceWindow.jsx";
import { useExpanded } from "../useExpanded.js";

/** Every LLM surface the extractor found, which is what the checks ran over.
 *
 * A row opens the lines it names. The source is read from the tree on disk
 * rather than carried in `surfaces.json`, which holds a location and never a
 * quotation -- so what opens is labelled as read now, not as audited evidence.
 */
export default function SurfaceList({ surfaces, runId }) {
  const rows = useExpanded(surfaces.map((surface) => surface.id));
  if (!surfaces.length) {
    return <p className="empty">No LLM surfaces found in this repository.</p>;
  }
  return (
    <>
      <ExpandAll allOpen={rows.allOpen} onToggle={rows.toggleAll} noun="line" />
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Kind</th><th>Name</th><th>Location</th><th>Language</th><th />
            </tr>
          </thead>
          <tbody>
            {surfaces.map((surface) => {
              const open = rows.isOpen(surface.id);
              return [
                <tr key={surface.id} className="row--clickable" aria-expanded={open}
                    onClick={() => rows.toggle(surface.id)}>
                  <td><span className="tag tag--rule">{surface.kind}</span></td>
                  <td className="mono">{surface.name}</td>
                  <td className="mono">{surface.file}:{surface.line}</td>
                  <td>{surface.language}</td>
                  <td className="row__action">
                    {/* The whole row toggles; this says so. A row that only
                        reacts to a click nobody knows to make is a feature
                        nobody finds. */}
                    <span className="details">{open ? "Hide" : "Details"}</span>
                  </td>
                </tr>,
                open ? (
                  <tr key={`${surface.id}-source`}>
                    <td className="prose" colSpan={5}>
                      <SourceWindow runId={runId} file={surface.file} line={surface.line} />
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
