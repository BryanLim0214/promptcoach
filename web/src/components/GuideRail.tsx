import { useEffect, useRef } from "react";
import "./guide.css";

export interface Readout {
  label: string;
  value: string;
  /** Marks the one value the step is actually about. */
  key?: boolean;
}

/**
 * The walkthrough's controls, and the only place the framework is named while
 * a student's screen is on show.
 *
 * Deliberately not a product tour: no dark backdrop, no spotlight cutout, no
 * pulsing ring, no floating bubble with an arrow. Those obscure the thing they
 * are meant to be showing, and in a defence the screen belongs to the app.
 *
 * The rail is split down the middle because two people are reading it. On the
 * left, what is happening, in the same voice the app uses. On the right, which
 * layer did it, what the thesis requires of that layer, and the values this run
 * produced a second ago. The hairline between them is the same distinction the
 * whole application is built on: the experience, and the instrument underneath
 * it, never mixed into one register.
 */
export function GuideRail({
  step,
  total,
  title,
  caption,
  layer,
  mechanism,
  cite,
  readout,
  busy,
  typing,
  canAdvance,
  onNext,
  onSkipTyping,
  onExit,
  finished,
}: {
  step: number;
  total: number;
  title: string;
  caption: string;
  layer?: { n: number; name: string };
  mechanism?: string;
  cite?: string;
  readout: Readout[];
  busy: boolean;
  typing: boolean;
  canAdvance: boolean;
  onNext: () => void;
  onSkipTyping: () => void;
  onExit: () => void;
  finished: boolean;
}) {
  const rail = useRef<HTMLElement | null>(null);

  // The rail's height swings with the readout, so the page reserves exactly
  // what the rail occupies rather than a guess that is wrong at both ends.
  useEffect(() => {
    const node = rail.current;
    if (!node) return;
    const publish = () =>
      document.documentElement.style.setProperty(
        "--guide-h",
        `${node.offsetHeight}px`,
      );
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(node);
    return () => {
      observer.disconnect();
      document.documentElement.style.removeProperty("--guide-h");
    };
  }, []);

  return (
    <aside className="guide" aria-label="Guided walkthrough" ref={rail}>
      <div className="guide-inner">
        <div className="guide-progress" aria-hidden="true">
          {Array.from({ length: total }, (_, i) => (
            <span key={i} className={i <= step ? "is-done" : ""} />
          ))}
        </div>

        <div className="guide-body">
          <p className="guide-step label">
            {finished ? `Done · ${total} steps` : `Step ${step + 1} of ${total}`}
            <span className="guide-title">{title}</span>
          </p>
          <p className="guide-caption" aria-live="polite">
            {caption}
          </p>
        </div>

        <div className="guide-meta">
          {layer ? (
            <p className="guide-layer">
              <span className="guide-layer-n">Layer {layer.n}</span>
              <span className="guide-layer-name">{layer.name}</span>
            </p>
          ) : (
            <p className="guide-layer is-none">
              <span className="guide-layer-name">Outside the layers</span>
            </p>
          )}

          {mechanism && <p className="guide-mechanism">{mechanism}</p>}

          {readout.length > 0 && (
            <dl className="guide-readout">
              {readout.map((r) => (
                <div key={r.label} className={r.key ? "is-key" : ""}>
                  <dt>{r.label}</dt>
                  <dd>{r.value}</dd>
                </div>
              ))}
            </dl>
          )}

          {cite && <p className="guide-cite">{cite}</p>}
        </div>

        <div className="guide-actions">
          <button className="linkish" onClick={onExit}>
            {finished ? "Close" : "Exit walkthrough"}
          </button>
          {typing ? (
            <button className="go go-sm" onClick={onSkipTyping}>
              Skip typing
            </button>
          ) : (
            !finished && (
              <button
                className="go go-sm"
                onClick={onNext}
                disabled={busy || !canAdvance}
              >
                {busy ? "Working…" : "Next"}
              </button>
            )
          )}
        </div>
      </div>
    </aside>
  );
}
