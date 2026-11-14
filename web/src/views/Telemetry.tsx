import { useEffect, useState } from "react";
import { api } from "../api";
import { LatencyChart } from "../components/LatencyChart";
import { LayerFlow } from "../components/LayerFlow";
import { ReliabilityChart } from "../components/ReliabilityChart";
import { TierChart } from "../components/TierChart";
import type { CycleResult, Telemetry as TelemetryData } from "../types";
import "./telemetry.css";

/**
 * The measured numbers, and which layer produced them.
 *
 * This exists in the researcher view and deliberately nowhere near the student.
 * Chapter 10: "Reporting all six dimensions is a report card, not coaching."
 * A dashboard of a twelve year old's scores is the artifact the framework's
 * ownership commitment exists to prevent.
 *
 * Three kinds of number appear here and they are never mixed in one series:
 * what the thesis reported, what this repository measured, and what this
 * process has done since it started. They carry different weight, and a chart
 * that averaged them would be asserting they do not.
 */
export function TelemetryView({ result }: { result: CycleResult | null }) {
  const [data, setData] = useState<TelemetryData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const load = () =>
      api
        .telemetry()
        .then((d) => live && setData(d))
        .catch((e) => live && setError(String(e)));
    load();
    // The live pane accumulates as cycles run, so it refreshes. Slow enough
    // that nothing on screen jitters while being read.
    const id = window.setInterval(load, 5000);
    return () => {
      live = false;
      window.clearInterval(id);
    };
  }, []);

  if (error) return <p className="page quiet">{error}</p>;
  if (!data) return <p className="page quiet">Loading telemetry…</p>;

  const m = data.measured;

  return (
    <div className="page telemetry">
      <section className="tel-block">
        <h2>Which layers ran</h2>
        <p className="quiet measure">
          The last cycle, on the thesis&rsquo;s own diagram. The rule under each
          box is that layer&rsquo;s evidence grade: solid holds on its own,
          dashed was established in another subject area, dotted has never been
          tested.
        </p>
        <LayerFlow trace={result?.trace ?? []} />
      </section>

      <section className="tel-block">
        <h2>This process</h2>
        <LatencyChart telemetry={data} />
      </section>

      {m ? (
        <>
          <section className="tel-block">
            <h2>Agreement</h2>
            <p className="quiet measure tel-scope">{m.not_cross_vendor}</p>

            <div className="tel-stats">
              <Stat
                label="ICC(2,2)"
                value={m.overall_icc}
                ci={m.overall_icc_ci}
                against={data.reported.overall_icc}
                range={m.stability?.icc?.range}
              />
              <Stat
                label="grader gap"
                value={m.mean_grader_gap}
                ci={m.mean_grader_gap_ci}
                against={data.reported.mean_grader_gap}
                unit=" pts"
              />
              <Stat
                label="paraphrase shift"
                value={m.paraphrase_shift}
                ci={m.paraphrase_shift_ci}
                against={data.reported.paraphrase_shift}
                unit=" pts"
                range={m.stability?.paraphrase?.range}
              />
              <Stat
                label="sentinel AUC"
                value={m.sentinel?.auc ?? null}
                against={data.reported.sentinel_auc}
                range={m.stability?.auc?.range}
              />
            </div>

            <ReliabilityChart telemetry={data} />
            <TierChart telemetry={data} />
          </section>

          <section className="tel-block">
            <h2>Run-to-run stability</h2>
            <p className="quiet measure">
              The same {m.n_items} items, rescored {m.n_runs} times, identical
              models. A figure whose range here is comparable to its interval is
              not stable enough to quote from a single run.
            </p>
            <table className="tbl tel-runs">
              <thead>
                <tr>
                  <th>run</th>
                  <th className="num">ICC</th>
                  <th className="num">paraphrase</th>
                  <th className="num">AUC</th>
                </tr>
              </thead>
              <tbody>
                {m.per_run.map((r) => (
                  <tr key={r.run}>
                    <td>{r.run}</td>
                    <td className="num">{fmt(r.icc)}</td>
                    <td className="num">{fmt(r.paraphrase)}</td>
                    <td className="num">{fmt(r.auc)}</td>
                  </tr>
                ))}
                <tr className="tbl-total">
                  <td>range</td>
                  <td className="num">{fmt(m.stability?.icc?.range)}</td>
                  <td className="num">{fmt(m.stability?.paraphrase?.range)}</td>
                  <td className="num is-flag">
                    {fmt(m.stability?.auc?.range)}
                  </td>
                </tr>
              </tbody>
            </table>
          </section>

          {m.sentinel && (
            <section className="tel-block">
              <h2>Which sentinel signal is doing the work</h2>
              <p className="quiet measure">
                Chapter 6 warns that &ldquo;a detector resting on one signal is a
                detector with one failure mode.&rdquo; It reported excessive
                deference carrying the aggregate. Here a different signal does.
              </p>
              <div className="tel-signals">
                {Object.entries(m.sentinel.per_signal).map(([id, s]) => {
                  const share = s.of ? s.fired_on_high_risk / s.of : 0;
                  return (
                    <div className="tel-signal" key={id}>
                      <p className="tel-signal-name">{s.name}</p>
                      <div className="tel-signal-track">
                        <span style={{ width: `${share * 100}%` }} />
                      </div>
                      <p className="small quiet">
                        {s.fired_on_high_risk} of {s.of} high-risk
                      </p>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </>
      ) : (
        <section className="tel-block">
          <h2>No benchmark on disk</h2>
          <p className="quiet measure">
            Run <code className="artifact">python -m eval.benchmark --repeats 5</code>{" "}
            to populate the measured columns.
          </p>
        </section>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  ci,
  against,
  unit = "",
  range,
}: {
  label: string;
  value: number | null;
  ci?: [number, number] | null;
  against?: number;
  unit?: string;
  range?: number | null;
}) {
  return (
    <div className="tel-stat">
      <p className="label">{label}</p>
      <p className="tel-stat-value">
        {value != null ? value.toFixed(3) : "—"}
        <span className="tel-stat-unit">{unit}</span>
      </p>
      {ci && (
        <p className="small quiet">
          [{ci[0].toFixed(3)}, {ci[1].toFixed(3)}]
        </p>
      )}
      {against != null && (
        <p className="small faint">Ch.&nbsp;4: {against}</p>
      )}
      {range != null && (
        <p className={`small ${range > 0.05 ? "tel-unstable" : "faint"}`}>
          run range {range.toFixed(3)}
        </p>
      )}
    </div>
  );
}

function fmt(v: number | null | undefined) {
  return v == null ? "—" : v.toFixed(3);
}
