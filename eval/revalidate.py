"""Chapter 3's protocols, runnable.

    python -m eval.revalidate --cases eval/cases.json

sec:method is the reason this exists rather than a
constant in a config file:

    "A reliability coefficient tied to two specific model versions expires when
    either is retired, so a system built to this framework needs a revalidation
    procedure rather than a one time certificate."

Two of Measure's three bars are recomputed here.

**Cross-model agreement.** Two scorers from different organisations, ICC(2,2) on
the overall score plus per-dimension weighted kappa. sec:measure - "A score two models
from different vendors agree on is not an artifact of one model's idiosyncrasy".
The script refuses to report agreement between two models from the same vendor as
if it were that bar.

**Paraphrase invariance.** sec:measure - a rubric "can be perfectly reliable and still
be measuring vocabulary sophistication, which would systematically penalize
multilingual students". Each case is machine-paraphrased and rescored; the
reported figure is mean absolute shift.

The third bar, agreement with a human rater, is not here because it cannot be:
it needs teachers. That absence is the point, and the report says so.

Numbers are reported against the three-point span between the scale's extremes,
not against four. sec:method records that the published paper divided by 4 in two
places and that the correct figures are 4.5 and 8.7 percent.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promptcoach_ref.engines.base import Engine, EngineError, ScoringRequest
from promptcoach_ref.framework import rubric


@dataclass
class Case:
    id: str
    stated_intent: str
    prompt_text: str
    paraphrase: str = ""


def icc_2_2(pairs: list[tuple[float, float]]) -> float | None:
    """Two-way random, average-measures ICC over paired ratings.

    Returned as None rather than 0.0 when it cannot be computed, because "the
    variance was too small to estimate" and "the raters disagree completely" are
    different facts.
    """
    n = len(pairs)
    if n < 2:
        return None
    grand = statistics.fmean([v for pair in pairs for v in pair])
    row_means = [statistics.fmean(pair) for pair in pairs]
    col_means = [
        statistics.fmean([p[0] for p in pairs]),
        statistics.fmean([p[1] for p in pairs]),
    ]

    ms_rows = 2 * sum((m - grand) ** 2 for m in row_means) / (n - 1)
    ms_cols = n * sum((m - grand) ** 2 for m in col_means)
    ss_total = sum((v - grand) ** 2 for pair in pairs for v in pair)
    ss_error = ss_total - (ms_rows * (n - 1)) - ms_cols
    df_error = n - 1
    if df_error <= 0:
        return None
    ms_error = ss_error / df_error
    denominator = ms_rows
    if denominator == 0:
        return None
    return round((ms_rows - ms_error) / denominator, 4)


def weighted_kappa(a: list[int], b: list[int], k: int = 4) -> float | None:
    """Linear-weighted kappa on an integer scale of size k."""
    if not a or len(a) != len(b):
        return None
    n = len(a)
    observed = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        observed[x - 1][y - 1] += 1
    row = [sum(observed[i]) for i in range(k)]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = abs(i - j) / (k - 1)
            expected = row[i] * col[j] / n
            num += w * observed[i][j]
            den += w * expected
    if den == 0:
        return None
    return round(1 - num / den, 4)


def score_overall(engine: Engine, case: Case, text: str) -> tuple[float | None, dict]:
    request = ScoringRequest(
        prompt_text=text, stated_intent=case.stated_intent, task_scenario=""
    )
    sample = engine.sample_scores(request, 0.2)
    values = {
        d.dimension_id: d.value
        for d in sample.dimensions
        if d.value is not None
        and rubric.RUBRIC_MIN <= d.value <= rubric.RUBRIC_MAX
    }
    if not values:
        return None, {}
    return statistics.fmean(values.values()), values


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", default=str(Path(__file__).parent / "cases.json"))
    ap.add_argument("--offline", action="store_true", help="use the rule engine")
    args = ap.parse_args()

    cases = [Case(**row) for row in json.loads(Path(args.cases).read_text("utf-8"))]

    if args.offline or not os.environ.get("OPENROUTER_API_KEY"):
        from promptcoach_ref.engines import DeterministicEngine

        primary: Engine = DeterministicEngine()
        comparator: Engine = DeterministicEngine()
        print("Running offline on the rule engine.")
        print("This exercises the protocol. It is NOT a reliability result: both")
        print("scorers are the same deterministic rules, so agreement is trivial.\n")
    else:
        from promptcoach_ref.engines import openrouter

        primary = openrouter.build("primary")
        comparator = openrouter.build("comparator")
        print(f"Primary    : {primary.name} ({primary.organisation})")
        print(f"Comparator : {comparator.name} ({comparator.organisation})\n")

    same_org = primary.organisation == comparator.organisation

    paired: list[tuple[float, float]] = []
    per_dim: dict[str, tuple[list[int], list[int]]] = {
        d.id: ([], []) for d in rubric.DIMENSIONS
    }
    shifts: list[float] = []

    for case in cases:
        try:
            a_overall, a_dims = score_overall(primary, case, case.prompt_text)
            b_overall, b_dims = score_overall(comparator, case, case.prompt_text)
        except EngineError as exc:
            print(f"  {case.id}: skipped ({exc})")
            continue

        if a_overall is None or b_overall is None:
            continue
        paired.append((a_overall, b_overall))
        for dim_id, (xs, ys) in per_dim.items():
            if dim_id in a_dims and dim_id in b_dims:
                xs.append(a_dims[dim_id])
                ys.append(b_dims[dim_id])

        if case.paraphrase:
            p_overall, _ = score_overall(primary, case, case.paraphrase)
            if p_overall is not None:
                shifts.append(abs(p_overall - a_overall))

    print(f"n = {len(paired)} paired cases\n")

    print("CROSS MODEL AGREEMENT")
    if same_org:
        print("  NOT the cross model bar. Both scorers are the same organisation,")
        print("  so this measures one vendor's self consistency.")
    icc = icc_2_2(paired)
    print(f"  ICC(2,2) overall     : {icc}   (thesis reported {rubric.OVERALL_ICC_2_2})")
    gaps = [abs(a - b) for a, b in paired]
    if gaps:
        print(
            f"  mean grader gap      : {statistics.fmean(gaps):.3f} points   "
            f"(thesis reported {rubric.MEAN_GRADER_GAP_POINTS})"
        )
    for dim in rubric.DIMENSIONS:
        xs, ys = per_dim[dim.id]
        k = weighted_kappa([round(v) for v in xs], [round(v) for v in ys])
        print(f"    {dim.name:24s} kappa {k}   (thesis {dim.weighted_kappa})")
    print("  NOTE: overall weighted kappa is 'n/a' in tab:agreement. None is computed.")

    print("\nPARAPHRASE INVARIANCE")
    if shifts:
        mean_shift = statistics.fmean(shifts)
        pct = 100 * mean_shift / rubric.RUBRIC_SPAN
        print(
            f"  mean absolute shift  : {mean_shift:.3f} points = {pct:.1f}% of the "
            f"{rubric.RUBRIC_SPAN}-point span"
        )
        print(f"    (thesis reported {rubric.PARAPHRASE_MEAN_ABSOLUTE_SHIFT}, 4.5%)")
        print(f"  largest single shift : {max(shifts):.3f}")
    else:
        print("  no paraphrases in the case file")

    print("\nTHE THIRD BAR")
    print(f"  {rubric.THIRD_BAR_UNCLEARED}")
    print("  It is not computed here because it needs teachers, not models.")
    print(f"\n  {rubric.SHARED_PRIOR_THREAT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
