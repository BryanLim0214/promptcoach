import type { Dimension } from "../types";
import "./gap.css";

/**
 * The intent-artifact gap, drawn.
 *
 * This is the organising idea of the whole interface. The thesis's core object
 * is the distance between what a student meant and what she typed - "the single
 * most informative signal available, and unavailable to any system that captures
 * only the artifact" (7:98). That is a spatial fact, so it is rendered as one.
 *
 * Her speech sits left in a serif, because speech is not interface text. Her
 * prompt sits right in monospace, because it is the object under examination.
 * Between them is a gutter, and each piece of thinking that appears on the left
 * and not on the right is drawn as a thread that starts at her words and ends in
 * mid-air.
 *
 * In the Chapter 11 example she says "she's like seven" and "a few sentences",
 * types "explain why the sky is blue", and three threads dangle. The reader
 * should see that before reading a single word of feedback.
 */
export function Gap({
  intent,
  artifact,
  modality,
  dropped,
  dimensions,
}: {
  intent: string;
  artifact: string;
  modality: string;
  /** Dimension ids present in what she said and absent from what she typed. */
  dropped: string[];
  dimensions: Dimension[];
}) {
  const byId = new Map(dimensions.map((d) => [d.id, d]));
  const carried = dropped.length === 0;
  const rowHeight = 34;
  const height = Math.max(96, dropped.length * rowHeight + 32);

  return (
    <div className="gap">
      <section className="gap-side" aria-labelledby="gap-intent-h">
        <h3 className="label" id="gap-intent-h">
          What she was trying to do
          <span className="faint"> · {modality}</span>
        </h3>
        <p className="speech">{intent || <span className="faint">—</span>}</p>
      </section>

      <div
        className="gap-gutter"
        role="img"
        aria-label={
          carried
            ? "Everything she said also appears in her prompt."
            : `${dropped.length} things she said did not reach her prompt: ` +
              dropped.map((d) => byId.get(d)?.name ?? d).join(", ")
        }
      >
        <svg
          width="100%"
          height={height}
          viewBox={`0 0 120 ${height}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {carried ? (
            <line
              x1="0"
              y1={height / 2}
              x2="120"
              y2={height / 2}
              stroke="var(--rule-strong)"
              strokeWidth="1.5"
            />
          ) : (
            dropped.map((id, i) => {
              const y = 22 + i * rowHeight;
              const colour = `var(--dim-${id}, var(--ink-faint))`;
              return (
                <g key={id} className="thread">
                  <path
                    d={`M 0 ${y} C 34 ${y}, 46 ${y + 9}, 78 ${y + 9}`}
                    fill="none"
                    stroke={colour}
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                  {/* An open end, not an arrowhead. The thread stops; it does
                      not arrive anywhere. */}
                  <circle
                    cx="80"
                    cy={y + 9}
                    r="2.5"
                    fill="var(--paper)"
                    stroke={colour}
                    strokeWidth="1.5"
                  />
                </g>
              );
            })
          )}
        </svg>

        <ul className="gap-threads">
          {carried ? (
            <li className="label">carried through</li>
          ) : (
            dropped.map((id) => (
              <li
                key={id}
                className="label"
                style={{ color: `var(--dim-${id}, var(--ink-faint))` }}
              >
                {byId.get(id)?.name ?? id}
              </li>
            ))
          )}
        </ul>
      </div>

      <section className="gap-side" aria-labelledby="gap-artifact-h">
        <h3 className="label" id="gap-artifact-h">
          What she typed
        </h3>
        <p className="artifact">{artifact || <span className="faint">—</span>}</p>
      </section>
    </div>
  );
}
