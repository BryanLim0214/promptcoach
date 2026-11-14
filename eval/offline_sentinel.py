"""Benchmark the offline keyword over-reliance rules against the risk labels.

    .venv/Scripts/python -m eval.offline_sentinel

PROTOCOL (fixed 2026-11-14, before the first run; nothing below changes after it):
- Items: the 30 replication items in eval/benchmark.json, with their author-set risk
  labels (9 high, 21 low). Retry items submit their history exactly as benchmark.py does.
- Detector: DeterministicEngine.sentinel, the four fixed text rules, unchanged.
- Score per item: the highest of the four signals, as for the live detector
  (benchmark.py, section 5) and the policy "the highest is reported".
- Measures: AUC as Mann-Whitney U / (n1 n2), ties counted as one half (eval.benchmark.
  auc_mann_whitney); a 95% percentile bootstrap over items (2,000 resamples, seed 20261114,
  resampling within each label group); per-signal AUC; mean score on low-risk items.
- The rules are deterministic, so there is one run. The rules are NOT tuned on these items:
  whatever the AUC is, it is reported as is.
Results go to eval/results/offline_sentinel-<timestamp>.json and .md.
"""

from __future__ import annotations

import json
import random
import statistics
from datetime import datetime
from pathlib import Path

from promptcoach_ref.engines import DeterministicEngine
from promptcoach_ref.framework import sentinel as spec

from .benchmark import auc_mann_whitney

HERE = Path(__file__).resolve().parent
SEED, RESAMPLES = 20261114, 2000


def main() -> dict:
    items = json.loads((HERE / "benchmark.json").read_text(encoding="utf-8"))["items"]
    eng = DeterministicEngine()
    rows = []
    for it in items:
        sig = eng.sentinel(it["stated_intent"], it["prompt_text"], tuple(it.get("history") or ()))
        vals = {k: v for k, v in sig.items() if k in spec.BY_ID}
        rows.append({"id": it["id"], "risk": it["risk"], "tier": it["tier"], "signals": vals, "max": max(vals.values())})
    hi = [r["max"] for r in rows if r["risk"] == "high"]
    lo = [r["max"] for r in rows if r["risk"] == "low"]
    auc = auc_mann_whitney(hi, lo)
    rng = random.Random(SEED)
    boots = sorted(
        auc_mann_whitney([rng.choice(hi) for _ in hi], [rng.choice(lo) for _ in lo])
        for _ in range(RESAMPLES)
    )
    ci = (boots[int(0.025 * RESAMPLES)], boots[int(0.975 * RESAMPLES) - 1])
    per_signal = {
        s.id: auc_mann_whitney([r["signals"][s.id] for r in rows if r["risk"] == "high"],
                               [r["signals"][s.id] for r in rows if r["risk"] == "low"])
        for s in spec.SIGNALS
    }
    out = {
        "protocol": __doc__,
        "n_high": len(hi), "n_low": len(lo),
        "auc": auc, "ci95": ci,
        "low_risk_mean": statistics.mean(lo), "high_risk_mean": statistics.mean(hi),
        "low_risk_nonzero": sum(v > 0 for v in lo),
        "high_risk_zero": sum(v == 0 for v in hi),
        "per_signal_auc": per_signal,
        "live_detector_for_comparison": {"proem_auc": spec.AUC, "replication_pooled_auc": spec.REPLICATION_AUC_POOLED},
        "rows": rows,
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (HERE / "results" / f"offline_sentinel-{stamp}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = [
        "# Offline keyword over-reliance rules against the risk labels",
        "",
        f"Items: {len(hi)} high-risk, {len(lo)} low-risk (author labels). One deterministic run.",
        f"AUC (highest signal per item): {auc:.3f}  (95% bootstrap {ci[0]:.3f} to {ci[1]:.3f})",
        f"Mean score: high-risk {out['high_risk_mean']:.3f}, low-risk {out['low_risk_mean']:.3f}",
        f"Low-risk items with any signal: {out['low_risk_nonzero']} of {len(lo)}; high-risk items with none: {out['high_risk_zero']} of {len(hi)}",
        "Per-signal AUC: " + ", ".join(f"{k} {v:.3f}" for k, v in per_signal.items()),
        f"For comparison, the model-based detector: {spec.AUC} (Proem, one run), {spec.REPLICATION_AUC_POOLED} (replication, pooled).",
        "",
        "The rules were not changed before or after this run.",
    ]
    (HERE / "results" / f"offline_sentinel-{stamp}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return out


if __name__ == "__main__":
    main()
