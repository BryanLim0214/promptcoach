# Changelog — 2026-10-24

Brings the reference implementation in line with the redesigned framework
(`UTPB_Thesis_Lim_Final/review/FRAMEWORK_SPEC.md`). The pre-change tree is at
`_snapshot_2026-10-24/promptcoach-reference`. The app still shows only that the
specification is implementable; it has not been used with students.

## Framework (`promptcoach_ref/framework/`)
- `grades.py`: new `NeedBasis` (Students, Builds, Argument), required on every
  component. 24 components: removed *Affective state inference* (kept in
  `REMOVED_COMPONENTS`, `sec:not-adopted`); escalation drops inactivity; added
  visible consequence before coaching, same-task revision with a reason,
  predicted rating beside the score, judge independent of the generator,
  selecting is not composing. Counts pinned at 5/10/9 and 4/18/2. Originals:
  taxonomy, progression, reasoned revision, calibration gap.
- Citations are section labels (`Cite(label, detail)`), validated against the
  chapter map; all file:line references were converted. Fixed: row 15 now cites
  Hattie and Timperley and Shute (not Demszky); row 19 no longer leans on the
  disability-access source for consent; row 23 leads with Panickssery. Wording
  updates for rows 2, 3 (clean-15 label) and 4 (both AUCs, not an improvement).
- `contracts.py`: `predicted_rating`, `revision_reason`, `inserted_spans` (with
  `Span`, `composed_text`); Measure output records `judge_model`,
  `generator_model`, `judge_independent_of_generator`; Calibrate output adds
  `calibration_gap` and `revision_pending`.
- New `revision.py` (the two revision rules) and `classroom.py` (RAW Promptémon
  and published PicPrompt aggregates, `COMPARABLE` flags, `present_change` that
  refuses non-comparable pairs, `WITHDRAWN`).

## Layers, session, engines
- Elicit asks for a reason on an unreasoned revision, checks the rating and
  spans, and uses unique attempt ids. Measure and Diagnose read only composed
  text; Respond treats inserted text as not hers; Calibrate computes the gap and
  the revision hold.
- The answer comes from a separate generator engine (`PROMPTCOACH_GENERATOR`);
  Gemini and OpenRouter take a generator model, and OpenRouter gained `answer()`.
  Offline still works with no key.
- `Session` tracks reasoned revisions, holds a new task (`move_to`, HTTP 409),
  and exposes F7/F8 switches.

## Policy
- New `revision.py` (required switch, minimum 10 characters, exit after 4
  attempts), `calibration.py` (show gap to student by default; never in the
  teacher view), `generator.py` (generator model per provider).
- `affect.py` is now a note that latency inference was tried and removed;
  `escalation.py` no longer has an inactivity trigger. Open gaps: 21.

## Surfaces
- `about.py`, `traceability.py` (13-chapter map, need column, label check
  against `thesis/sections_v2`: passed), `api.py` strings and payloads, README.
- Web: 1–4 confidence control, reason field on revision, generator label,
  hold message; tour gained predict and reason steps; `web/dist` rebuilt.

## Follow-up: judge independence enforced
- Default generators are a third model on every provider: Gemini
  `gemini-3.1-pro-preview` (scorer `gemini-3.1-flash-lite`, comparator
  `gemini-3.8-flash`); OpenRouter `openai/gpt-5.4-mini` (scorer
  `anthropic/claude-opus-5`, comparator `google/gemini-3.8-flash`).
- `generator.on_same_model` is now `refuse`: a live configuration whose
  generator equals the scorer or the comparator raises
  `NonIndependentConfiguration` at start-up with a message naming the collision.
  The bad-key offline fallback no longer swallows it; the offline rule engine is
  unaffected.
- Tests assert judge != generator for every shipped config (2 providers x with
  and without the comparator) and that each collision refuses to start.

## Tests
294 passing, offline. New `test_classroom.py`; extended rejection (calibration
never to teachers, unreasoned revision not scored, inserted text not hers,
judge differs from generator in live config, withdrawn figures absent) and
falsifiability (F7, F8, F9 switches; predicted rating stored).

## Follow-up: second review round (FINDINGS_LOG_R2 D01, D03-D06, D09; M16)
- **D03, escalation on evaluative pairings.** New policy value
  `escalation.evaluative_pairing`. When the diagnosis is paired only with
  Iteration Awareness or Reflection (blind acceptance, undiagnosed retry,
  delegated judgment), the repeated-attempt count no longer escalates; help
  moves up only on an explicit help request or when her composed text equals
  the previous attempt's in the same task cycle (whitespace and case ignored).
  `RespondInput.previous_composed_text` carries the earlier text; the session
  fills it.
- **D04, what a success is.** The rate-and-streak window used to record a
  success only when the paired dimension rose on a revision, so a clean first
  attempt counted as a failure. New policy values `gating.success` (bands 1-2:
  every named planning dimension >= 3; band 3: three of four planning
  dimensions >= 3; bands 4-5: one evaluative dimension >= 3; unscored counts
  as below 3) and `gating.streak_unit` (one outcome per closed cycle, so the
  streak counts attempts and revisions, not distinct tasks). Calibrate
  reports `attempt_succeeded`; the session appends it.
- **Gaps: 21 -> 23.** Added `evaluative_escalation` and `gating_success` to
  `UNSPECIFIED_BY_THESIS`. Policy choices: 30 -> 33.
- **D05.** Confirmed: the hold releases after 4 attempts on a task and each
  exit without a reasoned revision is recorded in `Session.gate_exits`. No
  route releases it; tests now assert no text claims a teacher release.
- **D06.** README and about text say the generator is a *different model*
  from the judge; README states that the Gemini defaults are all Google and
  only the OpenRouter defaults span three vendors.
- **D09.** `ElicitInput` documents the typed plan (`stated_intent`, before
  writing, every attempt) as separate from `revision_reason`; tests show a
  reason never stands in for the plan.
- **D01.** `NeedBasis.STUDENTS` keeps its value; every label (API
  `need_labels`/`need_label`, Instrument view, README, TRACEABILITY) now reads
  "Classroom studies", defined as "Need observed in a classroom study through
  its design or its self-report data."
- **M16.** `grades.py` basis/limit text now follows tab:evidence row by row:
  removed "as Veenman et al. predicted" (row 2), "recreated the overload"
  (row 14), "not significant" (row 24 -> "small and untested"), the PicPrompt
  decline as a basis (row 21), "validated signals" (row 11), "Established in
  mathematics" (row 6), "no intervals" (row 1). `escalation.py` quotes PyPal's
  trigger as "I'm stuck". `about.py` drops Veenman, the PicPrompt decline as a
  justification, and the non-significant strengths for R3 and R5.
- 329 tests passing (new `tests/test_review_r2.py`); TRACEABILITY.md
  regenerated; `web/dist` rebuilt.

## Follow-up: component 20 regraded (M7 decision)
- *Visible consequence before coaching* is now **Argued** (was Direct). Basis:
  "Both games showed students the output first and students accepted it
  (self-report); the order was never varied, so the mechanism is untested."
  Need basis unchanged (Classroom studies).
- Mechanism counts: **4 Direct / 10 Transferred / 10 Argued** (was 5/10/9);
  need basis still 4 Classroom studies / 18 Builds / 2 Argument.
  `EXPECTED_GRADE_COUNTS` updated. The Direct definition no longer mentions a
  classroom-based Direct row: the four Direct rows are the Build 1
  measurement rows, and a new test pins exactly those four.
- README tables and counts, Instrument view comment, and about.py's R1
  strength updated. D04's band 4-5 success rule kept as implemented.
- about.py's thesis statement now copies the revised Chapter 1 statement
  verbatim; the README no longer calls both games "prompt-writing games".
- 330 tests passing; TRACEABILITY.md regenerated (label check passed);
  `web/dist` rebuilt.

## Follow-up: third review round (FINDINGS_LOG_R3 E01, E02, E10; R3_CHAIR C1)
- **E01 / C1, help climbs across revisions.** A revision no longer closes the
  help cycle by itself. New policy value `escalation.cycle`: a help cycle is
  the help given on one task for one top-ranked category. Each revision is
  first measured by Layer 5; if the same category is still ranked first, the
  paired dimension did not improve and level 4 has not been issued, the cycle
  stays open and Layer 4 answers the revision. The cycle closes when the
  paired dimension improves, the top category changes or nothing is
  diagnosed, on the attempt after level 4 (recorded in `Session.unresolved`,
  level 4 is not repeated), or on a task move. A revision opens a new cycle
  only when she asks for more help. `escalation.consecutive_unresolved` now
  counts consecutive attempts (first attempts and revisions) with the same
  top category, supplied by the session in `RespondInput.consecutive_same_top`
  (the old count was `len(levels_issued)`), and its value is **2** (was 3): help
  moves up one rung on each attempt where the same category is ranked first
  again, so attempt + 3 revisions = levels 1, 2, 3, 4. D03 is unchanged and
  still governs the three evaluative-paired diagnoses. The revision hold and
  the ladder are independent: the first reasoned revision releases the hold
  while help keeps climbing; an unreasoned revision stops at Layer 1 and
  neither raises nor resets help, but counts toward the 4-attempt exit.
  `CycleResult.help_cycle` / API `help_cycle` say what happened to the cycle.
  `gating.streak_unit` re-worded (value `each_layer_5_run`): one outcome per
  Layer 5 run, which is every scored revision and a first attempt with
  nothing to diagnose, as before.
- **"I need more help".** Coach view: a toggle under the coaching; Session
  view: a checkbox beside "Send revision". Both send `asked_for_help` with the
  next try. Coach keeps the revise loop open while a revision gets more help.
- **Blind-acceptance bug** (Layers 3-4 run 1). The session now records on
  each attempt the help response it followed (`triggering_intervention_id`),
  and Layer 3 counts the current attempt's record as well as the history.
  Blind acceptance now fires offline on an unchanged resubmission after help.
- **E02, which detector runs.** Layer 5 calls the judge engine's own
  over-reliance detector: `GeminiEngine.sentinel` live (the detector
  `eval/benchmark.py` measured), `DeterministicEngine.sentinel` offline (the
  old keyword rules, moved from `layers/calibrate.py` and labelled an
  unbenchmarked stand-in). `CalibrateOutput.sentinel_source` names the
  detector; a failed call or an engine without a detector (OpenRouter) gives
  no signals and is never filled in with the keyword rules. Layer 3 does not
  read the sentinel (docs and a test say so).
- **Need-basis label** "Classroom studies" -> "User studies", definition "Need
  observed in a user study with students, through its design or its
  self-report data." Ids unchanged (`NeedBasis.STUDENTS` = "students").
  Descriptive mentions of the two studies in about.py, README, About and
  Instrument views and the TRACEABILITY chapter map now say "user study",
  matching the thesis; about.py's thesis statement again matches Chapter 1
  verbatim. The old book title string in about.py/README is unchanged.
- **Not changed (item 6):** the authorship check and the diagnosis prompts.
- **Layers 3-4, run 2** (`eval/results/layers34-20261024-143717.*`, run 1 kept):
  same protocol; the recorder also delegates `sentinel`, and `--label/--note`
  print the run label. Differences from run 1 are appended to the run 2 report.
- 356 tests passing (new `tests/test_review_r3.py`, 25 tests);
  TRACEABILITY.md regenerated; `web/dist` rebuilt.
