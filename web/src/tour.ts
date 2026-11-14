/**
 * The guided walkthrough script.
 *
 * It drives the real interface: it types into the same fields a student types
 * into and calls the same endpoints. Nothing is mocked, so what a viewer watches
 * is the system working, not a recording of it having once worked. If the
 * backend is wrong the tour breaks, which is the correct behaviour for a
 * demonstration.
 *
 * The script is Chapter 11's worked example, because that is the one interaction
 * the thesis specifies end to end and the one a committee can check line by
 * line against the manuscript.
 *
 * Two audiences watch the same screen, so the rail carries two registers. The
 * `caption` is what is happening, in plain words. The `mechanism` is which layer
 * did it and which line of the thesis says it must, and the readout beside it is
 * the live value this run actually produced - not an illustration of one. An
 * earlier version had only the caption, and it read as broad narration over an
 * interface: true, and unfalsifiable, which is the wrong tone for this artifact.
 */

export type StepKind =
  | "pick"
  | "type-intent"
  | "type-prompt"
  | "predict"
  | "submit"
  | "read"
  | "coach"
  | "type-revision"
  | "type-reason"
  | "compare"
  | "done";

export interface TourStep {
  kind: StepKind;
  /** Three or four words. Names the moment, not the mechanism. */
  title: string;
  /** Shown in the guide rail. Written for someone watching over a shoulder. */
  caption: string;
  /** Which layer is doing the work, for the reader rather than the student. */
  layer?: { n: number; name: string };
  /** What the thesis requires of it. Kept short enough to read at a glance. */
  mechanism?: string;
  /** The manuscript line the mechanism comes from. */
  cite?: string;
  /** What the step is about. Scrolled clear of the rail when the step opens. */
  focus?: string;
  /** Text to type, for the typing steps. */
  text?: string;
  /** The rating to pick, for the predict step (1 to 4). */
  rating?: number;
  /** Task to select, for the pick step. */
  taskId?: string;
  /** Advance on its own once the step's work is finished. */
  auto?: boolean;
}

export const WORKED_INTENT =
  "Okay so I have to explain the sky thing to my cousin, she's like seven so " +
  "it can't be complicated, maybe just a few sentences.";

export const WORKED_PROMPT = "explain why the sky is blue";

export const WORKED_REVISION =
  "explain why the sky is blue for a seven year old, keep it to a few sentences";

/** Authored for the walkthrough: the thesis's worked example predates the
 * reasoned-revision rule. It says what she changed, which is all the rule asks. */
export const WORKED_REASON =
  "I added who it is for and how long it should be";

/** Her guess before she sees the output. A student who is sure of a six-word
 * prompt is the case the calibration gap exists to show her. */
export const WORKED_PREDICTION = 3;

export const TOUR: TourStep[] = [
  {
    kind: "pick",
    taskId: "b3-babysitting",
    title: "A reason to want it",
    caption:
      "Every task carries one decision the system is never allowed to make " +
      "for her — this one's is named alongside. There is no right answer to " +
      "look up, which is exactly why it is worth practising.",
    mechanism:
      "Band 3 names no dimensions in the wording. She has to bring them unprompted.",
    cite: "sec:calibrate, tab:progression",
  },
  {
    kind: "type-intent",
    focus: "#intent",
    text: WORKED_INTENT,
    title: "What she means",
    caption:
      "Out loud, the way she would say it to a friend. Count what is already " +
      "in here: who it is for, how old, how simple, how long. She is not " +
      "missing any of it.",
    layer: { n: 1, name: "Elicit" },
    mechanism:
      "Layer 1 captures intent before the prompt exists and scores nothing. " +
      "The audio is discarded the moment it becomes text.",
    cite: "sec:method",
  },
  {
    kind: "type-prompt",
    focus: "#prompt",
    text: WORKED_PROMPT,
    title: "What she types",
    caption:
      "Six words. Everything she just said about the cousin, the age, the " +
      "length is gone — and she would tell you she knows all of it.",
    layer: { n: 1, name: "Elicit" },
    mechanism:
      "Both records are kept side by side and neither is corrected. The gap " +
      "between them is the object the rest of the system reads.",
    cite: "sec:framework",
  },
  {
    kind: "predict",
    focus: ".predict",
    rating: WORKED_PREDICTION,
    title: "Her guess first",
    caption:
      "Before she sees anything, she says how good she thinks the prompt is, " +
      "1 to 4. Nothing is shown yet. Later, the guess sits beside the score, " +
      "and only she sees the gap between them.",
    layer: { n: 1, name: "Elicit" },
    mechanism:
      "The predicted rating is recorded with the attempt. Calibrate subtracts " +
      "the measured score; whether she is shown the gap is a switch (F8). The " +
      "teacher view never carries it.",
    cite: "sec:calibrate",
  },
  {
    kind: "submit",
    auto: true,
    title: "Sent as written",
    caption:
      "The prompt goes to the model exactly as she typed it. Quietly " +
      "improving it first would hand her a good answer and delete the reason " +
      "to write a better prompt.",
    mechanism:
      "The answer path runs with no system prompt beyond a safety frame.",
    cite: "responder.py",
  },
  {
    kind: "read",
    focus: ".answer",
    title: "The answer it earned",
    caption:
      "Not wrong — just written for nobody in particular. A seven-year-old " +
      "will not follow it. While she reads, the prompt itself is being scored.",
    layer: { n: 2, name: "Measure" },
    mechanism:
      "Six dimensions, 1–4, scored by a three-judge ensemble at three " +
      "temperatures. A dimension nobody could score stays blank; it never " +
      "becomes a 1.",
    cite: "sec:build1",
  },
  {
    kind: "coach",
    focus: ".nudge",
    title: "One question",
    caption:
      "It replays her own sentence and stops. It does not rewrite the " +
      "prompt, list her six scores, or tell her what to add — and it will not " +
      "invent a detail she never said.",
    layer: { n: 4, name: "Respond" },
    mechanism:
      "Layer 3 ranks the failures, Layer 4 writes to the top one at the " +
      "lowest rung. Whether the reply crossed the authorship line is decided " +
      "by a check in code, not by asking the model nicely.",
    cite: "sec:respond",
  },
  {
    kind: "type-revision",
    focus: "#prompt",
    text: WORKED_REVISION,
    title: "Her words, her hands",
    caption:
      "She puts back what she had already said out loud. Nothing on screen " +
      "ever gave her “seven year old” or “a few sentences” — those were hers " +
      "before the system saw them.",
    mechanism:
      "Guidance may narrow the search space and may not close it. A scaffold " +
      "that supplies the missing element has written the prompt.",
    cite: "sec:respond",
  },
  {
    kind: "type-reason",
    focus: "#reason",
    text: WORKED_REASON,
    title: "Why she changed it",
    caption:
      "A revision of the same task is not scored until she says, in her own " +
      "words, why she changed it. One sentence is enough.",
    layer: { n: 1, name: "Elicit" },
    mechanism:
      "Same-task revision with a stated reason, before a new task. " +
      "Argued, never tested - which is why it can be switched off for F7.",
    cite: "sec:elicit",
  },
  {
    kind: "submit",
    auto: true,
    title: "Same model, new prompt",
    caption:
      "Nothing changed except the twenty words she added. Same model, same " +
      "task, same settings.",
    mechanism: "The comparison is the evidence, so only one variable moves.",
    cite: "sec:design, tab:worked",
  },
  {
    kind: "compare",
    focus: ".answer",
    title: "The gap, closed",
    caption:
      "Both answers, side by side, with the prompts that produced them. She " +
      "is not told her prompt improved — she is shown the two outputs and " +
      "left to decide.",
    layer: { n: 5, name: "Calibrate" },
    mechanism:
      "Layer 5 checks the one dimension the diagnosis pairs with, and the " +
      "unpaired ones too, so the pairing can be shown wrong rather than " +
      "assumed right.",
    cite: "sec:calibrate, tab:improvement",
  },
  {
    kind: "done",
    title: "Five layers she never saw",
    caption:
      "Capture, measurement, diagnosis, response, difficulty. Across those " +
      "two attempts all five ran, and not one of them appeared on her " +
      "screen. That is the design working, not the design hiding.",
    mechanism:
      "Four run on any single attempt, not five: Respond answers a first try, " +
      "Calibrate closes a revision. The layers are a graph, not a pipeline, " +
      "so the same session leaves different traces. Inspect has all of them.",
    cite: "sec:framework — “The dependency is not a single chain”",
  },
];
