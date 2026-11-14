# Layers 3 and 4 on the 30-item benchmark: protocol

Fixed on 2026-10-24, before the run. Results are reported as they come out.
No prompt, rule, threshold or template is changed during or after the run. If
something is clearly broken, the report says so and nothing is fixed in this run.

## Why

A hostile review pointed out that Layer 3 (Diagnose) and Layer 4 (Respond, with
its authorship check, `layers/respond.py::validate`) had been exercised on one
worked example only. This run puts all 30 benchmark items through them.

## Corpus

`eval/benchmark.json`, the 30 author-written items used by the Chapter 11
replication (`eval/benchmark.py`): 11 weak, 12 medium, 7 strong; 15 clean,
15 with a noise category (sarcastic 2, mindless_retry 3, pasted_ai_text 4,
disfluent 2, ell 2, typos 1, deferent 1). Tier, risk and noise labels were
fixed by the author before any scoring. No student data.

## Input per item

- **Prompt:** `prompt_text`, verbatim.
- **Plan:** the corpus has no spoken-transcript field. It has one plan field,
  `stated_intent`, the author-written statement of what the student was trying
  to do. That is used as the plan, with `intent_modality="typed"` (the session
  default; the corpus does not say it was spoken). No plan is invented. (Layer 1
  refuses an empty plan, so an item without one would stop at Elicit. Every item
  has one.)
- **Prior-turn history:** `history`, where present (w07, w08, w09: one prior
  prompt each). The corpus gives no plan for the prior turn, so the item's own
  `stated_intent` is reused for it; nothing is invented. The prior turn is
  submitted first in the same session as an ordinary attempt (no parent, so not
  a revision). Its outputs are recorded but are not counted as an item.
- **Everything else** is the Session default: task `b3-babysitting` (the worked
  example task; the corpus items belong to no task-bank task, so its protected
  judgment is the one the authorship check uses), no predicted rating, no reason,
  no inserted spans, `asked_for_help=False`, selection mode `diagnosis`,
  consent: platform use yes, research no, audio no.

## Code path

**Primary (the real path).** One fresh `Session` per item,
`Session.submit(...)`: Layer 1 Elicit, Layer 2 Measure (3-temperature
ensemble), the generator answers the prompt, Layer 3 Diagnose, Layer 4 Respond
with `validate()`. Respond runs only where the real session runs it (a score is
available and Diagnose returned a target). For the three history items the
second submission carries `levels_issued=(1,)` from the prior turn, so the
escalation policy may issue a level above 1; that is recorded as the final
level, not overridden.

**Secondary (declared now, used only if needed).** If the primary path stops
before Layer 4 for an item (Measure routes to clarification or human review,
or Diagnose returns no target), the item is additionally run through
`DiagnoseLayer.run` and `RespondLayer.run` directly with the same Layer 1
record and Layer 2 scores, `levels_already_issued=()`. Reported separately and
labelled "forced"; never merged with the primary numbers.

Engines are wrapped in a pass-through recorder that delegates every call
unchanged and logs the raw `compose` output and per-call latency. It alters
nothing.

## Recorded per item

id, tier, noise category, risk; Layer 2 scores and overall; routing; top
category and full ranked list (category, confidence, trigger);
insufficient-evidence flag; the stage the session stopped at; Respond level;
the raw first generated reply; whether `validate()` blocked it (the reason
string); whether the generator returned nothing; whether the template floor was
served and passed `validate()` (the code raises if the floor fails, which is
recorded as a crash); final response text; selection reason; any exception with
its traceback; wall-clock latency per item and per engine call (live only).

Note on "regenerated reply": the code does not regenerate. On a blocked or
empty generation it serves the template floor and validates that. "Passed after
block" therefore means "template floor served and passed".

Note on the offline engine: its `compose` *is* the template floor, so the
"first generated reply" offline is the template itself. A block there would be
the floor failing its own check.

## Reported

1. Distribution of top categories: overall, by tier, by noise category
   (clean items as their own group).
2. Category given its source signal. The source signal is the taxonomy's
   `derived_from` signal (`framework/sentinel.py`): transcript-prompt
   disconnect -> intent drift, excessive deference -> delegated judgment,
   mindless retry -> undiagnosed retry, copied AI content -> borrowed phrasing.
   "Fired" is defined two ways, both reported:
   - (a) **author label**: noise `mindless_retry` -> mindless retry,
     `pasted_ai_text` -> copied AI content, `deferent` -> excessive deference.
     No corpus label corresponds to transcript-prompt disconnect, and
     `sarcastic` is not mapped to any signal (the corpus does not say which it
     is); both are reported as unmapped.
   - (b) **the implementation's own sentinel**: offline, the rule formula in
     `CalibrateLayer._sentinel` evaluated on the item's record (and its prior
     turn as parent for history items); live, `GeminiEngine.sentinel` on the
     scorer (one call per item, as `eval/benchmark.py` does). Fired = value
     >= 0.5, the cut `eval/benchmark.py` uses (the thesis commits to no threshold).
   For each signal: n fired, n where the derived category is top, n where it is
   anywhere in the ranked list.
3. Authorship check: first-pass block rate (blocked / replies generated),
   empty-generation count, template-floor count, final pass rate
   (responses served that passed `validate()` / items reaching Layer 4), and
   the block reasons.
4. Final response level distribution.
5. Crashes (any exception), per engine.
6. Live only: latency per item and per call (mean, P95, max) for scorer,
   generator, and the Layer 3 and Layer 4 calls.

## Engines

1. **Offline deterministic** (`DeterministicEngine`, scripted responder),
   always. Deterministic; one run.
2. **Live Gemini**, if the project `.env` key works: judge
   `gemini-3.1-flash-lite` (scores, diagnoses, composes), generator per current
   defaults (`policy/generator.py`: `gemini-3.1-pro-preview` unless
   `PROMPTCOACH_GENERATOR` is set), no cross-model comparator (the app's
   default). One run per item. A one-call preflight decides whether the key
   works; if it fails, the report says so and only the offline run is reported.
   Model sampling is not seedable here; that is stated, not hidden.

Seed: `random.seed(20261024)`. Attempt ids use `uuid4` and are not seeded; they
affect nothing measured.

No API key, email or other personal identifier is printed or written to the
results. Benchmark items are author-written.

## Outputs

- `eval/layers34.py` (the script)
- `eval/results/layers34-<timestamp>.json` (everything per item)
- `eval/results/layers34-<timestamp>.md` (summary)

Afterwards the full test suite is run and must stay green.
