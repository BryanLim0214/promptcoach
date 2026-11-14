# Protocol: detector separability (A) and content over fluency (B)

Fixed 2026-10-24, before any analysis below was run and before any item in
`eval/fluency_pairs.json` was scored. Nothing in this file is to be changed
after results are seen. Any departure is reported as a departure in the results
file, not edited in here.

Script: `eval/fluency_detector.py`. Outputs:
`eval/results/fluency_detector-<timestamp>.json` and `.md`.

Two components, two reviewer points:

| Analysis | Component | Reviewer point |
|---|---|---|
| A | Over-reliance is separable | M5 |
| B | Content over fluency | M6 |

---

## Analysis A: does the sentinel add information beyond the prompt score?

### Question

The sentinel discriminates high- from low-risk items (pooled AUC 0.882 in the
replication). Six of the nine high-risk items are also weak-tier items. If the
prompt score alone separates the risk label as well, the sentinel is not shown
to measure anything separable from prompt quality.

### Data

Existing output only, no new model calls:
`eval/results/benchmark-20260906-160831.json` (30 items x 5 runs = 150
scorings), corpus `eval/benchmark.json`.

For each scoring:

- `rubric` = grader A's overall rubric score (`a_overall`: the mean of the six
  ensemble-merged dimension scores, scale 1 to 4).
- `sentinel` = the sentinel aggregate exactly as `eval/benchmark.py` computes
  it: the maximum of the four signal values (`transcript_prompt_disconnect`,
  `excessive_deference`, `mindless_retry`, `copied_ai_content`).
- `label` = 1 if the item's risk is `high`, 0 if `low`.

A scoring with a missing rubric score or empty signals is dropped and the count
reported.

### Computations

1. AUC of `sentinel` for `label`, as U/(n1 n2) with ties counted one half.
   Reproduction check: pooled value should be 0.882.
2. AUC of `-rubric` (a lower prompt score predicts high risk), same method.
3. Logistic regression by maximum likelihood (Newton-Raphson, implemented on
   numpy/scipy because statsmodels is not installed):
   - M1: `label ~ 1 + rubric`
   - M2: `label ~ 1 + rubric + sentinel`
   - Likelihood-ratio statistic 2(LL2 - LL1), chi-square with 1 df, p reported.
   - In-sample AUC of each model's fitted linear predictor.
   - Coefficients and Wald SEs reported for completeness.
   - If either model shows complete or quasi-complete separation (no finite
     MLE), this is reported as such and the LR p is flagged as unreliable; no
     penalisation is substituted after the fact.
4. All of 1 to 3 computed twice:
   - **Scoring level**: n = 150 (5 runs x 30 items).
   - **Item level**: n = 30, each item's `rubric` and `sentinel` averaged over
     its 5 runs.

### Unit of analysis

The five runs rescore the same 30 items, so the 150 scorings are 30 clusters of
5, not 150 independent observations. The scoring-level LR test treats reruns as
new evidence and its p-value is anti-conservative. **The item level (n = 30, 9
high risk, 21 low risk) is the honest unit and is the primary result.** The
scoring-level figures are reported only so the 0.882 reproduction can be
checked and so the reader can see how much the unit changes the conclusion.

### Reading rule (fixed in advance)

- The sentinel is reported as **adding information beyond the prompt score** if
  the item-level LR test gives p < 0.05 and the item-level M2 AUC exceeds the
  M1 AUC.
- Otherwise the result is reported as **not shown to add information** on this
  corpus. With 9 positives this test has little power, so a null is reported
  as "not shown", never as "shown not to".
- Whatever the outcome, the corpus labels were written by the same author who
  wrote the items, so neither reading is evidence about students.

---

## Analysis B: content over fluency with matched pairs

### Question

Does the live scorer give the same score to the same planning content whether
it is written in fluent standard English or in the rough English typical of an
English language learner?

### Items

`eval/fluency_pairs.json`, 12 matched pairs written for this analysis before
any scoring, none reused from `eval/benchmark.json`.

- Each pair has one `stated_intent` used for **both** versions, written in
  plain simple English, so the only thing that differs within a pair is the
  typed prompt.
- `fluent`: standard English.
- `rough`: the same content (topic, audience, format, constraints, purpose)
  with grammar and spelling errors and simpler vocabulary typical of an English
  language learner. No content element is removed.
- Content quality spread fixed by the author before scoring: 4 pairs `weak`,
  4 `medium`, 4 `strong`.

### Scoring

- Live Gemini scorer, `gemini-3.1-flash-lite` (the configured `scorer` role),
  run as the three-judge ensemble exactly as `eval/benchmark.py` does it:
  temperatures 0.2 / 0.5 / 0.8, each dimension merged as the rounded mean of
  the judges that returned a valid value, overall = mean of merged dimensions.
- 3 runs per item (24 items x 3 runs x 3 judges = 216 scoring calls).
- An item-run with no valid judge is dropped and counted. A version's score is
  the mean over its successful runs. A pair with no successful run for either
  version is excluded and reported.
- If live scoring fails entirely, the offline rule engine is run instead and
  this is stated; **offline results do not count for the decision rule**, and
  the decision is then reported as "not evaluated".

### Statistics

- Per pair: d = mean(fluent overall) - mean(rough overall), in rubric points.
- Mean d, SD of d, n = 12 pairs (the pair is the unit; runs are averaged
  within pair before any statistic).
- 95% percentile bootstrap CI of mean d: 10,000 resamples of pairs with
  replacement, `random.Random(20261024)`.
- Descriptive only (not part of the decision): mean d per content stratum, and
  mean within-pair difference per dimension.

### Pre-registered decision rule

The component's **Direct** grade is supported if **both**:

1. mean d (fluent minus rough) is **no more than 0.25** points on the 1 to 4
   scale (about twice the 0.134 paraphrase noise), **and**
2. the upper bound of the 95% bootstrap CI is **below 0.5**.

Otherwise the component is regraded **Argued**.

The rule is one-sided by design: it asks whether rough English is penalised.
A negative mean d (rough scored higher) satisfies condition 1; it is reported
and commented on, but does not by itself change the decision.

### Limits stated in advance

- The pairs were written by one author, who also wrote the rough versions; they
  imitate learner English, they are not learner English.
- 12 pairs is small; the CI is the honest statement of what it can show.
- The scorer's system prompt instructs it to ignore grammar and spelling, so
  this tests whether that instruction is followed, on one model version.
