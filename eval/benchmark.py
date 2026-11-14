"""Run the Chapter 3 protocols live against Gemini and report measured results.

    python -m eval.benchmark --repeats 3

Five protocols, all from sec:method:

  1. Three-judge ensemble self-consistency  (temps 0.2 / 0.5 / 0.8)
  2. Cross-model-version agreement           (two Gemini versions)
  3. Paraphrase invariance                   (machine rewrite, rescore)
  4. Tier discrimination                     (researcher-assigned weak/medium/strong)
  5. Over-reliance sentinel discrimination   (9 high-risk vs 21 low-risk)

Plus latency, because sec:threats makes it an ecological
threat and not a footnote.

TWO THINGS THIS CANNOT DO, stated up front because overstating them would be
worse than not running it:

**This is not the cross-vendor bar.** sec:measure - "A score two
models from different vendors agree on is not an artifact of one model's
idiosyncrasy". Both models here are Google. What this measures is agreement
across *model versions from one vendor*, which is a different and weaker claim.
It does, however, answer the question sec:method raises: whether a coefficient tied
to specific model versions survives a version change.

**This is not agreement with a teacher.** That is Measure's third bar and the
thesis does not clear it either. It needs people.

Where the thesis reports point estimates with no intervals, this reports
percentile bootstrap intervals, because sec:build1 names the
absence of intervals as a limitation of the original.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promptcoach_ref.engines.base import EngineError, ScoringRequest
from promptcoach_ref.engines.gemini import GeminiEngine, build, load_env
from promptcoach_ref.framework import rubric, sentinel as sentinel_spec

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------


def icc_2_2(pairs: list[tuple[float, float]]) -> float | None:
    """ICC(2,k) - two-way random effects, ABSOLUTE agreement, average measures.

        ICC(2,k) = (MSR - MSE) / (MSR + (MSC - MSE) / n)

    The rater term MSC stays in the denominator, which is what makes this
    absolute agreement rather than consistency. The difference is not academic:
    the consistency form, ICC(C,k), returns exactly 1.0 for a rater who is
    always half a point high, so it would report perfect agreement between two
    graders that never once produced the same number. Chapter 6 reports
    ICC(2,2), so this is the form its figures have to be compared against.

    Returns None when there is no between-item variance to attribute agreement
    to - reporting 1.0 there would be an artifact, not a result.
    """
    n = len(pairs)
    k = 2
    if n < 3:
        return None

    values = [v for p in pairs for v in p]
    grand = statistics.fmean(values)
    row_means = [statistics.fmean(p) for p in pairs]
    col_means = [
        statistics.fmean([p[0] for p in pairs]),
        statistics.fmean([p[1] for p in pairs]),
    ]

    ss_rows = k * sum((m - grand) ** 2 for m in row_means)
    ss_cols = n * sum((m - grand) ** 2 for m in col_means)
    ss_total = sum((v - grand) ** 2 for v in values)
    ss_error = ss_total - ss_rows - ss_cols

    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))

    denominator = ms_rows + (ms_cols - ms_error) / n
    if denominator <= 0 or ms_rows == 0:
        return None
    return (ms_rows - ms_error) / denominator


def weighted_kappa(a: list[int], b: list[int], k: int = 4) -> float | None:
    """Linear-weighted kappa on a 1..k integer scale."""
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        if not (1 <= x <= k and 1 <= y <= k):
            return None
        obs[x - 1][y - 1] += 1
    row = [sum(r) for r in obs]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = abs(i - j) / (k - 1)
            num += w * obs[i][j]
            den += w * (row[i] * col[j] / n)
    if den == 0:
        return None
    return 1 - num / den


def auc_mann_whitney(positive: list[float], negative: list[float]) -> float | None:
    """U / (n1*n2) - the rank statistic the thesis reports as an AUC.

    sec:build1 calls it "the rank based statistic U/(n1n2), which
    is the area under the curve". Ties count a half, as they must.
    """
    if not positive or not negative:
        return None
    wins = 0.0
    for p in positive:
        for q in negative:
            if p > q:
                wins += 1
            elif p == q:
                wins += 0.5
    return wins / (len(positive) * len(negative))


def _percentiles(draws: list[float], alpha: float) -> tuple[float, float] | None:
    if len(draws) < 20:
        return None
    draws.sort()
    lo = draws[int((alpha / 2) * len(draws))]
    hi = draws[int((1 - alpha / 2) * len(draws)) - 1]
    return lo, hi


def clustered_bootstrap_ci(
    clusters: dict[str, list[Any]],
    fn,
    reps: int = 4000,
    alpha: float = 0.05,
) -> tuple[float, float] | None:
    """Percentile bootstrap resampling *items*, not observations.

    A repeated run rescores the same 30 items, so the 90 rows are 30 clusters of
    3 and not 90 independent observations. Resampling rows would treat a rerun
    as new evidence and narrow every interval by roughly sqrt(3) for free.

    The thesis does the same thing where it reports intervals at all - "case
    bootstrap" and "source-item-clustered bootstrap" in Chapter 6 - so this
    matches its unit of resampling as well as its method.
    """
    keys = list(clusters)
    if len(keys) < 4:
        return None
    rng = random.Random(20260906)
    draws: list[float] = []
    for _ in range(reps):
        picked: list[Any] = []
        for _ in range(len(keys)):
            picked.extend(clusters[keys[rng.randrange(len(keys))]])
        try:
            value = fn(picked)
        except statistics.StatisticsError:
            continue
        if value is not None:
            draws.append(value)
    return _percentiles(draws, alpha)


def by_item(rows: list[dict[str, Any]], extract) -> dict[str, list[Any]]:
    """Group extracted values under their item id."""
    out: dict[str, list[Any]] = {}
    for row in rows:
        value = extract(row)
        if value is None:
            continue
        out.setdefault(row["id"], []).append(value)
    return out


def fmt(v: float | None, places: int = 3) -> str:
    return "n/a" if v is None else f"{v:.{places}f}"


def fmt_ci(ci: tuple[float, float] | None, places: int = 3) -> str:
    if ci is None:
        return ""
    return f" [{ci[0]:.{places}f}, {ci[1]:.{places}f}]"


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


@dataclass
class Item:
    id: str
    tier: str
    clean: bool
    risk: str
    noise_kind: str | None
    stated_intent: str
    prompt_text: str
    paraphrase: str
    history: list[str] = field(default_factory=list)


def score_once(
    engine: GeminiEngine, item: Item, text: str, temperature: float
) -> dict[str, int] | None:
    request = ScoringRequest(
        prompt_text=text, stated_intent=item.stated_intent, task_scenario=""
    )
    try:
        sample = engine.sample_scores(request, temperature)
    except EngineError:
        return None
    out: dict[str, int] = {}
    for d in sample.dimensions:
        if d.value is None:
            continue
        if not (rubric.RUBRIC_MIN <= d.value <= rubric.RUBRIC_MAX):
            continue  # discarded, never clamped
        out[d.dimension_id] = d.value
    return out or None


def overall(scores: dict[str, int]) -> float:
    return statistics.fmean(scores.values())


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------


def run_once(items: list[Item], workers: int, run_index: int) -> dict[str, Any]:
    scorer = build("scorer")
    comparator = build("comparator")

    print(f"  run {run_index}: {scorer.model} vs {comparator.model}")

    def ensemble(item: Item) -> dict[str, Any]:
        samples = [
            score_once(scorer, item, item.prompt_text, t) for t in (0.2, 0.5, 0.8)
        ]
        samples = [s for s in samples if s]
        if not samples:
            return {"id": item.id, "ok": False}

        merged: dict[str, int] = {}
        spreads: list[float] = []
        for dim in rubric.DIMENSIONS:
            vals = [s[dim.id] for s in samples if dim.id in s]
            if not vals:
                continue
            merged[dim.id] = round(statistics.fmean(vals))
            if len(vals) > 1:
                spreads.append(statistics.pstdev(vals))

        other = score_once(comparator, item, item.prompt_text, 0.2)
        para = score_once(scorer, item, item.paraphrase, 0.2)
        try:
            signals = scorer.sentinel(
                item.stated_intent, item.prompt_text, tuple(item.history)
            )
        except EngineError:
            signals = {}

        return {
            "id": item.id,
            "ok": True,
            "tier": item.tier,
            "risk": item.risk,
            "noise_kind": item.noise_kind,
            "a": merged,
            "a_overall": overall(merged) if merged else None,
            "ensemble_spread": statistics.fmean(spreads) if spreads else 0.0,
            "b": other,
            "b_overall": overall(other) if other else None,
            "paraphrase": para,
            "paraphrase_overall": overall(para) if para else None,
            "signals": signals,
        }

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(ensemble, items))
    wall = time.perf_counter() - started

    return {
        "run": run_index,
        "rows": [r for r in rows if r.get("ok")],
        "wall_seconds": round(wall, 1),
        "scorer": scorer.stats(),
        "comparator": comparator.stats(),
    }


def analyse(runs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for run in runs for r in run["rows"]]
    n_items = len({r["id"] for r in rows})
    out: dict[str, Any] = {
        "n_scored": len(rows),
        "n_items": n_items,
        "n_runs": len(runs),
    }

    # --- 1. ensemble self-consistency -----------------------------------
    spreads = [r["ensemble_spread"] for r in rows]
    out["ensemble_spread_mean"] = statistics.fmean(spreads) if spreads else None
    out["ensemble_spread_ci"] = clustered_bootstrap_ci(
        by_item(rows, lambda r: r["ensemble_spread"]), statistics.fmean
    )
    out["ensemble_exact_agreement"] = (
        sum(1 for s in spreads if s == 0.0) / len(spreads) if spreads else None
    )

    # --- 2. cross-model-version agreement -------------------------------
    pairs = [
        (r["a_overall"], r["b_overall"])
        for r in rows
        if r["a_overall"] is not None and r["b_overall"] is not None
    ]
    out["n_paired"] = len(pairs)
    out["icc"] = icc_2_2(pairs)
    out["icc_ci"] = clustered_bootstrap_ci(
        by_item(
            rows,
            lambda r: (r["a_overall"], r["b_overall"])
            if r["a_overall"] is not None and r["b_overall"] is not None
            else None,
        ),
        icc_2_2,
    )
    gaps = [abs(a - b) for a, b in pairs]
    out["mean_gap"] = statistics.fmean(gaps) if gaps else None
    out["mean_gap_ci"] = clustered_bootstrap_ci(
        by_item(
            rows,
            lambda r: abs(r["a_overall"] - r["b_overall"])
            if r["a_overall"] is not None and r["b_overall"] is not None
            else None,
        ),
        statistics.fmean,
    )

    per_dim: dict[str, Any] = {}
    for dim in rubric.DIMENSIONS:
        xs = [r["a"][dim.id] for r in rows if dim.id in r["a"] and r["b"] and dim.id in r["b"]]
        ys = [r["b"][dim.id] for r in rows if dim.id in r["a"] and r["b"] and dim.id in r["b"]]
        k = weighted_kappa(xs, ys)
        exact = (
            sum(1 for x, y in zip(xs, ys) if x == y) / len(xs) if xs else None
        )
        within1 = (
            sum(1 for x, y in zip(xs, ys) if abs(x - y) <= 1) / len(xs) if xs else None
        )
        per_dim[dim.id] = {
            "name": dim.name,
            "kappa": k,
            "exact": exact,
            "within_one": within1,
            "n": len(xs),
            "thesis_kappa": dim.weighted_kappa,
        }
    out["per_dimension"] = per_dim

    # --- 3. paraphrase invariance ---------------------------------------
    shifts = [
        abs(r["a_overall"] - r["paraphrase_overall"])
        for r in rows
        if r["a_overall"] is not None and r["paraphrase_overall"] is not None
    ]
    out["n_paraphrase"] = len(shifts)
    out["paraphrase_shift"] = statistics.fmean(shifts) if shifts else None
    out["paraphrase_shift_ci"] = clustered_bootstrap_ci(
        by_item(
            rows,
            lambda r: abs(r["a_overall"] - r["paraphrase_overall"])
            if r["a_overall"] is not None and r["paraphrase_overall"] is not None
            else None,
        ),
        statistics.fmean,
    )
    out["paraphrase_pct_of_span"] = (
        100 * statistics.fmean(shifts) / rubric.RUBRIC_SPAN if shifts else None
    )
    out["paraphrase_max"] = max(shifts) if shifts else None
    out["paraphrase_over_half_point"] = (
        sum(1 for s in shifts if s > 0.5) if shifts else 0
    )

    # --- 4. tier discrimination -----------------------------------------
    tiers: dict[str, list[float]] = {"weak": [], "medium": [], "strong": []}
    for r in rows:
        if r["a_overall"] is not None:
            tiers[r["tier"]].append(r["a_overall"])
    out["tiers"] = {
        name: {
            "n": len(vals),
            "n_items": len({r["id"] for r in rows if r["tier"] == name}),
            "mean": statistics.fmean(vals) if vals else None,
            "ci": clustered_bootstrap_ci(
                by_item(
                    [r for r in rows if r["tier"] == name],
                    lambda r: r["a_overall"],
                ),
                statistics.fmean,
            ),
        }
        for name, vals in tiers.items()
    }
    if all(tiers[t] for t in tiers):
        out["tier_order_preserved"] = (
            statistics.fmean(tiers["weak"])
            < statistics.fmean(tiers["medium"])
            < statistics.fmean(tiers["strong"])
        )
        out["weak_to_medium_gap"] = statistics.fmean(tiers["medium"]) - statistics.fmean(
            tiers["weak"]
        )
        out["medium_to_strong_gap"] = statistics.fmean(
            tiers["strong"]
        ) - statistics.fmean(tiers["medium"])

    # --- 5. sentinel discrimination -------------------------------------
    def agg(signals: dict[str, float]) -> float | None:
        vals = [v for k, v in signals.items() if k in sentinel_spec.BY_ID]
        return max(vals) if vals else None

    high = [agg(r["signals"]) for r in rows if r["risk"] == "high"]
    low = [agg(r["signals"]) for r in rows if r["risk"] == "low"]
    high = [v for v in high if v is not None]
    low = [v for v in low if v is not None]
    out["sentinel"] = {
        "n_high": len(high),
        "n_low": len(low),
        "high_mean": statistics.fmean(high) if high else None,
        "low_mean": statistics.fmean(low) if low else None,
        "auc": auc_mann_whitney(high, low),
    }
    per_signal: dict[str, Any] = {}
    for sig in sentinel_spec.SIGNALS:
        h = [r["signals"].get(sig.id, 0.0) for r in rows if r["risk"] == "high"]
        fired = sum(1 for v in h if v >= 0.5)
        per_signal[sig.id] = {
            "name": sig.name,
            "fired_on_high_risk": fired,
            "of": len(h),
        }
    out["sentinel"]["per_signal"] = per_signal

    # --- content over fluency -------------------------------------------
    ell = [r["a_overall"] for r in rows if r["noise_kind"] == "ell" and r["a_overall"]]
    allv = [r["a_overall"] for r in rows if r["a_overall"] is not None]
    out["content_over_fluency"] = {
        "ell_mean": statistics.fmean(ell) if ell else None,
        "benchmark_mean": statistics.fmean(allv) if allv else None,
        "n_ell": len(ell),
    }

    # --- run-to-run stability -------------------------------------------
    # The model is not deterministic, so the same thirty items scored twice give
    # two different coefficients. Pooling hides that; a reader deciding whether
    # to trust a figure needs to see how far it moved between identical runs.
    per_run: list[dict[str, Any]] = []
    for run in runs:
        rs = run["rows"]
        rp = [
            (r["a_overall"], r["b_overall"])
            for r in rs
            if r["a_overall"] is not None and r["b_overall"] is not None
        ]
        shifts_r = [
            abs(r["a_overall"] - r["paraphrase_overall"])
            for r in rs
            if r["a_overall"] is not None and r["paraphrase_overall"] is not None
        ]
        hi = [
            max(v for k, v in r["signals"].items() if k in sentinel_spec.BY_ID)
            for r in rs
            if r["risk"] == "high" and r["signals"]
        ]
        lo = [
            max(v for k, v in r["signals"].items() if k in sentinel_spec.BY_ID)
            for r in rs
            if r["risk"] == "low" and r["signals"]
        ]
        per_run.append(
            {
                "run": run["run"],
                "icc": icc_2_2(rp),
                "paraphrase": statistics.fmean(shifts_r) if shifts_r else None,
                "auc": auc_mann_whitney(hi, lo),
            }
        )
    out["per_run"] = per_run

    def spread(key: str) -> dict[str, Any]:
        vals = [r[key] for r in per_run if r[key] is not None]
        if not vals:
            return {"min": None, "max": None, "range": None}
        return {
            "min": min(vals),
            "max": max(vals),
            "range": max(vals) - min(vals),
        }

    out["stability"] = {k: spread(k) for k in ("icc", "paraphrase", "auc")}

    # --- latency ---------------------------------------------------------
    lat = [
        v
        for run in runs
        for v in (run["scorer"].get("latency_mean_ms"),)
        if v is not None
    ]
    out["latency"] = {
        "scorer_mean_ms": statistics.fmean(lat) if lat else None,
        "runs": [
            {
                "scorer": run["scorer"],
                "comparator": run["comparator"],
                "wall_seconds": run["wall_seconds"],
            }
            for run in runs
        ],
    }
    return out


def report(a: dict[str, Any]) -> str:
    L: list[str] = []
    p = L.append
    span = rubric.RUBRIC_SPAN

    p("=" * 78)
    p("MEASURED RESULTS — PromptCoach Reference against Gemini")
    p("=" * 78)
    p(f"{a['n_items']} items x {a['n_runs']} run(s) = {a['n_scored']} scorings")
    p("")
    p("SCOPE. Both scorers are Google models. This is NOT the cross-vendor bar")
    p("the thesis reports at ICC 0.976; it is agreement across model versions")
    p("from one vendor. It is also not agreement with a teacher, which needs")
    p("people.")
    p("")
    p("Intervals are percentile bootstrap resampling ITEMS, not scorings, so a")
    p("rerun of the same items does not count as new evidence.")
    p("")

    p("-" * 78)
    p("1. THREE-JUDGE ENSEMBLE SELF-CONSISTENCY  (temps 0.2 / 0.5 / 0.8)")
    p("-" * 78)
    p(f"  mean within-ensemble SD : {fmt(a['ensemble_spread_mean'])}"
      f"{fmt_ci(a['ensemble_spread_ci'])} rubric points")
    p(f"  dimensions where all three judges agreed exactly: "
      f"{fmt(a['ensemble_exact_agreement'], 3)}")
    p("  This is one model's self-consistency. It is the confidence mechanism")
    p("  sec:build1 names, and nothing more.")
    p("")

    p("-" * 78)
    p("2. CROSS-MODEL-VERSION AGREEMENT")
    p("-" * 78)
    p(f"  n paired            : {a['n_paired']}")
    p(f"  ICC(2,2) overall    : {fmt(a['icc'])}{fmt_ci(a['icc_ci'])}")
    p(f"                        (thesis, cross-VENDOR: {rubric.OVERALL_ICC_2_2})")
    p(f"  mean grader gap     : {fmt(a['mean_gap'])}{fmt_ci(a['mean_gap_ci'])} points")
    p(f"                        (thesis: {rubric.MEAN_GRADER_GAP_POINTS})")
    p("")
    p(f"  {'dimension':24s} {'kappa':>7s} {'exact':>7s} {'±1':>7s} {'thesis κ':>9s}")
    for dim in rubric.DIMENSIONS:
        d = a["per_dimension"][dim.id]
        p(f"  {d['name']:24s} {fmt(d['kappa']):>7s} {fmt(d['exact'], 2):>7s} "
          f"{fmt(d['within_one'], 2):>7s} {d['thesis_kappa']:>9.3f}")
    p("  No overall weighted kappa is computed: tab:agreement gives 'n/a'.")
    p("")

    p("-" * 78)
    p("3. PARAPHRASE INVARIANCE")
    p("-" * 78)
    p(f"  n                   : {a['n_paraphrase']}")
    p(f"  mean absolute shift : {fmt(a['paraphrase_shift'])}"
      f"{fmt_ci(a['paraphrase_shift_ci'])} points")
    p(f"                      = {fmt(a['paraphrase_pct_of_span'], 1)}% of the "
      f"{span}-point span")
    p(f"                        (thesis: {rubric.PARAPHRASE_MEAN_ABSOLUTE_SHIFT} = 4.5%)")
    p(f"  largest single shift: {fmt(a['paraphrase_max'])}")
    p(f"  shifts over 0.5     : {a['paraphrase_over_half_point']}"
      "   (thesis reported none)")
    p("")

    p("-" * 78)
    p("4. TIER DISCRIMINATION  (researcher-assigned labels, fixed before scoring)")
    p("-" * 78)
    for name in ("weak", "medium", "strong"):
        t = a["tiers"][name]
        p(f"  {name:8s} n={t['n']:<3d} mean {fmt(t['mean'])}{fmt_ci(t['ci'])}")
    if "tier_order_preserved" in a:
        p(f"  order preserved     : {a['tier_order_preserved']}")
        p(f"  weak→medium gap     : {fmt(a['weak_to_medium_gap'])}")
        p(f"  medium→strong gap   : {fmt(a['medium_to_strong_gap'])}")
    p("  A coherence check on constructed items, not a learner-difficulty result.")
    p("")

    p("-" * 78)
    p("5. OVER-RELIANCE SENTINEL DISCRIMINATION")
    p("-" * 78)
    s = a["sentinel"]
    p(f"  high risk n={s['n_high']:<3d} mean {fmt(s['high_mean'])}")
    p(f"  low  risk n={s['n_low']:<3d} mean {fmt(s['low_mean'])}")
    p(f"  AUC (U/n1n2)        : {fmt(s['auc'])}   (thesis: {sentinel_spec.AUC})")
    p("  per signal, fired at >=0.5 on the high-risk items:")
    for sig in sentinel_spec.SIGNALS:
        row = s["per_signal"][sig.id]
        p(f"    {row['name']:32s} {row['fired_on_high_risk']:>2d} / {row['of']}")
    p("  The thesis's warning applies: an aggregate carried by one signal is a")
    p("  detector with one failure mode.")
    p("")

    p("-" * 78)
    p("6. CONTENT OVER FLUENCY")
    p("-" * 78)
    c = a["content_over_fluency"]
    p(f"  second-language items (n={c['n_ell']}): {fmt(c['ell_mean'])}")
    p(f"  benchmark-wide mean            : {fmt(c['benchmark_mean'])}")
    p(f"  (thesis: 3.59 against 2.48)")
    p("")

    p("-" * 78)
    p("7. RUN-TO-RUN STABILITY  (identical items, identical models, rescored)")
    p("-" * 78)
    p(f"  {'run':>4s} {'ICC':>8s} {'paraphrase':>12s} {'AUC':>8s}")
    for r in a["per_run"]:
        p(f"  {r['run']:>4d} {fmt(r['icc']):>8s} {fmt(r['paraphrase']):>12s} "
          f"{fmt(r['auc']):>8s}")
    st = a["stability"]
    p("")
    for key, label in (("icc", "ICC"), ("paraphrase", "paraphrase"), ("auc", "AUC")):
        s = st[key]
        p(f"  {label:12s} range across runs: {fmt(s['range'])}"
          f"   ({fmt(s['min'])} to {fmt(s['max'])})")
    p("")
    p("  The model is not deterministic. A figure whose run-to-run range is")
    p("  comparable to its bootstrap interval is not stable enough to quote to")
    p("  three decimal places from a single run.")
    p("")

    p("-" * 78)
    p("8. LATENCY")
    p("-" * 78)
    def ms(v: float | None) -> str:
        return "     n/a" if v is None else f"{v:>8.0f}"

    for run in a["latency"]["runs"]:
        for role in ("scorer", "comparator"):
            e = run[role]
            errs = (
                "  errors " + ", ".join(f"{k}={v}" for k, v in e["errors"].items())
                if e.get("errors")
                else ""
            )
            p(f"  {e['model']:24s} mean {ms(e['latency_mean_ms'])} ms  "
              f"P95 {ms(e['latency_p95_ms'])} ms  calls {e['calls']}{errs}")
        p(f"  wall clock for the run   {run['wall_seconds']} s")
        p("")
    p(f"  thesis pipeline budget: {rubric.LATENCY_MEAN_SECONDS} s mean, "
      f"{rubric.LATENCY_P95_SECONDS} s P95")
    p("")
    p("=" * 78)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--items", default=str(HERE / "benchmark.json"))
    args = ap.parse_args()

    load_env()
    payload = json.loads(Path(args.items).read_text("utf-8"))
    items = [Item(**row) for row in payload["items"]]
    print(f"benchmark: {len(items)} items  ({payload['_construction']})\n")

    runs = []
    for i in range(1, args.repeats + 1):
        runs.append(run_once(items, args.workers, i))

    analysis = analyse(runs)
    text = report(analysis)
    print(text)

    RESULTS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (RESULTS / f"benchmark-{stamp}.json").write_text(
        json.dumps({"analysis": analysis, "runs": runs}, indent=2, default=str),
        encoding="utf-8",
    )
    (RESULTS / f"benchmark-{stamp}.txt").write_text(text, encoding="utf-8")
    print(f"\nwritten to eval/results/benchmark-{stamp}.{{json,txt}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
