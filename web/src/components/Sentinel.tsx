import type { Framework } from "../types";
import "./sentinel.css";

/**
 * The over-reliance sentinel: four signals, all four shown.
 *
 * Two rules from the thesis shape this component, and both cut against what an
 * analytics panel would normally do.
 *
 * It shows all four signals rather than a single score, because
 * sec:build1 records that one signal carried the whole AUC -
 * "a detector resting on one signal is a detector with one failure mode". A
 * summary number would hide exactly the weakness the thesis wants visible.
 *
 * It has no threshold and no alert state. The thesis reports discrimination as
 * an AUC precisely "to avoid committing to a threshold", and 4:143 forbids the
 * sentinel from generating an alert or restricting what the student can do next.
 * These are values she can look at, not a verdict on her.
 *
 * This component is only ever rendered in the student's own view. There is no
 * teacher route that reaches it.
 */
export function Sentinel({
  signals,
  values,
}: {
  signals: Framework["sentinel"]["signals"];
  values: Record<string, number>;
}) {
  return (
    <div className="sentinel">
      {signals.map((sig) => {
        const v = values[sig.id] ?? 0;
        return (
          <div className="sentinel-row" key={sig.id}>
            <div>
              <p className="sentinel-name">{sig.name}</p>
              <p className="small faint">{sig.detects}</p>
            </div>
            <div
              className="sentinel-track"
              role="img"
              aria-label={`${sig.name}: ${v.toFixed(2)} of 1`}
            >
              <span className="sentinel-fill" style={{ width: `${v * 100}%` }} />
            </div>
            <span className="sentinel-value small">{v.toFixed(2)}</span>
          </div>
        );
      })}
    </div>
  );
}
