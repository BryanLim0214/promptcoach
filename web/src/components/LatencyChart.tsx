import { scaleLinear } from "d3-scale";
import type { Telemetry } from "../types";
import "./charts.css";

/**
 * Latency against the budget Chapter 12 sets.
 *
 * Form. One measure, a distribution, and two reference lines that are the whole
 * point of plotting it. A strip of every observed call plus a summary, rather
 * than a histogram: at these counts the individual points are readable and the
 * shape of the tail matters more than the bin heights.
 *
 * The reference lines are the reason this chart exists. Chapter 12 records
 * latency as an ecological threat with a 5.7s mean and 8.6s P95 budget for the
 * composed pipeline, "paid on every attempt, after the student has already
 * spent time speaking". A latency chart without the budget on it would be
 * telemetry; with it, it is a claim being checked.
 */
export function LatencyChart({ telemetry }: { telemetry: Telemetry }) {
  const live = telemetry.live;
  const budget = telemetry.budget;
  const points = live.latencies_ms ?? [];

  const maxObserved = points.length ? Math.max(...points) / 1000 : 1;
  // The axis keeps the budget in view even when every call lands far short of
  // it. The empty right-hand side is the finding, not wasted space - but the
  // lane is short so that finding costs a strip rather than a panel.
  const upper = Math.max(budget.pipeline_p95_s * 1.08, maxObserved * 1.1, 2);
  const headroom =
    live.latency_p95_ms != null
      ? budget.pipeline_p95_s / (live.latency_p95_ms / 1000)
      : null;

  const W = 640;
  const H = 104;
  const padL = 16;
  const padR = 16;
  const padT = 28;
  const lane = 34;

  const x = scaleLinear().domain([0, upper]).range([padL, W - padR]);

  const marks: { at: number; label: string; kind: string }[] = [
    { at: budget.reference_s, label: "3s reference", kind: "soft" },
    { at: budget.pipeline_mean_s, label: "pipeline mean budget", kind: "budget" },
    { at: budget.pipeline_p95_s, label: "pipeline P95 budget", kind: "budget" },
  ].filter((m) => m.at <= upper);

  return (
    <figure className="chart">
      <figcaption className="chart-head">
        <h3>Scoring latency</h3>
        <p className="small quiet">
          Every call this process has made, against Chapter 12&rsquo;s budget.
          {points.length === 0 && " Nothing measured yet — run a cycle."}
        </p>
      </figcaption>

      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img"
        aria-label={
          live.latency_mean_ms
            ? `Mean ${(live.latency_mean_ms / 1000).toFixed(2)} seconds, P95 ${((live.latency_p95_ms ?? 0) / 1000).toFixed(2)} seconds, against a budget of ${budget.pipeline_p95_s} seconds`
            : "No latency measured yet"
        }
      >
        {marks.map((m) => (
          <g key={m.label} className={`ref is-${m.kind}`}>
            <line x1={x(m.at)} y1={padT - 12} x2={x(m.at)} y2={padT + lane} />
            <text x={x(m.at) + 5} y={padT - 16} className="ref-label">
              {m.label}
            </text>
          </g>
        ))}

        <line
          x1={padL}
          y1={padT + lane / 2}
          x2={W - padR}
          y2={padT + lane / 2}
          className="strip-axis"
        />

        {points.map((ms, i) => (
          <circle
            key={i}
            cx={x(ms / 1000)}
            cy={padT + lane / 2}
            r={3.5}
            className="strip-dot"
          >
            <title>{(ms / 1000).toFixed(2)}s</title>
          </circle>
        ))}

        {live.latency_mean_ms != null && (
          <g className="strip-summary">
            <line
              x1={x(live.latency_mean_ms / 1000)}
              y1={padT + 6}
              x2={x(live.latency_mean_ms / 1000)}
              y2={padT + lane - 6}
            />
            <text
              x={x(live.latency_mean_ms / 1000)}
              y={padT + lane + 16}
              className="strip-summary-label"
            >
              mean {(live.latency_mean_ms / 1000).toFixed(2)}s
            </text>
          </g>
        )}

        {[0, upper / 2, upper].map((t) => (
          <text key={t} x={x(t)} y={H - 6} className="axis-tick">
            {t.toFixed(1)}s
          </text>
        ))}
      </svg>

      <dl className="stat-row">
        <div>
          <dt className="label">calls</dt>
          <dd>{live.calls}</dd>
        </div>
        <div>
          <dt className="label">mean</dt>
          <dd>
            {live.latency_mean_ms != null
              ? `${(live.latency_mean_ms / 1000).toFixed(2)}s`
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="label">p95</dt>
          <dd>
            {live.latency_p95_ms != null
              ? `${(live.latency_p95_ms / 1000).toFixed(2)}s`
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="label">headroom</dt>
          <dd>
            {headroom != null ? `${headroom.toFixed(1)}×` : "—"}
            <span className="tel-stat-unit"> under P95 budget</span>
          </dd>
        </div>
        <div>
          <dt className="label">engine</dt>
          <dd className="artifact">{live.engine}</dd>
        </div>
      </dl>

      <p className="chart-note small quiet">{budget.note}</p>
    </figure>
  );
}
