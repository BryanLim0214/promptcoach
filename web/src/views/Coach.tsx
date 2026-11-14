import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { GuideRail, type Readout } from "../components/GuideRail";
import { TOUR, type TourStep } from "../tour";
import { useSpeech } from "../useSpeech";
import { useTypewriter } from "../useTypewriter";
import type { CycleResult, Framework, SessionState, Task } from "../types";
import "./coach.css";

/**
 * The application.
 *
 * A student picks something she has a reason to want, says what she is after,
 * writes a prompt, and **gets the answer her prompt earned**. Then one question
 * about the gap between the two, a revision, and the new answer beside the old
 * one so she can see what changed.
 *
 * Nothing on this screen names a layer, a dimension score, an evidence grade or
 * a chapter. All five layers ran to produce what she sees; the framework is the
 * engine, not the subject. The trace and the specification live at /inspect,
 * which nothing here links to.
 *
 * The one design rule that governs the screen: the answer is the largest thing
 * on it. An interface that put the coaching first would be telling her what she
 * did wrong before she had any reason to care.
 *
 * The attempt cycle the framework specifies is Plan, Write, Predict, See,
 * Revise. So before she sends, she may say how good she thinks the prompt is
 * (1 to 4, optional); after, she sees what it produced before any coaching; and
 * a revision of the same task asks her for one sentence on why she changed it.
 * The gap between her guess and the score is hers - shown to her, never to a
 * teacher - and the answer names the model that wrote it, which is not the one
 * that scored her prompt.
 *
 * The guided walkthrough drives this same component - it types into these
 * fields and calls these functions. There is no separate demo path, so a broken
 * backend breaks the demo, which is the point.
 */

type Phase = "pick" | "write" | "answered" | "revised";

export function Coach() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [state, setState] = useState<SessionState | null>(null);
  const [phase, setPhase] = useState<Phase>("pick");
  const [intent, setIntent] = useState("");
  const [prompt, setPrompt] = useState("");
  const [modality, setModality] = useState<"typed" | "speech">("typed");
  const [predicted, setPredicted] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  // The attempt a revision revises. Kept apart from `result` so a revision
  // that was sent back for a reason still knows its parent.
  const [parentId, setParentId] = useState<string | null>(null);
  // A request from Layer 1 (a reason, a rating off the scale). Shown without
  // clearing the answer she is still reading.
  const [clarify, setClarify] = useState<string | null>(null);
  // "I need more help". Sent with her next try as asked_for_help; the help on
  // that try moves up one rung.
  const [askHelp, setAskHelp] = useState(false);
  const [result, setResult] = useState<CycleResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- walkthrough --------------------------------------------------------
  const [tourStep, setTourStep] = useState<number | null>(null);
  const touring = tourStep !== null;
  const step = touring ? TOUR[tourStep] : null;
  const [filling, setFilling] = useState<"intent" | "prompt" | "reason" | null>(
    null,
  );
  // Fetched only while touring, and only so the rail can print a dimension or
  // category by the name the thesis gives it instead of a name invented here.
  const [fw, setFw] = useState<Framework | null>(null);

  const intentTyper = useTypewriter(setIntent);
  const promptTyper = useTypewriter(setPrompt);
  const reasonTyper = useTypewriter(setReason);
  const typing = intentTyper.typing || promptTyper.typing || reasonTyper.typing;

  useEffect(() => {
    api.tasks().then(setTasks).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    document.body.classList.toggle("touring", touring);
    return () => document.body.classList.remove("touring");
  }, [touring]);

  useEffect(() => {
    if (touring && !fw) api.framework().then(setFw).catch(() => undefined);
  }, [touring, fw]);

  // Bring the thing the current step is about into the band above the rail.
  //
  // `scrollIntoView` is not enough here: it knows nothing about a fixed
  // element, so on the coaching step it centred the answer and left the
  // question itself - the entire subject of the step - hidden behind the rail.
  useEffect(() => {
    if (!touring) return;
    const selector = TOUR[tourStep!]?.focus;
    if (!selector) return;
    const id = window.setTimeout(() => {
      const el = document.querySelector(selector);
      if (!el) return;
      const railH =
        (document.querySelector(".guide") as HTMLElement | null)?.offsetHeight ??
        0;
      const band = window.innerHeight - railH;
      const box = el.getBoundingClientRect();
      const inset = Math.max(24, (band - box.height) / 2);
      window.scrollTo({
        top: Math.max(0, window.scrollY + box.top - inset),
        behavior: "smooth",
      });
    }, 90);
    return () => window.clearTimeout(id);
  }, [touring, tourStep]);

  const onTranscript = useCallback((text: string) => {
    setIntent(text);
    setModality("speech");
  }, []);
  const speech = useSpeech(onTranscript);

  const task = state?.task;

  const begin = useCallback(
    async (taskId: string) => {
      setError(null);
      try {
        const s = await api.createSession({
          platform_use: true,
          research_participation: false,
          audio_retention: false,
          task_id: taskId,
        });
        setState(s);
        setPhase("write");
        setIntent("");
        setPrompt("");
        setPredicted(null);
        setReason("");
        setParentId(null);
        setClarify(null);
        setAskHelp(false);
        setResult(null);
        return s;
      } catch (e) {
        setError(String(e));
        return null;
      }
    },
    [],
  );

  const send = useCallback(
    async (isRevision: boolean, session?: SessionState | null) => {
      const active = session ?? state;
      if (!active) return null;
      setBusy(true);
      setError(null);
      try {
        const r = await api.submit(active.session_id, {
          stated_intent: intent,
          prompt_text: prompt,
          intent_modality: modality,
          transcript_reviewed: true,
          student_ms: 0,
          parent_attempt_id: isRevision ? parentId : null,
          predicted_rating: predicted,
          revision_reason: isRevision ? reason : null,
          asked_for_help: askHelp,
        });
        setState(r.state);
        if (r.stopped_at === "elicit") {
          // Nothing was scored. Keep what she is reading and ask.
          setClarify(r.clarification);
          return r;
        }
        setClarify(null);
        setResult(r);
        setAskHelp(false);
        // A revision that got more help keeps the same task open: the next try
        // revises this one, and help keeps climbing while the same problem
        // is ranked first. A revision with no new help closes the loop.
        const helpedAgain = isRevision && r.stopped_at === "respond";
        if (!isRevision || helpedAgain) {
          setParentId(r.elicit.record?.attempt_id ?? null);
        }
        if (helpedAgain) setReason("");
        setPhase(isRevision && !helpedAgain ? "revised" : "answered");
        return r;
      } catch (e) {
        setError(String(e));
        return null;
      } finally {
        setBusy(false);
      }
    },
    [state, intent, prompt, modality, predicted, reason, parentId, askHelp],
  );

  // --- one step of the walkthrough ---------------------------------------

  async function advance() {
    if (tourStep === null) return;
    const current = TOUR[tourStep];
    const go = () => setTourStep((n) => (n === null ? null : n + 1));

    switch (current.kind) {
      case "pick": {
        const s = await begin(current.taskId!);
        if (s) go();
        break;
      }
      case "type-intent":
        setFilling("intent");
        setModality("typed");
        intentTyper.type(current.text!, () => {
          setFilling(null);
          go();
        });
        break;
      case "type-prompt":
      case "type-revision":
        setFilling("prompt");
        promptTyper.type(current.text!, () => {
          setFilling(null);
          go();
        });
        break;
      case "predict":
        setPredicted(current.rating ?? null);
        go();
        break;
      case "type-reason":
        setFilling("reason");
        reasonTyper.type(current.text!, () => {
          setFilling(null);
          go();
        });
        break;
      case "submit": {
        const r = await send(phase === "answered");
        if (r) go();
        break;
      }
      default:
        go();
    }
  }

  function exitTour() {
    intentTyper.skip();
    promptTyper.skip();
    reasonTyper.skip();
    setFilling(null);
    setTourStep(null);
  }

  function startTour() {
    setResult(null);
    setState(null);
    setIntent("");
    setPrompt("");
    setPredicted(null);
    setReason("");
    setParentId(null);
    setClarify(null);
    setPhase("pick");
    setTourStep(0);
  }

  const answer = result?.answer;
  const previous = result?.previous_answer;
  const coaching = result?.respond;

  // --- what the rail shows beside the narration ---------------------------
  //
  // Every value below is read off the run that just happened. None of it is
  // authored for the walkthrough, which is the difference between a narrated
  // demonstration and a claim a viewer can check on the spot: change the
  // prompt and these change with it.

  const dimName = (id: string) =>
    fw?.dimensions.find((d) => d.id === id)?.name ?? id;
  const catName = (id: string) =>
    fw?.taxonomy.find((c) => c.id === id)?.name ?? id;
  const words = (text: string) =>
    text.trim() ? text.trim().split(/\s+/).length : 0;

  function readoutFor(s: TourStep): Readout[] {
    switch (s.kind) {
      case "pick": {
        const t = tasks.find((x) => x.id === s.taskId);
        if (!t) return [];
        return [
          { label: "Band", value: `${t.band} of 5` },
          {
            label: "Named in the task",
            value: t.named_dimensions.length
              ? t.named_dimensions.map(dimName).join(", ")
              : "nothing — she has to bring it unprompted",
          },
          { label: "Never decided for her", value: t.protected_judgment, key: true },
        ];
      }

      case "type-intent":
        return [
          {
            label: "Captured as",
            value: modality === "speech" ? "speech, transcribed" : "typed",
          },
          { label: "Words said", value: `${words(intent)}`, key: true },
          { label: "Scored so far", value: "nothing — Layer 1 judges neither" },
        ];

      case "type-prompt":
        return [
          { label: "Words said", value: `${words(intent)}` },
          { label: "Words typed", value: `${words(prompt)}`, key: true },
          { label: "Kept", value: "both, unedited, side by side" },
        ];

      case "predict":
        return [
          {
            label: "Her guess",
            value: predicted ? `${predicted} of 4` : "skipped",
            key: true,
          },
          { label: "Shown to", value: "her only — never a teacher view" },
        ];

      case "submit":
        return [
          { label: "Sent verbatim", value: prompt || "—", key: true },
          { label: "Improved first", value: "no" },
          ...(phase === "answered"
            ? [{ label: "Reason given", value: reason ? "yes" : "no" }]
            : []),
        ];

      case "type-reason":
        return [
          { label: "Words in the reason", value: `${words(reason)}`, key: true },
          { label: "Scored without one", value: "no — Layer 1 asks first" },
        ];

      case "read": {
        const m = result?.measure;
        const scored = m
          ? Object.values(m.scores).filter((d) => d.value !== null)
          : [];
        const weakest = [...scored]
          .sort((a, b) => (a.value ?? 9) - (b.value ?? 9))
          .slice(0, 2);
        const rows: Readout[] = [
          {
            label: "Scored",
            value: scored.length
              ? `${scored.length} of 6 dimensions, 1–4`
              : "—",
          },
          {
            label: "Weakest",
            value:
              weakest.map((d) => `${dimName(d.dimension_id)} ${d.value}`).join(
                " · ",
              ) || "—",
            key: true,
          },
        ];
        if (m) {
          rows.push({
            label: "Judged by / answered by",
            value: `${m.judge_model} / ${m.generator_model}`,
          });
        }
        if (m?.agreement) {
          rows.push({
            label: "Two scorers apart by",
            value: `${m.agreement.mean_gap.toFixed(2)} points`,
          });
        }
        if (answer) {
          rows.push({
            label: "Answer took",
            value: `${(answer.latency_ms / 1000).toFixed(1)} s`,
          });
        }
        return rows;
      }

      case "coach": {
        const d = result?.diagnose;
        const r = result?.respond;
        const top = d?.assignments?.[0];
        return [
          {
            label: "Ranked first",
            value: top
              ? `${catName(top.category)} · ${top.confidence.toFixed(2)}`
              : "—",
            key: true,
          },
          {
            label: "Also ranked",
            value:
              d?.assignments
                .slice(1, 3)
                .map((a) => catName(a.category))
                .join(", ") || "nothing else fired",
          },
          {
            label: "Rung issued",
            value: r ? `${r.level} of 4 — never starts higher` : "—",
          },
          {
            label: "Authorship check",
            value: r
              ? r.used_template_floor
                ? "reply rejected; the floor was served"
                : "reply passed"
              : "—",
          },
        ];
      }

      case "type-revision":
        return [
          { label: "Supplied by the system", value: "nothing", key: true },
          { label: "Words typed", value: `${words(prompt)}` },
        ];

      case "compare": {
        const c = result?.calibrate;
        const moved = Object.entries(c?.unpaired_deltas ?? {}).filter(
          ([, v]) => v !== 0,
        );
        return [
          {
            label: "Paired dimension",
            value:
              c?.paired_delta === null || c?.paired_delta === undefined
                ? "not scorable"
                : `${c.paired_delta > 0 ? "+" : ""}${c.paired_delta}`,
            key: true,
          },
          {
            label: "Unpaired moved",
            value: moved.length
              ? moved
                  .map(([k, v]) => `${dimName(k)} ${v > 0 ? "+" : ""}${v}`)
                  .join(" · ")
              : "none",
          },
          {
            label: "Difficulty",
            value: c
              ? c.band_changed
                ? `moved to band ${c.band}`
                : `held at band ${c.band}`
              : "—",
          },
          {
            label: "Guess minus score",
            value:
              result?.calibration.gap === null ||
              result?.calibration.gap === undefined
                ? "not recorded"
                : `${result.calibration.gap > 0 ? "+" : ""}${result.calibration.gap}`,
          },
        ];
      }

      case "done":
        return [
          {
            label: "This attempt ran",
            value: result?.trace.length
              ? result.trace.map((t) => t.layer).join(" → ")
              : "—",
          },
          {
            label: "Evidence behind it",
            value: fw
              ? `${fw.grades.counts.direct} direct · ` +
                `${fw.grades.counts.transferred} transferred · ` +
                `${fw.grades.counts.argued} argued`
              : "5 direct · 10 transferred · 9 argued",
            key: true,
          },
          {
            label: "Students so far",
            value: "none — this is not effectiveness evidence",
          },
        ];

      default:
        return [];
    }
  }

  // --- pick ---------------------------------------------------------------

  if (phase === "pick") {
    return (
      <>
        <div className="coach coach-pick">
          <h1>What do you need?</h1>
          <p className="coach-lede">
            Pick one you'd actually want. You'll ask an AI for it and read
            exactly what your words earned — then get one chance to ask better.
            Nothing here rewrites your prompt for you.
          </p>
          {error && <p className="coach-error">{error}</p>}
          <ul className="missions">
            {tasks.map((t) => (
              <li key={t.id}>
                <button
                  className="mission"
                  onClick={() => begin(t.id)}
                  disabled={touring}
                >
                  <span className="mission-text">{t.scenario}</span>
                </button>
              </li>
            ))}
          </ul>
          {!touring && (
            <p className="coach-tourcta">
              <button className="start-tour" onClick={startTour}>
                Show me how it works
              </button>
            </p>
          )}
        </div>
        {touring && step && (
          <GuideRail
            step={tourStep!}
            total={TOUR.length}
            title={step.title}
            caption={step.caption}
            layer={step.layer}
            mechanism={step.mechanism}
            cite={step.cite}
            readout={readoutFor(step)}
            busy={busy}
            typing={typing}
            canAdvance
            onNext={advance}
            onSkipTyping={() => {
              intentTyper.skip();
              promptTyper.skip();
              reasonTyper.skip();
            }}
            onExit={exitTour}
            finished={step.kind === "done"}
          />
        )}
      </>
    );
  }

  return (
    <>
      <div className="coach">
        <header className="coach-task">
          <p>{task?.scenario}</p>
          {!touring && !state?.revision_pending && (
            <button className="linkish" onClick={() => setPhase("pick")}>
              Something else
            </button>
          )}
        </header>

        {error && <p className="coach-error">{error}</p>}

        <section className="ask" aria-label="Ask">
          <div className="ask-field">
            <label htmlFor="intent">
              First — what are you actually after?
              <span className="hint">
                {" "}
                Say it the way you'd say it to a friend. Nobody is scoring this
                part.
              </span>
            </label>
            <div className="ask-intent">
              <textarea
                id="intent"
                className={filling === "intent" ? "is-filling" : ""}
                rows={2}
                value={intent}
                onChange={(e) => {
                  setIntent(e.target.value);
                  if (!speech.listening) setModality("typed");
                }}
                placeholder="I need to…"
                readOnly={touring}
              />
              {speech.supported && !touring && (
                <button
                  className={`mic${speech.listening ? " is-live" : ""}`}
                  onClick={speech.listening ? speech.stop : speech.start}
                  aria-pressed={speech.listening}
                >
                  {speech.listening ? "Stop" : "Say it"}
                </button>
              )}
            </div>
            {speech.error && <p className="hint">{speech.error}</p>}
          </div>

          <div className="ask-field">
            <label htmlFor="prompt">
              Now write what you'd actually type into the AI.
              <span className="hint"> It gets sent exactly as you write it.</span>
            </label>
            <textarea
              id="prompt"
              className={`mono${filling === "prompt" ? " is-filling" : ""}`}
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask it here…"
              readOnly={touring}
            />
          </div>

          {phase === "answered" && (
            <div className="ask-field">
              <label htmlFor="reason">
                What did you change, and why?
                <span className="hint">
                  {" "}
                  One sentence. Your new version is not checked until you say.
                </span>
              </label>
              <input
                id="reason"
                className={filling === "reason" ? "is-filling" : ""}
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="I changed it because…"
                readOnly={touring}
              />
            </div>
          )}

          <fieldset className="ask-field predict">
            <legend>
              Before you send it — how good do you think this prompt is?
              <span className="hint"> Optional. Only you see how close you were.</span>
            </legend>
            <div className="predict-scale" role="radiogroup">
              {[1, 2, 3, 4].map((n) => (
                <label key={n} className={predicted === n ? "is-on" : ""}>
                  <input
                    type="radio"
                    name="predicted"
                    value={n}
                    checked={predicted === n}
                    onChange={() => setPredicted(n)}
                    disabled={touring}
                  />
                  <span>{n}</span>
                  <span className="hint">
                    {["not much yet", "okay", "good", "strong"][n - 1]}
                  </span>
                </label>
              ))}
              {predicted !== null && !touring && (
                <button className="linkish" onClick={() => setPredicted(null)}>
                  skip
                </button>
              )}
            </div>
          </fieldset>

          {!touring && (
            <div className="ask-go">
              <button
                className="go"
                onClick={() => send(phase === "answered")}
                disabled={busy || !prompt.trim() || !intent.trim()}
              >
                {busy ? "Asking…" : phase === "answered" ? "Ask again" : "Ask"}
              </button>
            </div>
          )}
          {clarify && <p className="coach-clarify">{clarify}</p>}
        </section>

        {answer && (
          <section
            className="answer"
            aria-label="What you got back"
          >
            {previous ? (
              <>
                <h2>Before and after</h2>
                <div className="answer-pair">
                  <article className="answer-col is-old">
                    <p className="answer-tag">You asked</p>
                    <p className="mono answer-prompt">{result?.previous_prompt}</p>
                    <p className="answer-tag">You got</p>
                    <div className="answer-body">{previous.text}</div>
                  </article>
                  <article className="answer-col is-new">
                    <p className="answer-tag">Then you asked</p>
                    <p className="mono answer-prompt">
                      {result?.elicit.record?.prompt_text}
                    </p>
                    <p className="answer-tag">And you got</p>
                    <div className="answer-body">{answer.text}</div>
                  </article>
                </div>
              </>
            ) : (
              <>
                <h2>Here's what you got</h2>
                <div className="answer-body answer-single">{answer.text}</div>
              </>
            )}
            <p className="hint answer-note generator-label">
              {answer.scripted
                ? "Written by a built-in stand-in, not a real model — this copy is running without an API key."
                : `Written by ${answer.source}.`}{" "}
              Your prompt was scored by a different model from the one that
              wrote this answer.
            </p>
            {result?.calibration.visible &&
              result.calibration.predicted_rating !== null &&
              result.calibration.measured_overall !== null && (
                <p className="hint answer-note calibration-note">
                  You guessed {result.calibration.predicted_rating} of 4. It was
                  scored {result.calibration.measured_overall.toFixed(1)}. Only
                  you can see this.
                </p>
              )}
          </section>
        )}

        {coaching && phase === "answered" && (
          <section className="nudge" aria-label="One thing to notice">
            <p className="label nudge-label">One thing to notice</p>
            <p className="nudge-text">{coaching.text}</p>
            <p className="hint nudge-do">{coaching.expected_action}</p>
            {!touring && (
              <p className="nudge-help">
                <button
                  className={`linkish${askHelp ? " is-on" : ""}`}
                  aria-pressed={askHelp}
                  onClick={() => setAskHelp((v) => !v)}
                >
                  I need more help
                </button>
                <span className="hint">
                  {askHelp
                    ? " Your next try will get the next level of help."
                    : " Press this, then send your next try."}
                </span>
              </p>
            )}
          </section>
        )}

        {phase === "revised" && !touring && (
          <section className="nudge is-done">
            <p className="label nudge-label">What just happened</p>
            <p className="nudge-text">
              Same model, same task, same settings. The only thing that changed
              was the handful of words you already knew and hadn't typed — and
              that is the whole idea. What you mean and what you write are two
              different things, and the distance between them was doing most of
              the work.
            </p>
            <div className="loop">
              <button
                className="go"
                onClick={async () => {
                  const next = result?.calibrate?.next_task_id;
                  if (!next || !state) {
                    setPhase("pick");
                    return;
                  }
                  // Move within the same session so the band and the history
                  // carry over. Starting a fresh session would reset the loop
                  // she is in the middle of.
                  try {
                    const s = await api.setTask(state.session_id, next);
                    setState(s);
                  } catch (e) {
                    // The reasoned-revision hold says what to do next.
                    setError(e instanceof ApiError ? e.message : String(e));
                    return;
                  }
                  setIntent("");
                  setPrompt("");
                  setPredicted(null);
                  setReason("");
                  setParentId(null);
                  setClarify(null);
                  setResult(null);
                  setPhase("write");
                }}
              >
                Next one
              </button>
              <button className="linkish" onClick={() => setPhase("pick")}>
                Pick something else
              </button>
            </div>
            {/* The loop's own state, in her words rather than as a band number.
                Chapter 10 requires the adaptation to be legible to her: "when
                the system changes what it asks of her, it tells her why it
                changed". A silent difficulty engine would satisfy ownership and
                fail legibility. */}
            {result?.calibrate && (
              <p className="small quiet loop-why">
                {result.calibrate.band_changed
                  ? "The next one steps up. You have been getting these."
                  : "Holding at this level. One good revision is not enough to tell — it takes a run of them."}
              </p>
            )}
          </section>
        )}
      </div>

      {touring && step && (
        <GuideRail
          step={tourStep!}
          total={TOUR.length}
          title={step.title}
          caption={step.caption}
          layer={step.layer}
          mechanism={step.mechanism}
          cite={step.cite}
          readout={readoutFor(step)}
          busy={busy}
          typing={typing}
          canAdvance
          onNext={advance}
          onSkipTyping={() => {
            intentTyper.skip();
            promptTyper.skip();
            reasonTyper.skip();
          }}
          onExit={exitTour}
          finished={step.kind === "done"}
        />
      )}
    </>
  );
}
