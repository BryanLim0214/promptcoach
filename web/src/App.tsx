import { Tabs } from "radix-ui";
import { useEffect, useState } from "react";
import { api } from "./api";
import { Coach } from "./views/Coach";
import { AboutView } from "./views/About";
import { InstrumentView } from "./views/Instrument";
import { SessionView } from "./views/Session";
import { TelemetryView } from "./views/Telemetry";
import { TraceView } from "./views/Trace";
import type {
  AboutPayload,
  CycleResult,
  Framework,
  Health,
  PolicyPayload,
  SessionState,
  Task,
} from "./types";
import "./app.css";

/**
 * Two applications behind one build.
 *
 * `/` is the student's tool. It shows a task, an answer, and one question, and
 * it never uses the words layer, dimension, grade or chapter.
 *
 * `/inspect` is the researcher's view - the layer trace, the specification, the
 * evidence grades, the twenty-four gaps. Nothing in the student app links to it,
 * because a twelve year old has no use for a citation and every reason to be
 * distracted by one. It exists so a committee can confirm that the thing on the
 * student's screen really is the specified framework rather than something that
 * merely resembles it.
 */
export default function App() {
  const inspecting = window.location.pathname.startsWith("/inspect");
  return inspecting ? <Inspector /> : <StudentApp />;
}

function StudentApp() {
  return <Coach />;
}

function Inspector() {
  const [framework, setFramework] = useState<Framework | null>(null);
  const [policy, setPolicy] = useState<PolicyPayload | null>(null);
  const [about, setAbout] = useState<AboutPayload | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [state, setState] = useState<SessionState | null>(null);
  const [result, setResult] = useState<CycleResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.framework(),
      api.policy(),
      api.about(),
      api.tasks(),
      api.health(),
    ])
      .then(([f, p, a, t, h]) => {
        setFramework(f);
        setPolicy(p);
        setAbout(a);
        setTasks(t);
        setHealth(h);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <Down error={error} />;
  if (!framework || !policy || !about) return <Loading />;

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="masthead">
        <div>
          <h1>
            PromptCoach <span className="faint">— researcher view</span>
          </h1>
          <p className="small quiet">
            The same running system, opened up.{" "}
            {health?.offline
              ? "Offline on the deterministic engine."
              : `Running on ${health?.engine}.`}{" "}
            <a href="/">Back to the app</a>
          </p>
        </div>
        <p className="label masthead-note">no student has used this</p>
      </header>

      <Tabs.Root defaultValue="session">
        <Tabs.List className="tabs" aria-label="Views">
          <Tabs.Trigger className="tab" value="session">
            Run a cycle
          </Tabs.Trigger>
          <Tabs.Trigger className="tab" value="telemetry">
            Telemetry
          </Tabs.Trigger>
          <Tabs.Trigger className="tab" value="trace">
            Trace
          </Tabs.Trigger>
          <Tabs.Trigger className="tab" value="instrument">
            Specification
          </Tabs.Trigger>
          <Tabs.Trigger className="tab" value="about">
            Limits
          </Tabs.Trigger>
        </Tabs.List>

        <main id="main">
          <Tabs.Content value="session">
            <SessionView
              framework={framework}
              tasks={tasks}
              state={state}
              setState={setState}
              onResult={setResult}
            />
          </Tabs.Content>
          <Tabs.Content value="telemetry">
            <TelemetryView result={result} />
          </Tabs.Content>
          <Tabs.Content value="trace">
            <TraceView result={result} />
          </Tabs.Content>
          <Tabs.Content value="instrument">
            <InstrumentView framework={framework} policy={policy} />
          </Tabs.Content>
          <Tabs.Content value="about">
            <AboutView about={about} framework={framework} health={health} />
          </Tabs.Content>
        </main>
      </Tabs.Root>
    </>
  );
}

function Loading() {
  return (
    <main className="page">
      <p className="quiet">Loading…</p>
    </main>
  );
}

function Down({ error }: { error: string }) {
  return (
    <main className="page">
      <h1>Could not reach the server</h1>
      <p className="quiet measure">{error}</p>
      <p className="artifact small">
        python -m uvicorn promptcoach_ref.api:app --port 8823
      </p>
    </main>
  );
}
