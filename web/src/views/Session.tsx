import { useCallback, useMemo, useState } from "react";
import { api } from "../api";
import { BandIndicator } from "../components/BandIndicator";
import { Cite } from "../components/Cite";
import { DimensionMeter } from "../components/DimensionMeter";
import { Gap } from "../components/Gap";
import { GradeMark } from "../components/GradeMark";
import { Ladder } from "../components/Ladder";
import { Sentinel } from "../components/Sentinel";
import { useSpeech } from "../useSpeech";
import type { CycleResult, Framework, SessionState, Task } from "../types";
import "./session.css";

export function SessionView({
  framework,
  tasks,
  state,
  setState,
  onResult,
}: {
  framework: Framework;
  tasks: Task[];
  state: SessionState | null;
  setState: (s: SessionState) => void;
  /** Lifted so the Trace view can open the same cycle this one just ran. */
  onResult: (r: CycleResult | null) => void;
}) {
  const [intent, setIntent] = useState("");
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState<CycleResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [modality, setModality] = useState<"typed" | "speech">("typed");
  const [predicted, setPredicted] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [parentId, setParentId] = useState<string | null>(null);
  // "I need more help": sent with the next attempt as asked_for_help, which
  // moves help up one rung (policy escalation; it is the only trigger for the
  // three diagnoses paired with an evaluative dimension, besides unchanged text).
  const [askHelp, setAskHelp] = useState(false);
  const [startedAt] = useState(() => Date.now());

  const onTranscript = useCallback((text: string) => {
    setIntent(text);
    setModality("speech");
  }, []);
  const speech = useSpeech(onTranscript);

  const task = state?.task;
  // A revision that was sent back for its reason is still a revision.
  const awaitingRevision = parentId !== null;

  const dropped = useMemo(() => {
    const drift = result?.diagnose?.assignments?.find(
      (a) => a.category === "intent_drift",
    );
    if (!drift) return [];
    return framework.dimensions
      .filter((d) => drift.trigger.includes(d.name))
      .map((d) => d.id);
  }, [result, framework.dimensions]);

  async function start(taskId: string) {
    const s = await api.createSession({
      platform_use: true,
      research_participation: false,
      audio_retention: false,
      task_id: taskId,
    });
    setState(s);
    setResult(null);
    onResult(null);
    setIntent("");
    setPrompt("");
    setPredicted(null);
    setReason("");
    setParentId(null);
    setAskHelp(false);
  }

  async function submit() {
    if (!state) return;
    setBusy(true);
    try {
      const r = await api.submit(state.session_id, {
        stated_intent: intent,
        prompt_text: prompt,
        intent_modality: modality,
        transcript_reviewed: true,
        student_ms: Date.now() - startedAt,
        parent_attempt_id: awaitingRevision ? parentId : null,
        predicted_rating: predicted,
        revision_reason: awaitingRevision ? reason : null,
        asked_for_help: askHelp,
      });
      setResult(r);
      onResult(r);
      setState(r.state);
      if (r.stopped_at === "respond") {
        // Help was given, on a first attempt or on a revision whose cycle is
        // still open: the next send revises this attempt.
        setParentId(r.elicit.record?.attempt_id ?? null);
        setReason("");
        setAskHelp(false);
      } else if (r.stopped_at !== "elicit") {
        setParentId(null);
        setReason("");
        setAskHelp(false);
      }
    } finally {
      setBusy(false);
    }
  }

  if (!state) {
    return (
      <div className="page">
        <TaskPicker tasks={tasks} onPick={start} framework={framework} />
      </div>
    );
  }

  return (
    <div className="page session">
      <header className="session-head">
        <div>
          <p className="label">
            Band {state.band} · {task?.id}
            {task?.from_thesis && " · the thesis's own worked example"}
          </p>
          <p className="session-scenario measure">{task?.scenario}</p>
        </div>
        <button className="btn btn-quiet" onClick={() => start(state.task_id)}>
          Restart
        </button>
      </header>

      <section className="session-inputs" aria-label="Your attempt">
        <div>
          <label className="label" htmlFor="intent">
            What are you trying to do?
          </label>
          <textarea
            id="intent"
            className="field speech"
            rows={3}
            value={intent}
            onChange={(e) => {
              setIntent(e.target.value);
              if (!speech.listening) setModality("typed");
            }}
            placeholder="Say it out loud, or type it here."
          />
          <div className="session-mic">
            {speech.supported ? (
              <button
                className="btn btn-quiet"
                onClick={speech.listening ? speech.stop : speech.start}
                aria-pressed={speech.listening}
              >
                {speech.listening ? "Stop recording" : "Record instead"}
              </button>
            ) : (
              <span className="small faint">
                This browser cannot capture speech — typing works just as well.
              </span>
            )}
            <span className="small faint">
              {speech.error ??
                "Nothing is recorded. The words are the artifact; there is no audio."}
            </span>
          </div>
        </div>

        <div>
          <label className="label" htmlFor="prompt">
            Your prompt
          </label>
          <textarea
            id="prompt"
            className="field artifact"
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="What you would actually type into the AI."
          />
          {awaitingRevision && (
            <>
              <label className="label" htmlFor="reason">
                Why you changed it
              </label>
              <input
                id="reason"
                className="field"
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Required before a revision is scored."
              />
            </>
          )}
          <label className="label" htmlFor="predicted">
            Predicted rating (1–4, optional)
          </label>
          <select
            id="predicted"
            className="field"
            value={predicted ?? ""}
            onChange={(e) =>
              setPredicted(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">skip</option>
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <div className="session-actions">
            <button className="btn" onClick={submit} disabled={busy || !prompt.trim()}>
              {busy ? "Working…" : awaitingRevision ? "Send revision" : "Send"}
            </button>
            {awaitingRevision && (
              <label className="small session-help">
                <input
                  type="checkbox"
                  checked={askHelp}
                  onChange={(e) => setAskHelp(e.target.checked)}
                />{" "}
                I need more help (sent with this revision as asked_for_help)
              </label>
            )}
            {task && (
              <p className="small faint measure">
                <span className="label" style={{ display: "inline" }}>
                  yours to decide
                </span>{" "}
                {task.protected_judgment}
              </p>
            )}
          </div>
        </div>
      </section>

      {result?.clarification && (
        <p className="session-clarify measure">{result.clarification}</p>
      )}

      {result?.elicit.record && (
        <Gap
          intent={result.elicit.record.stated_intent}
          artifact={result.elicit.record.prompt_text}
          modality={result.elicit.record.intent_modality}
          dropped={dropped}
          dimensions={framework.dimensions}
        />
      )}

      {result?.measure && (
        <section className="session-block" aria-labelledby="h-measure">
          <Head
            id="h-measure"
            n="2"
            title="Measure"
            grade="direct"
            cite="sec:measure"
            note="six dimension scores with per dimension confidence"
          />
          <DimensionMeter
            dimensions={framework.dimensions}
            scores={result.measure.scores}
            agreement={result.measure.agreement}
            min={framework.scale.min}
            max={framework.scale.max}
          />
          <p className="small faint measure session-note">
            {result.measure.agreement?.different_organisations
              ? `Two scorers, different organisations. Mean gap ${result.measure.agreement.mean_gap}. ${framework.reliability.shared_prior}`
              : framework.reliability.third_bar}
          </p>
        </section>
      )}

      {result?.diagnose && (
        <section className="session-block" aria-labelledby="h-diagnose">
          <Head
            id="h-diagnose"
            n="3"
            title="Diagnose"
            grade="argued"
            cite="sec:diagnose"
            note="a ranked list of failure categories with confidence"
          />
          {result.diagnose.assignments.length === 0 ? (
            <p className="quiet">
              {result.diagnose.insufficient_evidence
                ? "Something was seen but not clearly enough to name. That is not the same as nothing being wrong."
                : "No category cleared its trigger."}
            </p>
          ) : (
            <ol className="ranked">
              {result.diagnose.assignments.map((a) => {
                const cat = framework.taxonomy.find((c) => c.id === a.category);
                const isTarget = a.category === result.diagnose?.target;
                return (
                  <li key={a.category} className={isTarget ? "is-target" : ""}>
                    <div className="ranked-head">
                      <span className="ranked-name">{cat?.name ?? a.category}</span>
                      <span className="small faint">{a.confidence.toFixed(2)}</span>
                      {isTarget && <span className="label ranked-flag">responding to this</span>}
                    </div>
                    <p className="small quiet">{a.trigger}</p>
                  </li>
                );
              })}
            </ol>
          )}
          <p className="small faint measure session-note">
            {framework.taxonomy_notes.overlap}
          </p>
        </section>
      )}

      {result?.respond && (
        <section className="session-block" aria-labelledby="h-respond">
          <Head
            id="h-respond"
            n="4"
            title="Respond"
            grade="transferred"
            cite="sec:respond"
            note="the level issued, and whether the next attempt improved"
          />
          <blockquote className="response speech">{result.respond.text}</blockquote>
          <p className="small quiet">{result.respond.expected_action}</p>
          {result.respond.used_template_floor && (
            <p className="small faint">
              Served from the template floor — generation failed or overreached.
            </p>
          )}
          <div className="session-ladder">
            <Ladder
              levels={framework.ladder}
              issued={state.levels_issued}
              current={result.respond.level}
            />
          </div>
          <p className="small faint measure session-note">
            {result.respond.selection_reason}
          </p>
        </section>
      )}

      {result?.help_cycle && (
        <p className="small quiet measure session-note">
          Help cycle: {result.help_cycle}
        </p>
      )}

      {result?.calibrate && (
        <section className="session-block" aria-labelledby="h-calibrate">
          <Head
            id="h-calibrate"
            n="5"
            title="Calibrate"
            grade="argued"
            cite="no downstream requirement is stated for Layer 5"
            note="this layer's output shape is ours, not the thesis's"
          />
          <p className="quiet measure">{result.calibrate.reason}</p>
          <div className="session-ladder">
            <BandIndicator
              bands={framework.bands}
              current={result.calibrate.band}
              join={framework.band_notes.axis_join}
            />
          </div>
          <div className="session-deltas">
            <p className="label">
              Paired dimension moved {fmt(result.calibrate.paired_delta)} ·{" "}
              {result.calibrate.pairing_strictness}
            </p>
            <p className="small faint measure">
              {framework.taxonomy_notes.strictness}
            </p>
          </div>
          <h3 className="label session-sub">Over-reliance signals — yours only</h3>
          {Object.keys(result.calibrate.sentinel).length > 0 ? (
            <Sentinel
              signals={framework.sentinel.signals}
              values={result.calibrate.sentinel}
            />
          ) : (
            <p className="quiet">No signals were computed for this attempt.</p>
          )}
          <p className="small faint measure session-note">
            Detector: {result.calibrate.sentinel_source}
          </p>
          <p className="small faint measure session-note">
            {framework.sentinel.routing_rule} {framework.sentinel.one_signal}
          </p>
        </section>
      )}
    </div>
  );
}

function Head({
  id,
  n,
  title,
  grade,
  cite,
  note,
}: {
  id: string;
  n: string;
  title: string;
  grade: "direct" | "transferred" | "argued";
  cite: string;
  note: string;
}) {
  return (
    <div className="session-blockhead">
      <h2 id={id}>
        <span className="faint">{n}</span> {title}
      </h2>
      <div className="session-blockmeta">
        <GradeMark grade={grade} />
        <Cite label={title} source="thesis" cite={cite} grade={grade}>
          <p>{note}</p>
        </Cite>
      </div>
    </div>
  );
}

function TaskPicker({
  tasks,
  onPick,
  framework,
}: {
  tasks: Task[];
  onPick: (id: string) => void;
  framework: Framework;
}) {
  return (
    <div className="picker">
      <h2>Pick a task</h2>
      <p className="quiet measure">
        Ten tasks across the five bands. Nine are authored for this
        implementation; one is the thesis's own worked example. The bands are an
        untested proposition — {framework.band_notes.not_commensurable}
      </p>
      <ol className="picker-list">
        {tasks.map((t) => (
          <li key={t.id}>
            <button className="picker-task" onClick={() => onPick(t.id)}>
              <span className="label">
                Band {t.band}
                {t.from_thesis && " · from the thesis"}
              </span>
              <span className="picker-scenario">{t.scenario}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

function fmt(v: number | null) {
  if (v === null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}
