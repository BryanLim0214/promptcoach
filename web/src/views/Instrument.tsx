import { Cite } from "../components/Cite";
import { GradeMark } from "../components/GradeMark";
import type { Framework, Grade, NeedBasis, PolicyPayload } from "../types";
import "./instrument.css";

/**
 * The specification itself, with every claim's evidence grade beside it.
 *
 * Two tables do the real work. The first is the framework's twenty-four graded
 * components with both columns - the mechanism grade and the need basis - and
 * the counts at the top are pinned by a test: 4 Direct, 10 Transferred, 10
 * Argued; 4 User studies, 18 Builds, 2 Argument. The second is the twenty-four things
 * the thesis does not specify, each with what this implementation chose and why.
 *
 * A reader who wants to attack the thesis is told where to start, in the
 * thesis's own words.
 */
export function InstrumentView({
  framework,
  policy,
}: {
  framework: Framework;
  policy: PolicyPayload;
}) {
  const counts = framework.grades.counts;
  const needs = framework.grades.need_counts;

  return (
    <div className="page instrument">
      <section>
        <h2>Evidence</h2>
        <p className="quiet measure">
          Every component carries two grades. The mechanism grade is the route
          from evidence to the claim that it works. The need basis is where the
          need for it was observed: in the user studies, in the builds, or
          in an argument. Neither is importance.
        </p>
        <div className="grade-legend">
          {(["direct", "transferred", "argued"] as Grade[]).map((g) => (
            <div key={g}>
              <GradeMark grade={g} />
              <span className="grade-count">{counts[g]}</span>
              <p className="small quiet">{framework.grades.definitions[g]}</p>
            </div>
          ))}
        </div>

        <ul className="need-legend small">
          {(["students", "builds", "argument"] as NeedBasis[]).map((n) => (
            <li key={n}>
              <span className="label">{framework.grades.need_labels[n]}</span>{" "}
              <span className="grade-count">{needs[n]}</span>{" "}
              <span className="quiet">{framework.grades.need_definitions[n]}</span>
            </li>
          ))}
        </ul>

        <table className="tbl">
          <thead>
            <tr>
              <th>Component</th>
              <th>Grade</th>
              <th>Need</th>
              <th>Basis</th>
              <th>Limit</th>
            </tr>
          </thead>
          <tbody>
            {framework.grades.components.map((c) => (
              <tr
                key={c.id}
                className={
                  framework.grades.originals.includes(c.id) ? "is-original" : ""
                }
              >
                <td>
                  {c.name}
                  {framework.grades.originals.includes(c.id) && (
                    <span className="label tbl-flag">the thesis's own</span>
                  )}
                </td>
                <td>
                  <GradeMark grade={c.grade} showLabel={false} />
                </td>
                <td className="small">
                  {c.need_label}
                  {c.requirement && (
                    <span className="label tbl-flag">{c.requirement}</span>
                  )}
                </td>
                <td className="small">{c.basis}</td>
                <td className="small quiet">{c.limit}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {Object.entries(framework.grades.removed).map(([id, r]) => (
          <p key={id} className="small quiet measure">
            <span className="label">Removed after implementation</span> {r.why}
          </p>
        ))}
      </section>

      <section>
        <h2>The rubric</h2>
        <p className="quiet measure">{framework.reliability.caveat}</p>
        <table className="tbl">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Measures</th>
              <th>κ</th>
              <th>±1</th>
            </tr>
          </thead>
          <tbody>
            {framework.dimensions.map((d) => (
              <tr key={d.id}>
                <td>
                  <span
                    className="swatch"
                    style={{ background: `var(--dim-${d.id})` }}
                    aria-hidden="true"
                  />
                  {d.name}
                  {d.kind === "evaluative" && (
                    <span className="label tbl-flag">evaluative</span>
                  )}
                </td>
                <td className="small">{d.measures}</td>
                <td className="num">{d.weighted_kappa}</td>
                <td className="num">{d.within_one_pct}%</td>
              </tr>
            ))}
            <tr className="tbl-total">
              <td>Overall</td>
              <td className="small quiet">ICC(2,2) on the overall score</td>
              <td className="num quiet" title="tab:agreement gives n/a">
                n/a
              </td>
              <td className="num">{framework.reliability.overall_icc}</td>
            </tr>
          </tbody>
        </table>
        <p className="small faint measure">{framework.reliability.third_bar}</p>
      </section>

      <section>
        <h2>Taxonomy</h2>
        <p className="quiet measure">{framework.taxonomy_notes.circularity}</p>
        <table className="tbl">
          <thead>
            <tr>
              <th>Failure</th>
              <th>What she did</th>
              <th>Response implied</th>
              <th>Visible in</th>
            </tr>
          </thead>
          <tbody>
            {framework.taxonomy.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td className="small">{c.student_did}</td>
                <td className="small quiet">{c.response_implied}</td>
                <td className="small faint">
                  {c.detectable_from.replace(/_/g, " ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>What the thesis does not specify</h2>
        <p className="quiet measure">
          {policy.unspecified.length} things an implementation needs and the
          manuscript leaves open. Every value below is this implementation's,
          with the passage proving it is open and the caveat that goes with
          relying on it. Some are removals or refusals rather than values, and
          two are switches that exist so F7 and F8 can be run.
        </p>
        <ul className="choices">
          {policy.choices.map((c) => (
            <li key={c.id}>
              <div className="choice-head">
                <code className="choice-id">{c.id}</code>
                <span className="choice-value artifact">
                  {formatValue(c.value)}
                </span>
                <Cite label={c.id} source="policy">
                  <p>
                    <span className="label">Thesis says</span> {c.thesis_says}
                  </p>
                  <p style={{ marginTop: 8 }}>
                    <span className="label">Borrowed from</span> {c.borrowed_from}
                  </p>
                  <p style={{ marginTop: 8 }}>
                    <span className="label">Caveat</span> {c.caveat}
                  </p>
                </Cite>
              </div>
              <p className="small quiet">{c.caveat}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function formatValue(v: unknown): string {
  if (v === null) return "none";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
