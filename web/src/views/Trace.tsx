import { Collapsible } from "radix-ui";
import { GradeMark } from "../components/GradeMark";
import type { CycleResult } from "../types";
import "./trace.css";

/**
 * The design-to-code view.
 *
 * Each layer that ran, opened: the contract sentence from Chapter 10, the value
 * the code actually produced, the evidence grade of the claim the layer rests
 * on, and its limit. This is what makes "it follows the design" checkable rather
 * than asserted - the reader compares the manuscript's sentence with the payload
 * beside it.
 *
 * Layer 5 is the interesting row. It shows "no downstream requirement is stated"
 * where the others show a quotation, because Layers 1-4 each end with a
 * "Requirement passed downstream" sentence and Layer 5 does not. The gap in the
 * thesis is visible rather than papered over.
 */
export function TraceView({ result }: { result: CycleResult | null }) {
  if (!result) {
    return (
      <div className="page">
        <p className="quiet measure">
          Run a cycle in the Session view and every layer will be laid out here
          with its contract, its output, and its evidence grade.
        </p>
      </div>
    );
  }

  return (
    <div className="page">
      <h2 className="trace-title">
        Cycle stopped at <em>{result.stopped_at}</em>
      </h2>
      <p className="quiet measure">
        Each layer below shows what the thesis requires it to hand downstream,
        beside what this implementation actually produced.
      </p>

      <div className="trace">
        {result.trace.map((step, i) => (
          <Collapsible.Root key={`${step.layer}-${i}`} defaultOpen={i === 0}>
            <div className="trace-row">
              <Collapsible.Trigger className="trace-trigger">
                <span className="trace-n">{i + 1}</span>
                <span className="trace-layer">{step.layer}</span>
                <span className="trace-contract small quiet">
                  {step.contract_is_from_thesis ? (
                    <>“{step.contract}”</>
                  ) : (
                    <em>{step.cite}</em>
                  )}
                </span>
                <GradeMark grade={step.grade} />
              </Collapsible.Trigger>

              <Collapsible.Content className="trace-content">
                <dl className="trace-meta">
                  <div>
                    <dt className="label">Contract</dt>
                    <dd>
                      {step.contract_is_from_thesis ? (
                        <>
                          “{step.contract}”{" "}
                          <span className="faint small">{step.cite}</span>
                        </>
                      ) : (
                        <span className="quiet">
                          The thesis states no downstream requirement for this
                          layer. The shape below is this implementation's.
                        </span>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="label">Rests on</dt>
                    <dd>
                      {step.component} — {step.grade_basis}
                    </dd>
                  </div>
                  <div>
                    <dt className="label">Limit</dt>
                    <dd className="quiet">{step.grade_limit}</dd>
                  </div>
                </dl>
                <pre className="trace-json artifact">
                  {JSON.stringify(step.output, null, 2)}
                </pre>
              </Collapsible.Content>
            </div>
          </Collapsible.Root>
        ))}
      </div>
    </div>
  );
}
