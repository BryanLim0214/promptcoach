import { scaleLinear } from "d3-scale";
import type { Agreement, Dimension, DimensionScore } from "../types";
import "./meter.css";

/**
 * Six dimensions, and - when the cross-model protocol is running - two ticks per
 * dimension with the divergence between them drawn.
 *
 * Rater independence is the thesis's strongest evidenced claim, so the interface
 * shows it being checked rather than asserting it in a caption. When one scorer
 * runs, there is one tick. When two organisations score, there are two and the
 * distance between them is visible.
 *
 * Evaluative dimensions are hatched, permanently. 7:116 makes lowering
 * confidence on Iteration Awareness and Reflection normative, and Reflection's
 * weighted kappa is 0.645 against Specificity's 0.967. A meter that drew all six
 * identically would be overstating two of them.
 *
 * A dimension nobody could score renders as an explicit "not scored", never as a
 * bar of length zero. A failure to measure is not a measurement of nothing.
 */
export function DimensionMeter({
  dimensions,
  scores,
  agreement,
  min,
  max,
}: {
  dimensions: Dimension[];
  scores: Record<string, DimensionScore>;
  agreement: Agreement | null;
  min: number;
  max: number;
}) {
  const x = scaleLinear().domain([min, max]).range([0, 100]);

  return (
    <div className="meter">
      <div className="meter-scale" aria-hidden="true">
        {[1, 2, 3, 4].map((v) => (
          <span key={v} style={{ left: `${x(v)}%` }}>
            {v}
          </span>
        ))}
      </div>

      {dimensions.map((dim) => {
        const score = scores[dim.id];
        const gap = agreement?.per_dimension_gap?.[dim.id];
        const value = score?.value ?? null;
        const other =
          value !== null && gap !== undefined ? clamp(value - gap, min, max) : null;

        return (
          <div className="meter-row" key={dim.id}>
            <div className="meter-name">
              <span>{dim.name}</span>
              {dim.kind === "evaluative" && (
                <span className="label meter-flag" title={`weighted kappa ${dim.weighted_kappa}`}>
                  lower confidence
                </span>
              )}
            </div>

            <div
              className={`meter-track${dim.kind === "evaluative" ? " is-evaluative" : ""}`}
              role="img"
              aria-label={
                value === null
                  ? `${dim.name}: not scored`
                  : `${dim.name}: ${value} of ${max}` +
                    (other !== null
                      ? `, second scorer ${other}, gap ${gap}`
                      : "")
              }
            >
              {value === null ? (
                <span className="meter-unscored label">not scored</span>
              ) : (
                <>
                  {other !== null && other !== value && (
                    <span
                      className="meter-divergence"
                      style={{
                        left: `${Math.min(x(value), x(other))}%`,
                        width: `${Math.abs(x(value) - x(other))}%`,
                      }}
                    />
                  )}
                  <span
                    className="meter-tick is-primary"
                    style={{
                      left: `${x(value)}%`,
                      background: `var(--dim-${dim.id})`,
                    }}
                  />
                  {other !== null && (
                    <span
                      className="meter-tick is-secondary"
                      style={{ left: `${x(other)}%` }}
                    />
                  )}
                </>
              )}
            </div>

            <div className="meter-value">
              {value === null ? (
                <span className="faint">—</span>
              ) : (
                <>
                  <strong>{value}</strong>
                  <span className="faint small"> ·{score.confidence.toFixed(2)}</span>
                </>
              )}
            </div>
          </div>
        );
      })}

      {dimensions.some((d) => scores[d.id]?.evidence_span) && (
        <dl className="meter-spans">
          {dimensions.map((dim) => {
            const span = scores[dim.id]?.evidence_span;
            if (!span) return null;
            return (
              <div key={dim.id}>
                <dt className="label">{dim.name}</dt>
                <dd className="artifact small">“{span}”</dd>
              </div>
            );
          })}
        </dl>
      )}
    </div>
  );
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}
