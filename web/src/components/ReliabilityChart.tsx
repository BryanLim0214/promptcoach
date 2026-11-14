import { scaleLinear } from "d3-scale";
import { useState } from "react";
import type { Telemetry } from "../types";
import "./charts.css";

/**
 * Per-dimension agreement: what Chapter 6 reported against what this
 * repository measured.
 *
 * Form. Two values per dimension, and the interesting quantity is the *gap*
 * between them - so a dumbbell, not paired bars. Paired bars would make the
 * reader compare six pairs of lengths; the dumbbell draws the comparison
 * itself, and the six rows sort so the biggest disagreement is unmissable.
 *
 * One axis. Weighted kappa, 0 to 1, shared by both series. Nothing else is
 * plotted here - agreement and, say, latency would be two charts.
 *
 * The Landis and Koch bands are background, not data. They carry the thesis's
 * own caveat: at n=30 a dimension's placement relative to a threshold "should
 * not be treated as a finding on its own", so they are drawn as the faintest
 * thing on the chart.
 */
export function ReliabilityChart({ telemetry }: { telemetry: Telemetry }) {
  const [hover, setHover] = useState<string | null>(null);
  const reported = telemetry.reported;
  const measured = telemetry.measured;

  const rows = reported.dimensions
    .map((d) => {
      const m = measured?.dimensions.find((x) => x.id === d.id);
      return {
        id: d.id,
        name: d.name,
        kind: d.kind,
        reported: d.kappa,
        measured: m?.kappa ?? null,
        gap: m?.kappa != null ? Math.abs(m.kappa - d.kappa) : 0,
      };
    })
    .sort((a, b) => b.gap - a.gap);

  const W = 640;
  const rowH = 30;
  // Room for the longest dimension name plus the "evaluative" flag beside it,
  // measured rather than guessed: at 12px the widest label is ~118px and the
  // flag ~62px. The first version overlapped them.
  const padL = 200;
  const padR = 48;
  const padT = 24;
  const H = padT + rows.length * rowH + 28;
  const x = scaleLinear().domain([0, 1]).range([padL, W - padR]);

  return (
    <figure className="chart">
      <figcaption className="chart-head">
        <h3>Per-dimension agreement</h3>
        <p className="small quiet">
          Weighted kappa. Sorted by how far the two disagree.
        </p>
      </figcaption>

      {/* Two series, so a legend is always present - identity is never
          carried by colour alone. */}
      <div className="chart-legend">
        <span className="key">
          <span className="key-mark is-reported" /> Chapter&nbsp;4, cross-vendor
        </span>
        <span className="key">
          <span className="key-mark is-measured" /> measured here, cross-version
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img"
        aria-label="Per dimension weighted kappa, reported against measured">
        {telemetry.landis_koch.map((band, i) => (
          <g key={band.label}>
            <rect
              x={x(band.from)}
              y={padT - 6}
              width={x(band.to) - x(band.from)}
              height={rows.length * rowH + 6}
              className={`band ${i % 2 ? "is-alt" : ""}`}
            />
            <text x={x(band.to) - 3} y={padT - 12} className="band-label">
              {band.label}
            </text>
          </g>
        ))}

        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => (
          <text key={t} x={x(t)} y={H - 12} className="axis-tick">
            {t.toFixed(1)}
          </text>
        ))}

        {rows.map((row, i) => {
          const y = padT + i * rowH + rowH / 2;
          const lit = hover === row.id;
          return (
            <g
              key={row.id}
              className={`dumbbell${lit ? " is-hover" : ""}`}
              onMouseEnter={() => setHover(row.id)}
              onMouseLeave={() => setHover(null)}
            >
              {/* Hit target larger than the marks. */}
              <rect
                x={0}
                y={y - rowH / 2}
                width={W}
                height={rowH}
                fill="transparent"
              />
              <text x={padL - 12} y={y + 4} className="row-label">
                {row.name}
              </text>
              {/* The flag sits left of the names, in its own gutter, so it
                  cannot collide with a long label. */}
              {row.kind === "evaluative" && (
                <text x={4} y={y + 4} className="row-flag">
                  evaluative
                </text>
              )}

              {row.measured != null && (
                <line
                  x1={x(row.reported)}
                  y1={y}
                  x2={x(row.measured)}
                  y2={y}
                  className="dumbbell-bar"
                />
              )}
              <circle
                cx={x(row.reported)}
                cy={y}
                r={5}
                className="dot is-reported"
              />
              {row.measured != null && (
                <circle
                  cx={x(row.measured)}
                  cy={y}
                  r={5}
                  className="dot is-measured"
                />
              )}

              <text x={W - padR + 8} y={y + 4} className="row-value">
                {row.measured != null ? row.measured.toFixed(2) : "—"}
              </text>

              <title>
                {row.name}: Chapter 6 {row.reported.toFixed(3)}, measured here{" "}
                {row.measured != null ? row.measured.toFixed(3) : "not measured"}
              </title>
            </g>
          );
        })}
      </svg>

      <p className="chart-note small quiet">
        {reported.caveat}
      </p>
    </figure>
  );
}
