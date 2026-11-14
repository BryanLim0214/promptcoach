import { scaleLinear } from "d3-scale";
import type { Telemetry } from "../types";
import "./charts.css";

/**
 * Tier separation, with intervals.
 *
 * Form. Three ordered groups on one measure, and the question is whether they
 * separate - so a dot with an interval, not a bar. Bars would invite reading
 * the *area* as the quantity when the quantity is a mean on a 1-to-4 scale that
 * does not start at zero; a bar chart with a non-zero baseline is the classic
 * way to lie with this data.
 *
 * The intervals are the addition to Chapter 6, which reports these means as
 * point estimates. Overlap or its absence is the whole result.
 */
export function TierChart({ telemetry }: { telemetry: Telemetry }) {
  const measured = telemetry.measured;
  const reported = telemetry.reported.tiers;
  if (!measured?.tiers) return null;

  const order = ["weak", "medium", "strong"] as const;
  const W = 640;
  const rowH = 40;
  //  n=…    tier name    | plot
  //  0-34   34-116       | 128+
  const padL = 128;
  const padR = 52;
  const padT = 18;
  const H = padT + order.length * rowH + 26;
  // Padded past the scale ends so a tier sitting near 1.0 - which weak always
  // does - is not drawn on top of the axis line.
  const x = scaleLinear().domain([0.85, 4.15]).range([padL, W - padR]);

  return (
    <figure className="chart">
      <figcaption className="chart-head">
        <h3>Tier separation</h3>
        <p className="small quiet">
          Researcher-assigned labels, fixed before scoring. A coherence check on
          constructed items, not a result about learners.
        </p>
      </figcaption>

      <div className="chart-legend">
        <span className="key">
          <span className="key-mark is-measured" /> measured, with 95% interval
        </span>
        <span className="key">
          <span className="key-mark is-reported" /> Chapter&nbsp;4
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img"
        aria-label="Mean score by tier with intervals">
        {[1, 2, 3, 4].map((t) => (
          <g key={t}>
            <line
              x1={x(t)}
              y1={padT}
              x2={x(t)}
              y2={padT + order.length * rowH}
              className="grid"
            />
            <text x={x(t)} y={H - 10} className="axis-tick">
              {t}
            </text>
          </g>
        ))}

        {order.map((tier, i) => {
          const m = measured.tiers[tier];
          const r = reported[tier];
          const y = padT + i * rowH + rowH / 2;
          if (m?.mean == null) return null;
          return (
            <g key={tier} className="tier-row">
              <text x={padL - 12} y={y + 4} className="row-label">
                {tier}
              </text>
              {/* Its own gutter, left of the names. Previously these two
                  overlapped on every row. */}
              <text x={4} y={y + 4} className="row-flag">
                n={m.n_items ?? m.n}
              </text>

              {m.ci && (
                <line
                  x1={x(m.ci[0])}
                  y1={y}
                  x2={x(m.ci[1])}
                  y2={y}
                  className="interval"
                />
              )}
              {m.ci && (
                <>
                  <line x1={x(m.ci[0])} y1={y - 5} x2={x(m.ci[0])} y2={y + 5} className="interval-cap" />
                  <line x1={x(m.ci[1])} y1={y - 5} x2={x(m.ci[1])} y2={y + 5} className="interval-cap" />
                </>
              )}

              {r != null && (
                <circle cx={x(r)} cy={y} r={5} className="dot is-reported" />
              )}
              <circle cx={x(m.mean)} cy={y} r={5.5} className="dot is-measured" />

              <text x={W - padR + 8} y={y + 4} className="row-value">
                {m.mean.toFixed(2)}
              </text>

              <title>
                {tier}: measured {m.mean.toFixed(3)}
                {m.ci ? ` [${m.ci[0].toFixed(2)}, ${m.ci[1].toFixed(2)}]` : ""}
                {r != null ? `, Chapter 6 reported ${r}` : ""}
              </title>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
