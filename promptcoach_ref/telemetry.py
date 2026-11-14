"""Measured numbers, for the researcher view.

Three sources, kept apart because they carry different weight and conflating
them is exactly the error the evidence grades exist to prevent:

  reported   - what Chapter 6 of the thesis states. Point estimates on 30
               items, cross-vendor, no intervals.
  measured   - what the benchmark in this repository produced against Gemini.
               Cross-model-VERSION, not cross-vendor, with item-clustered
               intervals and a run-to-run range.
  live       - what this running process has done since it started.

The frontend renders all three and labels which is which. A chart that plotted
them as one series would be asserting they are the same kind of number.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from .framework import rubric, sentinel

RESULTS = Path(__file__).resolve().parent.parent / "eval" / "results"

#: Landis and Koch's bands, which fig_reliability plots as shaded regions.
#: The thesis's own caution applies: a dimension's placement relative to a
#: threshold "should not be treated as a finding on its own" at n=30.
LANDIS_KOCH = [
    {"from": 0.0, "to": 0.20, "label": "slight"},
    {"from": 0.20, "to": 0.40, "label": "fair"},
    {"from": 0.40, "to": 0.60, "label": "moderate"},
    {"from": 0.60, "to": 0.80, "label": "substantial"},
    {"from": 0.80, "to": 1.00, "label": "almost perfect"},
]


def latest_benchmark() -> dict[str, Any] | None:
    if not RESULTS.exists():
        return None
    files = sorted(RESULTS.glob("benchmark-*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def reported() -> dict[str, Any]:
    """Chapter 6, as transcribed in framework/rubric.py."""
    return {
        "source": "Chapter 6, cross-vendor, n=30, no intervals",
        "overall_icc": rubric.OVERALL_ICC_2_2,
        "mean_grader_gap": rubric.MEAN_GRADER_GAP_POINTS,
        "paraphrase_shift": rubric.PARAPHRASE_MEAN_ABSOLUTE_SHIFT,
        "sentinel_auc": sentinel.AUC,
        "sentinel_agreement": sentinel.CROSS_MODEL_PEARSON,
        "latency_mean_s": rubric.LATENCY_MEAN_SECONDS,
        "latency_p95_s": rubric.LATENCY_P95_SECONDS,
        "dimensions": [
            {
                "id": d.id,
                "name": d.name,
                "kappa": d.weighted_kappa,
                "within_one": d.within_one_pct,
                "kind": d.kind.value,
            }
            for d in rubric.DIMENSIONS
        ],
        "tiers": {"weak": 1.18, "medium": 2.88, "strong": 3.90},
        "caveat": rubric.RELIABILITY_CAVEAT,
    }


def measured() -> dict[str, Any] | None:
    payload = latest_benchmark()
    if not payload:
        return None
    a = payload.get("analysis", {})
    per_dim = a.get("per_dimension", {})
    return {
        "source": (
            f"This repository, {a.get('n_items')} items x {a.get('n_runs')} runs, "
            "cross-model-VERSION within one vendor"
        ),
        "not_cross_vendor": (
            "Both scorers are Google models. Chapter 10 requires two "
            "organisations; this does not supply that."
        ),
        "n_items": a.get("n_items"),
        "n_runs": a.get("n_runs"),
        "overall_icc": a.get("icc"),
        "overall_icc_ci": a.get("icc_ci"),
        "mean_grader_gap": a.get("mean_gap"),
        "mean_grader_gap_ci": a.get("mean_gap_ci"),
        "paraphrase_shift": a.get("paraphrase_shift"),
        "paraphrase_shift_ci": a.get("paraphrase_shift_ci"),
        "sentinel": a.get("sentinel"),
        "tiers": a.get("tiers"),
        "stability": a.get("stability"),
        "per_run": a.get("per_run"),
        "ensemble_spread": a.get("ensemble_spread_mean"),
        "dimensions": [
            {
                "id": dim.id,
                "name": dim.name,
                "kappa": per_dim.get(dim.id, {}).get("kappa"),
                "exact": per_dim.get(dim.id, {}).get("exact"),
                "within_one": per_dim.get(dim.id, {}).get("within_one"),
                "kind": dim.kind.value,
            }
            for dim in rubric.DIMENSIONS
        ],
        "latency": a.get("latency"),
    }


def live(engine: Any) -> dict[str, Any]:
    """What this process has actually done. Empty until something runs."""
    stats = engine.stats() if hasattr(engine, "stats") else {}
    latencies = list(getattr(engine, "latencies_ms", []) or [])
    out: dict[str, Any] = {
        "engine": getattr(engine, "name", "unknown"),
        "organisation": getattr(engine, "organisation", "unknown"),
        "calls": stats.get("calls", 0),
        "errors": stats.get("errors", {}),
        "input_tokens": stats.get("input_tokens", 0),
        "output_tokens": stats.get("output_tokens", 0),
        "latency_mean_ms": stats.get("latency_mean_ms"),
        "latency_p95_ms": stats.get("latency_p95_ms"),
        "latency_max_ms": stats.get("latency_max_ms"),
        "latencies_ms": latencies[-200:],
    }
    if latencies:
        out["latency_median_ms"] = round(statistics.median(latencies), 1)
    return out


def budget() -> dict[str, Any]:
    """Chapter 12's ecological threat, as a number a chart can draw."""
    return {
        "pipeline_mean_s": rubric.LATENCY_MEAN_SECONDS,
        "pipeline_p95_s": rubric.LATENCY_P95_SECONDS,
        "reference_s": 3.0,
        "note": (
            "Chapter 12 records latency as an ecological threat: it is paid on "
            "every attempt, after the student has already spent time speaking, "
            "and may exceed middle school patience."
        ),
    }


def payload(engine: Any) -> dict[str, Any]:
    return {
        "reported": reported(),
        "measured": measured(),
        "live": live(engine),
        "budget": budget(),
        "landis_koch": LANDIS_KOCH,
    }
