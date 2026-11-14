import type { AboutPayload, Framework, Health } from "../types";
import "./about.css";

/**
 * The chapters that are not the framework: the thesis statement and research
 * questions (1), background (2), the requirements the user studies gave
 * (9), threats (12) and remaining work (13).
 *
 * This view exists because the app can be read as a claim, and the thesis is
 * careful about what it claims. The scope paragraph and the threats are quoted
 * rather than summarised, so what the software says about itself is what the
 * manuscript says about itself.
 */
export function AboutView({
  about,
  framework,
  health,
}: {
  about: AboutPayload;
  framework: Framework;
  health: Health | null;
}) {
  return (
    <div className="page about">
      <section className="about-lede">
        <h2>What this is</h2>
        <p className="about-big measure">{about.conclusion.text}</p>
        <p className="measure quiet">{about.thesis_statement.text}</p>
      </section>

      <section className="about-two">
        <div>
          <h3 className="label">Running this shows</h3>
          <p className="measure">{about.shows}</p>
        </div>
        <div>
          <h3 className="label">It does not show</h3>
          <p className="measure quiet">{about.does_not_show}</p>
        </div>
      </section>

      <hr className="rule" />

      <section>
        <h3>Research questions</h3>
        <ol className="about-rq">
          {about.research_questions.map((q, i) => (
            <li key={i} className="measure">
              {q}
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h3>Requirements from the user studies</h3>
        <ol className="about-rq">
          {about.requirements.map((r) => (
            <li key={r.id} className="measure">
              <strong>{r.id}.</strong> {r.requirement}{" "}
              <span className="small quiet">({r.strength})</span>
            </li>
          ))}
        </ol>
      </section>

      <Passage p={about.scope} />
      <Passage p={about.why_the_boundary} />
      <Passage p={about.why_input_side} />
      <Passage p={about.where_the_rubric_comes_from} />

      <hr className="rule" />

      <section>
        <h3>Threats to what this can claim</h3>
        <div className="about-threats">
          {about.threats.map((t) => (
            <article key={t.heading}>
              <h4>{t.heading}</h4>
              <p className="small quiet">{t.text}</p>
              <p className="label">Chapter {t.chapter}</p>
            </article>
          ))}
        </div>
      </section>

      <section>
        <h3>Deliberately not implemented</h3>
        <dl className="about-non">
          {Object.entries(framework.non_transfers).map(([k, v]) => (
            <div key={k}>
              <dt className="artifact">{k.replace(/_/g, " ")}</dt>
              <dd className="small quiet">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h3>What is left</h3>
        <ol className="about-remaining">
          {about.remaining.map((r, i) => (
            <li key={i} className="measure small">
              {r}
            </li>
          ))}
        </ol>
      </section>

      {health && (
        <section className="about-runtime">
          <h3 className="label">This instance</h3>
          <dl>
            <div>
              <dt className="label">Engine</dt>
              <dd className="artifact small">{health.engine}</dd>
            </div>
            <div>
              <dt className="label">Comparator</dt>
              <dd className="artifact small">
                {health.comparator ?? "none — single scorer"}
              </dd>
            </div>
            <div>
              <dt className="label">Cross-model bar</dt>
              <dd className="small">
                {health.cross_model
                  ? "running, two organisations"
                  : "not running"}
              </dd>
            </div>
            <div>
              <dt className="label">Students</dt>
              <dd className="small">{health.no_students}</dd>
            </div>
          </dl>
        </section>
      )}
    </div>
  );
}

function Passage({ p }: { p: AboutPayload["scope"] }) {
  return (
    <section>
      <h3>{p.heading}</h3>
      <p className="measure">{p.text}</p>
      <p className="label">Chapter {p.chapter}</p>
    </section>
  );
}
