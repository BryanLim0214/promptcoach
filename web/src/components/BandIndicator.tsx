import type { Band } from "../types";
import "./band.css";

/**
 * The five-band progression, drawn with the break the thesis requires.
 *
 * The obvious component here is a five-step progress bar. It would be wrong, and
 * the thesis says exactly why (7:309):
 *
 *   "The two axes are not commensurable. Nothing in the construction says a band
 *   4 task is harder than a band 3 task; it says band 4 demands a different kind
 *   of work."
 *
 * Bands 1-3 are ordered by how many planning dimensions a task needs unprompted.
 * Bands 4-5 are ordered by whether an output is visible while she evaluates.
 * Those are two orderings laid end to end, so this draws two groups with a gap
 * and a labelled break between them, and never one continuous track.
 *
 * This is the clearest case in the interface of a design decision that comes
 * from the argument rather than from taste.
 */
export function BandIndicator({
  bands,
  current,
  join,
}: {
  bands: Band[];
  current: number;
  join: number[];
}) {
  const [lastBefore] = join;
  const groupA = bands.filter((b) => b.band <= lastBefore);
  const groupB = bands.filter((b) => b.band > lastBefore);

  return (
    <div className="bands" role="img" aria-label={`Current band: ${current} of 5`}>
      <Group bands={groupA} current={current} axisLabel="planning dimensions required" />
      <div className="band-break" aria-hidden="true">
        <span className="band-break-rule" />
        <span className="label band-break-note">axes not comparable</span>
        <span className="band-break-rule" />
      </div>
      <Group bands={groupB} current={current} axisLabel="output visible while evaluating" />
    </div>
  );
}

function Group({
  bands,
  current,
  axisLabel,
}: {
  bands: Band[];
  current: number;
  axisLabel: string;
}) {
  return (
    <div className="band-group">
      <ol className="band-list">
        {bands.map((b) => (
          <li
            key={b.band}
            className={`band${b.band === current ? " is-current" : ""}`}
            aria-current={b.band === current}
          >
            <span className="band-num">{b.band}</span>
            <span className="band-requires small">{b.requires}</span>
          </li>
        ))}
      </ol>
      <p className="label band-axis">{axisLabel}</p>
    </div>
  );
}
