import type { TraceStep } from "../types";
import "./layerflow.css";

/**
 * The five layers, with the ones that ran lit.
 *
 * This is the thesis's own `fig_five_layers`, made live. Its caption is the
 * reason it is drawn this way rather than as a row of five boxes with arrows:
 *
 *   "Layers 2 through 5 all read Layer 1's paired record, so the flow is not a
 *   strict chain from one layer to the next, which is why the order cannot be
 *   permuted."
 *
 * So the back-edges from Layer 1 are drawn explicitly. A left-to-right pipeline
 * would misdescribe the dependency, and it is the dependency that makes the
 * order unpermutable.
 *
 * Not a chart - a diagram. No axis, no scale, nothing quantitative.
 */

const LAYERS = [
  { id: "elicit", n: 1, name: "Elicit", owns: "intent + artifact" },
  { id: "measure", n: 2, name: "Measure", owns: "six scores" },
  { id: "diagnose", n: 3, name: "Diagnose", owns: "ranked failures" },
  { id: "respond", n: 4, name: "Respond", owns: "one level of help" },
  { id: "calibrate", n: 5, name: "Calibrate", owns: "difficulty + sentinel" },
];

const GRADE_TITLE: Record<string, string> = {
  direct: "Direct — a completed evaluation supports this",
  transferred: "Transferred — established in another subject area",
  argued: "Argued — follows from evidence, never tested",
};

export function LayerFlow({
  trace,
  active,
}: {
  trace: TraceStep[];
  active?: string | null;
}) {
  const ran = new Map(trace.map((s) => [s.layer, s]));

  const W = 880;
  const boxW = 152;
  const boxH = 58;
  const gap = (W - boxW * 5) / 4;
  const y = 6;
  // The four back-edges nest; the deepest sets the height. Previously H was a
  // round number chosen ahead of the geometry and left ~60px of empty canvas
  // under the curves.
  const dipOf = (i: number) => y + boxH + 18 + i * 11;
  const H = dipOf(4) + 10;
  const x = (i: number) => i * (boxW + gap);

  return (
    <figure className="flow">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="flow-svg"
        role="img"
        aria-label={
          ran.size
            ? `Layers that ran: ${[...ran.keys()].join(", ")}`
            : "No cycle has run yet"
        }
      >
        {/* Back-edges first, so the boxes sit over them. Layers 2-5 each read
            Layer 1 directly; that is the DAG edge, not decoration. */}
        {[1, 2, 3, 4].map((i) => {
          const from = x(0) + boxW / 2;
          const to = x(i) + boxW / 2;
          const dip = dipOf(i);
          const lit = ran.has(LAYERS[i].id) && ran.has("elicit");
          return (
            <path
              key={`back-${i}`}
              d={`M ${from} ${y + boxH} C ${from} ${dip}, ${to} ${dip}, ${to} ${y + boxH}`}
              className={`flow-back${lit ? " is-lit" : ""}`}
            />
          );
        })}

        {/* Forward edges */}
        {[0, 1, 2, 3].map((i) => {
          const lit = ran.has(LAYERS[i].id) && ran.has(LAYERS[i + 1].id);
          return (
            <line
              key={`fwd-${i}`}
              x1={x(i) + boxW}
              y1={y + boxH / 2}
              x2={x(i + 1)}
              y2={y + boxH / 2}
              className={`flow-edge${lit ? " is-lit" : ""}`}
            />
          );
        })}

        {LAYERS.map((layer, i) => {
          const step = ran.get(layer.id);
          const isActive = active === layer.id;
          const state = isActive ? "active" : step ? "ran" : "idle";
          return (
            <g key={layer.id} className={`flow-node is-${state}`}>
              <rect
                x={x(i)}
                y={y}
                width={boxW}
                height={boxH}
                rx={2}
                className="flow-box"
              />
              <text x={x(i) + 12} y={y + 21} className="flow-n">
                {layer.n}
              </text>
              <text x={x(i) + 30} y={y + 21} className="flow-name">
                {layer.name}
              </text>
              <text x={x(i) + 12} y={y + 40} className="flow-owns">
                {layer.owns}
              </text>
              {step && (
                <title>
                  {layer.name} — {GRADE_TITLE[step.grade] ?? step.grade}
                  {"\n"}
                  {step.contract_is_from_thesis
                    ? `Hands downstream: ${step.contract}`
                    : "The thesis states no downstream requirement for this layer."}
                </title>
              )}
              {/* Evidence grade as a rule weight under the box: solid holds,
                  dashed is borrowed, dotted has never been tested. Same
                  semiotics as everywhere else in the interface. */}
              {step && (
                <line
                  x1={x(i) + 12}
                  y1={y + boxH - 8}
                  x2={x(i) + 44}
                  y2={y + boxH - 8}
                  className={`flow-grade is-${step.grade}`}
                />
              )}
            </g>
          );
        })}
      </svg>

      <figcaption className="flow-caption small quiet">
        Layers 2 to 5 all read Layer 1&rsquo;s paired record — the curves below.
        The flow is not a chain, which is why the order cannot be permuted.
        {ran.size === 0 && " Nothing has run yet."}
      </figcaption>
    </figure>
  );
}
