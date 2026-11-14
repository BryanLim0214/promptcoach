"""Analyses A and B of eval/fluency_detector_protocol.md (fixed before running).

    .venv/Scripts/python -m eval.fluency_detector [--runs 3] [--workers 4]

A  Does the over-reliance sentinel add information beyond the prompt score?
   Re-analysis of eval/results/benchmark-20260906-160831.json; no model calls.
B  Content over fluency: 12 matched fluent / rough-English pairs
   (eval/fluency_pairs.json), scored live by the three-judge Gemini ensemble.

Logistic regression is fitted by Newton-Raphson in pure Python (statsmodels is
not installed in the project venv); the chi-square(1) tail is erfc(sqrt(x/2)).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.benchmark import auc_mann_whitney  # noqa: E402
from promptcoach_ref.engines.base import EngineError, ScoringRequest  # noqa: E402
from promptcoach_ref.framework import rubric, sentinel as sentinel_spec  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SOURCE = RESULTS / "benchmark-20260906-160831.json"
PAIRS = HERE / "fluency_pairs.json"
SEED = 20261024


# ---------------------------------------------------------------------------
# logistic regression
# ---------------------------------------------------------------------------


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        if abs(m[c][c]) < 1e-300:
            raise ZeroDivisionError("singular")
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                for k in range(c, n + 1):
                    m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def _inv(a: list[list[float]]) -> list[list[float]]:
    n = len(a)
    cols = [_solve(a, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def logit_fit(X: list[list[float]], y: list[int], iters: int = 100) -> dict[str, Any]:
    """MLE by Newton-Raphson. X includes the intercept column."""
    k = len(X[0])
    beta = [0.0] * k
    ll_prev = -math.inf
    separated = False
    for it in range(iters):
        eta = [sum(b * x for b, x in zip(beta, row)) for row in X]
        p = [1 / (1 + math.exp(-e)) if e > -700 else 0.0 for e in eta]
        ll = sum(
            yi * math.log(max(pi, 1e-300)) + (1 - yi) * math.log(max(1 - pi, 1e-300))
            for yi, pi in zip(y, p)
        )
        grad = [sum((yi - pi) * row[j] for yi, pi, row in zip(y, p, X)) for j in range(k)]
        H = [
            [sum(pi * (1 - pi) * row[i] * row[j] for pi, row in zip(p, X)) for j in range(k)]
            for i in range(k)
        ]
        try:
            step = _solve(H, grad)
        except ZeroDivisionError:
            separated = True
            break
        beta = [b + s for b, s in zip(beta, step)]
        if abs(ll - ll_prev) < 1e-10:
            break
        ll_prev = ll
    eta = [sum(b * x for b, x in zip(beta, row)) for row in X]
    p = [1 / (1 + math.exp(-e)) if e > -700 else 0.0 for e in eta]
    ll = sum(
        yi * math.log(max(pi, 1e-300)) + (1 - yi) * math.log(max(1 - pi, 1e-300))
        for yi, pi in zip(y, p)
    )
    if max(abs(b) for b in beta) > 30 or min(min(pi, 1 - pi) for pi in p) < 1e-8:
        separated = True
    try:
        H = [
            [sum(pi * (1 - pi) * row[i] * row[j] for pi, row in zip(p, X)) for j in range(k)]
            for i in range(k)
        ]
        cov = _inv(H)
        se = [math.sqrt(cov[i][i]) if cov[i][i] > 0 else None for i in range(k)]
    except ZeroDivisionError:
        se = [None] * k
    pos = [e for e, yi in zip(eta, y) if yi == 1]
    neg = [e for e, yi in zip(eta, y) if yi == 0]
    return {
        "beta": beta,
        "se": se,
        "loglik": ll,
        "auc": auc_mann_whitney(pos, neg),
        "separation_suspected": separated,
        "iterations": it + 1,
    }


def chi2_sf_1df(x: float) -> float:
    return math.erfc(math.sqrt(max(x, 0.0) / 2))


# ---------------------------------------------------------------------------
# Analysis A
# ---------------------------------------------------------------------------


def sentinel_agg(signals: dict[str, float]) -> float | None:
    vals = [v for k, v in signals.items() if k in sentinel_spec.BY_ID]
    return max(vals) if vals else None


def analysis_a() -> dict[str, Any]:
    data = json.loads(SOURCE.read_text("utf-8"))
    rows, dropped = [], 0
    for run in data["runs"]:
        for r in run["rows"]:
            s = sentinel_agg(r.get("signals") or {})
            if r.get("a_overall") is None or s is None:
                dropped += 1
                continue
            rows.append(
                {
                    "id": r["id"],
                    "run": run["run"],
                    "rubric": r["a_overall"],
                    "sentinel": s,
                    "label": 1 if r["risk"] == "high" else 0,
                }
            )

    items: dict[str, dict[str, Any]] = {}
    for r in rows:
        it = items.setdefault(r["id"], {"id": r["id"], "label": r["label"], "r": [], "s": []})
        it["r"].append(r["rubric"])
        it["s"].append(r["sentinel"])
    item_rows = [
        {
            "id": it["id"],
            "label": it["label"],
            "rubric": statistics.fmean(it["r"]),
            "sentinel": statistics.fmean(it["s"]),
            "n_runs": len(it["r"]),
        }
        for it in items.values()
    ]

    def block(rs: list[dict[str, Any]]) -> dict[str, Any]:
        y = [r["label"] for r in rs]
        hi = [r for r in rs if r["label"] == 1]
        lo = [r for r in rs if r["label"] == 0]
        m1 = logit_fit([[1.0, r["rubric"]] for r in rs], y)
        m2 = logit_fit([[1.0, r["rubric"], r["sentinel"]] for r in rs], y)
        lr = 2 * (m2["loglik"] - m1["loglik"])
        return {
            "n": len(rs),
            "n_high": len(hi),
            "n_low": len(lo),
            "auc_sentinel": auc_mann_whitney([r["sentinel"] for r in hi], [r["sentinel"] for r in lo]),
            "auc_lower_rubric": auc_mann_whitney([-r["rubric"] for r in hi], [-r["rubric"] for r in lo]),
            "mean_rubric_high": statistics.fmean(r["rubric"] for r in hi),
            "mean_rubric_low": statistics.fmean(r["rubric"] for r in lo),
            "mean_sentinel_high": statistics.fmean(r["sentinel"] for r in hi),
            "mean_sentinel_low": statistics.fmean(r["sentinel"] for r in lo),
            "M1_rubric_only": m1,
            "M2_rubric_plus_sentinel": m2,
            "lr_stat": lr,
            "lr_df": 1,
            "lr_p": chi2_sf_1df(lr),
        }

    scoring = block(rows)
    item = block(item_rows)
    adds = (
        item["lr_p"] < 0.05
        and item["M2_rubric_plus_sentinel"]["auc"] > item["M1_rubric_only"]["auc"]
    )
    return {
        "source": str(SOURCE.relative_to(HERE.parent)),
        "dropped_scorings": dropped,
        "sentinel_aggregate": "max of the four signals, as eval/benchmark.py",
        "scoring_level": scoring,
        "item_level": item,
        "honest_unit": "item level (n = 30): the 150 scorings are 30 items rescored 5 times",
        "reading": "adds information beyond the prompt score"
        if adds
        else "not shown to add information beyond the prompt score",
        "items": item_rows,
    }


# ---------------------------------------------------------------------------
# Analysis B
# ---------------------------------------------------------------------------


def ensemble_score(engine, stated_intent: str, text: str) -> dict[str, Any] | None:
    req = ScoringRequest(prompt_text=text, stated_intent=stated_intent, task_scenario="")
    samples = []
    for t in (0.2, 0.5, 0.8):
        try:
            s = engine.sample_scores(req, t)
        except EngineError:
            continue
        vals = {
            d.dimension_id: d.value
            for d in s.dimensions
            if d.value is not None and rubric.RUBRIC_MIN <= d.value <= rubric.RUBRIC_MAX
        }
        if vals:
            samples.append(vals)
    if not samples:
        return None
    merged: dict[str, int] = {}
    for dim in rubric.DIMENSIONS:
        vs = [s[dim.id] for s in samples if dim.id in s]
        if vs:
            merged[dim.id] = round(statistics.fmean(vs))
    return {"dims": merged, "overall": statistics.fmean(merged.values()), "n_judges": len(samples)}


def score_pairs(runs: int, workers: int) -> dict[str, Any]:
    pairs = json.loads(PAIRS.read_text("utf-8"))["pairs"]
    mode = "live"
    engine = None
    try:
        from promptcoach_ref.engines.gemini import build

        engine = build("scorer")
        probe = ensemble_score(engine, pairs[0]["stated_intent"], pairs[0]["fluent"])
        if probe is None:
            raise EngineError("live probe returned no valid judge")
    except Exception as exc:  # noqa: BLE001
        print(f"  live scoring unavailable ({exc}); falling back to offline engine")
        from promptcoach_ref.engines.deterministic import DeterministicEngine

        engine = DeterministicEngine()
        mode = "offline"
    model = getattr(engine, "model", "deterministic")
    print(f"  mode={mode} model={model}")

    jobs = [(p, v, r) for r in range(1, runs + 1) for p in pairs for v in ("fluent", "rough")]

    def do(job):
        p, v, r = job
        return {"id": p["id"], "version": v, "run": r,
                "score": ensemble_score(engine, p["stated_intent"], p[v])}

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        raw = list(pool.map(do, jobs))
    wall = time.perf_counter() - started
    stats = engine.stats() if hasattr(engine, "stats") else {}
    return {"mode": mode, "model": model, "runs": runs, "raw": raw,
            "wall_seconds": round(wall, 1), "engine_stats": stats}


def analysis_b(scored: dict[str, Any]) -> dict[str, Any]:
    pairs = json.loads(PAIRS.read_text("utf-8"))["pairs"]
    raw = scored["raw"]
    failed = sum(1 for r in raw if r["score"] is None)
    per_pair = []
    excluded = []
    dim_diffs: dict[str, list[float]] = {d.id: [] for d in rubric.DIMENSIONS}
    for p in pairs:
        v = {}
        dims = {}
        for ver in ("fluent", "rough"):
            ok = [r["score"] for r in raw if r["id"] == p["id"] and r["version"] == ver and r["score"]]
            if not ok:
                break
            v[ver] = [s["overall"] for s in ok]
            dims[ver] = {
                d.id: statistics.fmean(s["dims"][d.id] for s in ok if d.id in s["dims"])
                for d in rubric.DIMENSIONS
                if any(d.id in s["dims"] for s in ok)
            }
        if len(v) < 2:
            excluded.append(p["id"])
            continue
        f, r_ = statistics.fmean(v["fluent"]), statistics.fmean(v["rough"])
        per_pair.append({
            "id": p["id"], "tier": p["tier"],
            "fluent_runs": v["fluent"], "rough_runs": v["rough"],
            "fluent_mean": f, "rough_mean": r_, "diff": f - r_,
        })
        for d in rubric.DIMENSIONS:
            if d.id in dims["fluent"] and d.id in dims["rough"]:
                dim_diffs[d.id].append(dims["fluent"][d.id] - dims["rough"][d.id])

    diffs = [p["diff"] for p in per_pair]
    mean_d = statistics.fmean(diffs)
    sd_d = statistics.stdev(diffs) if len(diffs) > 1 else None
    rng = random.Random(SEED)
    draws = sorted(
        statistics.fmean(diffs[rng.randrange(len(diffs))] for _ in diffs) for _ in range(10_000)
    )
    ci = (draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1])

    by_tier = {
        t: statistics.fmean(p["diff"] for p in per_pair if p["tier"] == t)
        for t in ("weak", "medium", "strong")
        if any(p["tier"] == t for p in per_pair)
    }
    cond1 = mean_d <= 0.25
    cond2 = ci[1] < 0.5
    if scored["mode"] != "live":
        decision = "not evaluated (offline engine; offline results do not count)"
    elif cond1 and cond2:
        decision = "Direct grade supported"
    else:
        decision = "regraded Argued"
    return {
        "mode": scored["mode"],
        "model": scored["model"],
        "runs": scored["runs"],
        "failed_item_runs": failed,
        "excluded_pairs": excluded,
        "n_pairs": len(per_pair),
        "per_pair": per_pair,
        "mean_diff": mean_d,
        "sd_diff": sd_d,
        "bootstrap": {"resamples": 10_000, "seed": SEED, "ci95": ci},
        "mean_diff_by_tier": by_tier,
        "mean_diff_by_dimension": {k: statistics.fmean(v) for k, v in dim_diffs.items() if v},
        "fluent_mean_overall": statistics.fmean(p["fluent_mean"] for p in per_pair),
        "rough_mean_overall": statistics.fmean(p["rough_mean"] for p in per_pair),
        "rule": {"mean_diff_le_0.25": cond1, "ci_upper_lt_0.5": cond2},
        "decision": decision,
        "wall_seconds": scored["wall_seconds"],
        "engine_stats": scored["engine_stats"],
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def f3(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def report(a: dict[str, Any], b: dict[str, Any], stamp: str) -> str:
    L: list[str] = []
    p = L.append
    p(f"# Fluency and detector analyses ({stamp})")
    p("")
    p("Protocol: `eval/fluency_detector_protocol.md`, fixed before running. "
      "Script: `eval/fluency_detector.py`.")
    p("")
    p("## A. Does the sentinel add information beyond the prompt score? (M5)")
    p("")
    p(f"Source: `{a['source']}`; sentinel aggregate = {a['sentinel_aggregate']}; "
      f"dropped scorings: {a['dropped_scorings']}.")
    p("")
    p("| | Scoring level | Item level (primary) |")
    p("|---|---|---|")
    s, i = a["scoring_level"], a["item_level"]
    p(f"| n (high / low) | {s['n']} ({s['n_high']} / {s['n_low']}) | {i['n']} ({i['n_high']} / {i['n_low']}) |")
    p(f"| AUC, sentinel aggregate | {f3(s['auc_sentinel'])} | {f3(i['auc_sentinel'])} |")
    p(f"| AUC, lower rubric score | {f3(s['auc_lower_rubric'])} | {f3(i['auc_lower_rubric'])} |")
    p(f"| Mean rubric, high / low | {f3(s['mean_rubric_high'])} / {f3(s['mean_rubric_low'])} | {f3(i['mean_rubric_high'])} / {f3(i['mean_rubric_low'])} |")
    p(f"| Mean sentinel, high / low | {f3(s['mean_sentinel_high'])} / {f3(s['mean_sentinel_low'])} | {f3(i['mean_sentinel_high'])} / {f3(i['mean_sentinel_low'])} |")
    p(f"| M1 (rubric) AUC | {f3(s['M1_rubric_only']['auc'])} | {f3(i['M1_rubric_only']['auc'])} |")
    p(f"| M2 (rubric + sentinel) AUC | {f3(s['M2_rubric_plus_sentinel']['auc'])} | {f3(i['M2_rubric_plus_sentinel']['auc'])} |")
    p(f"| LR statistic (1 df) | {f3(s['lr_stat'])} | {f3(i['lr_stat'])} |")
    p(f"| LR test p | {s['lr_p']:.2g} | {i['lr_p']:.2g} |")
    for lvl, blk in (("scoring", s), ("item", i)):
        m2 = blk["M2_rubric_plus_sentinel"]
        se = ["n/a" if x is None else f"{x:.3f}" for x in m2["se"]]
        p("")
        p(f"M2 coefficients, {lvl} level: intercept {m2['beta'][0]:.3f} (SE {se[0]}), "
          f"rubric {m2['beta'][1]:.3f} (SE {se[1]}), sentinel {m2['beta'][2]:.3f} (SE {se[2]}). "
          f"Separation suspected: M1 {blk['M1_rubric_only']['separation_suspected']}, "
          f"M2 {m2['separation_suspected']}.")
    p("")
    p(f"Honest unit: {a['honest_unit']}. The scoring-level LR p treats reruns as "
      "independent and is anti-conservative.")
    p("")
    p(f"**Reading (pre-specified rule, item level): {a['reading']}.**")
    p("")
    p("## B. Content over fluency, matched pairs (M6)")
    p("")
    p(f"Mode: **{b['mode']}** ({b['model']}, three-judge ensemble 0.2/0.5/0.8), "
      f"{b['runs']} runs per item; failed item-runs {b['failed_item_runs']}; "
      f"excluded pairs {b['excluded_pairs'] or 'none'}.")
    p("")
    p("| Pair | Tier | Fluent (runs) | Rough (runs) | Fluent mean | Rough mean | Diff |")
    p("|---|---|---|---|---|---|---|")
    for r in b["per_pair"]:
        fr = ", ".join(f"{x:.2f}" for x in r["fluent_runs"])
        rr = ", ".join(f"{x:.2f}" for x in r["rough_runs"])
        p(f"| {r['id']} | {r['tier']} | {fr} | {rr} | {r['fluent_mean']:.3f} | {r['rough_mean']:.3f} | {r['diff']:+.3f} |")
    p("")
    ci = b["bootstrap"]["ci95"]
    p(f"- Mean within-pair difference (fluent minus rough): **{b['mean_diff']:+.3f}** points, "
      f"SD {f3(b['sd_diff'])}, n = {b['n_pairs']} pairs")
    p(f"- 95% percentile bootstrap CI (10,000 resamples of pairs, seed {b['bootstrap']['seed']}): "
      f"**[{ci[0]:+.3f}, {ci[1]:+.3f}]**")
    p(f"- Overall means: fluent {b['fluent_mean_overall']:.3f}, rough {b['rough_mean_overall']:.3f}")
    p("- By tier (descriptive): " + ", ".join(f"{k} {v:+.3f}" for k, v in b["mean_diff_by_tier"].items()))
    p("- By dimension (descriptive): " + ", ".join(f"{k} {v:+.3f}" for k, v in b["mean_diff_by_dimension"].items()))
    p("")
    p(f"Rule: mean diff <= 0.25: {b['rule']['mean_diff_le_0.25']}; "
      f"CI upper < 0.5: {b['rule']['ci_upper_lt_0.5']}.")
    p("")
    p(f"**Decision: {b['decision']}.**")
    p("")
    p("Limits: pairs written by one author (imitated learner English, not learner "
      "English); 12 pairs; one scorer model version; benchmark labels in A written "
      "by the item author. Nothing here is evidence about students.")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    print("Analysis A ...")
    a = analysis_a()
    print("Analysis B: scoring pairs ...")
    scored = score_pairs(args.runs, args.workers)
    b = analysis_b(scored)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"fluency_detector-{stamp}.json").write_text(
        json.dumps({"protocol": "eval/fluency_detector_protocol.md", "A": a, "B": b,
                    "B_raw": scored["raw"]}, indent=2, default=str),
        encoding="utf-8",
    )
    text = report(a, b, stamp)
    (RESULTS / f"fluency_detector-{stamp}.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwritten to eval/results/fluency_detector-{stamp}.{{json,md}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
