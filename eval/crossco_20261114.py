"""Two-company grader check on the replication's 30 items (Google grader A vs OpenAI grader B).

    .venv/Scripts/python -m eval.crossco_20261114 --dry-run   # gate + offline reference only, no API call
    .venv/Scripts/python -m eval.crossco_20261114             # the run

PROTOCOL (written 2026-11-14, before this script made any API call; not changed after)
======================================================================================

Why
---
The thesis trusts a score only when graders built by two different companies agree
on it. Build 1 met this (Gemini 3.1 Flash-Lite vs gpt-5.4-mini, ICC(2,2) 0.976, 30
author-written items). The 5-run replication (eval/results/benchmark-20260906-160831.json)
paired its Gemini grader A with a second GOOGLE model (gemini-3.8-flash), so on the
replication's items the two-company check was not met. This script runs it.

Items and inputs
----------------
* The same 30 items, eval/benchmark.json, loaded as eval.benchmark.Item exactly as the
  replication loaded them.
* Inputs given to grader B are exactly what the replication gave its graders: the
  user message built by GeminiEngine.sample_scores from `stated_intent` and
  `prompt_text`. The replication did not pass `history` (or `paraphrase`) to the
  scoring call - history went only to the sentinel - so it is not passed here either.

Grader A (no new Gemini call)
-----------------------------
The stored replication grader-A scores: per run and item, `rows[*].a` (per-dimension,
the 3-temperature ensemble mean rounded to an integer) and `rows[*].a_overall` (their
mean), model gemini-3.1-flash-lite. Replication run i is paired with OpenAI run i.

Grader B (only the model changes)
---------------------------------
* Scoring instruction: promptcoach_ref.engines.gemini.SCORE_SYSTEM, byte-identical
  (the replication's grader B, gemini-3.8-flash, used GeminiEngine and this prompt).
* Call path: eval.benchmark.score_once on a subclass of GeminiEngine whose ONLY
  override is the `_json` transport (and its name/organisation labels). So the user
  message, the response parsing (unknown dimensions dropped, missing -> None) and the
  score_once rules (None skipped, values outside 1..4 discarded never clamped, an
  empty result = unscored) are the replication's own code, not a copy of it.
* Output schema: gemini.SCORE_SCHEMA, same properties, types, enum and required
  lists. OpenAI's strict json_schema mode requires `additionalProperties: false` on
  every object; that is added and is the only schema change (Gemini's responseSchema
  already admits no extra keys). Sent as response_format json_schema, strict true.
* Endpoint POST https://api.openai.com/v1/chat/completions; messages = [system:
  SCORE_SYSTEM, user: the replication's user message]. No max-token cap and no
  reasoning-effort parameter are sent (API defaults). The replication's Gemini call
  set maxOutputTokens 2048; it is not copied because for OpenAI reasoning models the
  cap would also cover hidden reasoning tokens and so would not mean the same thing.
* Temperature: 0.2 (the replication's grader-B temperature and Build 1's). The very
  first call for each model is made alone, before any parallel call. If the API
  rejects it with HTTP 400 naming `temperature`, the model is run at the API default
  for every call and the rejection is recorded; that rejected request does not count
  as an attempt. Nothing else is changed in response to an error.
* Model ids are checked with GET /v1/models/{id} first. A missing id aborts the run;
  no other model is substituted. The snapshot id each response reports is recorded.
* Primary grader B: gpt-5.4-mini (Build 1's OpenAI grader), 5 runs x 30 items.
  Secondary grader B: gpt-5.5, 1 run x 30 items, paired with replication run 1. The
  secondary is a sensitivity check and is never reported instead of the primary.
  About 180 calls in total.

Failures
--------
A call that errors or yields no usable score (score_once returns None) is retried at
most twice (3 attempts per cell, 2 s then 4 s pause between attempts). A cell still
unscored after that is recorded and excluded from that pairing only; counts are
reported. A partially scored cell is kept as the replication kept it (overall = mean
of the dimensions present) and the number of missing dimension values is reported.

Measures (for each pairing: primary pooled over 5 runs, secondary 1 run)
-------------------------------------------------------------------------
* Overall ICC(2,2), absolute agreement: eval.benchmark.icc_2_2 on (a_overall,
  b_overall), all paired cells pooled - the replication's computation.
* Mean absolute grader gap |a_overall - b_overall|; mean signed gap (A - B) also shown.
* Per dimension: weighted kappa under BOTH linear (|i-j|/3) and quadratic ((i-j)^2/9)
  weights (eval.reanalysis_20261114.weighted_kappa; linear equals
  eval.benchmark.weighted_kappa), exact agreement %, within-one %, n.
* Lowest dimension = smallest kappa, under each weighting; ties reported as ties.
* 95% percentile intervals from an item bootstrap: 4000 resamples of the 30 items,
  drawn once per pairing from a fresh random.Random(20261114) (so every pairing and
  every statistic uses the same 4000 index sets); all runs of a resampled item travel
  together; a draw where a statistic is undefined is dropped and valid draws are
  counted. Interval indices from eval.benchmark._percentiles.
* Primary per-run overall ICC (and per-run lowest dimension), and its range.
* Reference row (no API call): the stored Google-only pairing (grader B
  gemini-3.8-flash) recomputed with this same code and the same resamples, so the
  two-company result is compared like for like. Its published figures (0.973
  [0.936, 0.990], seed 20260906; Iteration Awareness linear kappa 0.404) are quoted
  as published.

Gate (before any API call; on failure the script stops without calling anything)
--------------------------------------------------------------------------------
From the stored replication data this code must reproduce: pooled ICC equal to the
stored analysis value (to 1e-12) and 0.973 at 3 decimals; pooled Iteration Awareness
linear kappa 0.404; each stored per-run ICC; 150 grader-A cells with all six
dimensions.

Fixed in advance
----------------
Nothing is tuned and nothing is changed after seeing results; whatever comes out is
reported. What this is: agreement between AI graders from two companies on
author-written items. It is not agreement with teachers, and the intervals cover
item sampling only (not prompt-version, model-version or population variance).
The API key is read from .env and never printed, logged or written.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.benchmark import Item, _percentiles, icc_2_2, score_once  # noqa: E402
from eval.benchmark import weighted_kappa as linear_kappa_helper  # noqa: E402
from eval.reanalysis_20261114 import resamples, weighted_kappa  # noqa: E402
from promptcoach_ref.engines.base import EngineError  # noqa: E402
from promptcoach_ref.engines.gemini import (  # noqa: E402
    SCORE_SCHEMA,
    SCORE_SYSTEM,
    GeminiEngine,
    load_env,
)
from promptcoach_ref.framework import rubric  # noqa: E402

SEED = 20261114
REPS = 4000
ALPHA = 0.05
TEMPERATURE = 0.2
PRIMARY = "gpt-5.4-mini"
PRIMARY_RUNS = 5
SECONDARY = "gpt-5.5"
SECONDARY_RUNS = 1
MAX_ATTEMPTS = 3  # initial call + at most two retries
WORKERS = 6
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models/"

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
REPLICATION = RESULTS / "benchmark-20260906-160831.json"
ITEMS = HERE / "benchmark.json"
OUT_JSON = RESULTS / "crossco_20261114.json"
OUT_MD = RESULTS / "crossco_20261114.md"

DIMS = [(d.id, d.name) for d in rubric.DIMENSIONS]
NAME = dict(DIMS)
BUILD1_QUADRATIC_KAPPA = {d.id: d.weighted_kappa for d in rubric.DIMENSIONS}


# ---------------------------------------------------------------------------
# key hygiene
# ---------------------------------------------------------------------------

_KEY: str | None = None


def redact(text: str) -> str:
    """Strip anything key-like from a string before it is stored or shown."""
    if _KEY:
        text = text.replace(_KEY, "[redacted]")
    return re.sub(r"sk-[A-Za-z0-9_\-\*]{4,}", "sk-[redacted]", text)


# ---------------------------------------------------------------------------
# grader B: GeminiEngine with only the transport replaced
# ---------------------------------------------------------------------------


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """gemini.SCORE_SCHEMA plus additionalProperties:false on every object (OpenAI strict mode)."""
    out = copy.deepcopy(schema)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(out)
    return out


class OpenAIGrader(GeminiEngine):
    """Replication grader B with the transport pointed at OpenAI. Prompt, user message
    and parsing are inherited unchanged from GeminiEngine."""

    def __post_init__(self) -> None:  # noqa: D401
        super().__post_init__()
        self.name = f"openai:{self.model}"
        self.organisation = "openai"
        self.send_temperature = True
        self.temperature_rejection: str | None = None
        self.call_log: list[dict[str, Any]] = []
        self._local = threading.local()
        self._lock = threading.Lock()

    def set_cell(self, tag: dict[str, Any]) -> None:
        self._local.cell = tag

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        return self._client.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=body,
        )

    def _json(self, system: str, user: str, temperature: float, schema: dict) -> dict:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "rubric_scores", "strict": True, "schema": strict_schema(schema)},
            },
        }
        if self.send_temperature:
            body["temperature"] = temperature
        entry: dict[str, Any] = dict(getattr(self._local, "cell", {}) or {})
        entry["temperature_sent"] = body.get("temperature")
        started = time.perf_counter()
        try:
            response = self._post(body)
            # Temperature capability rule (protocol): a 400 naming temperature switches the
            # model to the API default for every call; the rejected request is not an attempt.
            if (
                response.status_code == 400
                and "temperature" in body
                and "temperature" in response.text.lower()
            ):
                with self._lock:
                    if self.send_temperature:
                        self.send_temperature = False
                        self.temperature_rejection = redact(response.text[:500])
                body.pop("temperature", None)
                entry["temperature_sent"] = None
                entry["temperature_rejected_first"] = True
                started = time.perf_counter()
                response = self._post(body)
        except httpx.HTTPError as exc:
            self._note("transport")
            entry.update(ok=False, error=redact(f"transport failure: {exc}"))
            self.call_log.append(entry)
            raise EngineError(entry["error"]) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        entry["latency_ms"] = round(elapsed_ms, 1)

        if response.status_code >= 400:
            self._note(f"http_{response.status_code}")
            entry.update(ok=False, error=redact(f"HTTP {response.status_code}: {response.text[:400]}"))
            self.call_log.append(entry)
            raise EngineError(entry["error"])

        data = response.json()
        usage = data.get("usage") or {}
        with self._lock:
            self.calls += 1
            self.input_tokens += usage.get("prompt_tokens", 0) or 0
            self.output_tokens += usage.get("completion_tokens", 0) or 0
            self.latencies_ms.append(elapsed_ms)
        entry.update(
            response_model=data.get("model"),
            system_fingerprint=data.get("system_fingerprint"),
            usage=usage,
        )
        try:
            choice = data["choices"][0]
            content = choice["message"].get("content")
            entry["finish_reason"] = choice.get("finish_reason")
            if choice["message"].get("refusal"):
                entry["refusal"] = redact(str(choice["message"]["refusal"]))
        except (KeyError, IndexError) as exc:
            self._note("bad_shape")
            entry.update(ok=False, error="unexpected response shape")
            self.call_log.append(entry)
            raise EngineError("unexpected response shape") from exc
        entry["content"] = content
        if not content:
            self._note(f"no_content_{entry.get('finish_reason')}")
            entry.update(ok=False, error=f"no content (finish_reason={entry.get('finish_reason')})")
            self.call_log.append(entry)
            raise EngineError(entry["error"])
        try:
            parsed = json.loads(content)
        except ValueError as exc:
            self._note("invalid_json")
            entry.update(ok=False, error="model returned invalid JSON")
            self.call_log.append(entry)
            raise EngineError("model returned invalid JSON") from exc
        entry["ok"] = True
        self.call_log.append(entry)
        return parsed


def verify_model(client: httpx.Client, key: str, model: str) -> dict[str, Any]:
    r = client.get(OPENAI_MODELS_URL + model, headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        return {"model": model, "found": False, "status": r.status_code, "detail": redact(r.text[:300])}
    j = r.json()
    return {"model": model, "found": True, "id": j.get("id"), "owned_by": j.get("owned_by")}


def score_cell(engine: OpenAIGrader, item: Item, run: int) -> dict[str, Any]:
    attempts = 0
    result = None
    for attempt in range(MAX_ATTEMPTS):
        attempts += 1
        engine.set_cell({"id": item.id, "run": run, "attempt": attempt + 1})
        result = score_once(engine, item, item.prompt_text, TEMPERATURE)
        if result:
            break
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(2.0 * (2 ** attempt))
    return {
        "id": item.id,
        "run": run,
        "attempts": attempts,
        "b": result,
        "b_overall": statistics.fmean(result.values()) if result else None,
    }


def run_model(model: str, n_runs: int, items: list[Item], key: str) -> dict[str, Any]:
    engine = OpenAIGrader(model=model, api_key=key, timeout=120.0)
    cells: list[tuple[Item, int]] = [(it, r) for r in range(1, n_runs + 1) for it in items]
    started = time.perf_counter()
    # first call alone, so the temperature rule is settled before anything runs in parallel
    first = score_cell(engine, *cells[0])
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rest = list(pool.map(lambda c: score_cell(engine, *c), cells[1:]))
    wall = time.perf_counter() - started
    out_cells = [first] + rest
    snapshots = sorted({c.get("response_model") for c in engine.call_log if c.get("response_model")})
    return {
        "model_requested": model,
        "response_models": snapshots,
        "temperature_requested": TEMPERATURE,
        "temperature_used": TEMPERATURE if engine.send_temperature else "API default (temperature rejected)",
        "temperature_rejection": engine.temperature_rejection,
        "runs": n_runs,
        "cells": out_cells,
        "calls_log": engine.call_log,
        "stats": engine.stats(),
        "wall_seconds": round(wall, 1),
    }


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------


def interval(draws: list[float | None]) -> dict[str, Any]:
    valid = [d for d in draws if d is not None]
    ci = _percentiles(list(valid), ALPHA)
    return {"lo": ci[0] if ci else None, "hi": ci[1] if ci else None, "valid_draws": len(valid)}


def paired(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("b") and r.get("a_overall") is not None and r.get("b_overall") is not None]


def stat_icc(rows):
    p = paired(rows)
    return icc_2_2([(r["a_overall"], r["b_overall"]) for r in p]) if p else None


def stat_gap(rows):
    p = paired(rows)
    return statistics.fmean(abs(r["a_overall"] - r["b_overall"]) for r in p) if p else None


def stat_signed(rows):
    p = paired(rows)
    return statistics.fmean(r["a_overall"] - r["b_overall"] for r in p) if p else None


def dim_pairs(rows, dim):
    xs, ys = [], []
    for r in rows:
        if dim in r["a"] and r.get("b") and dim in r["b"]:
            xs.append(r["a"][dim])
            ys.append(r["b"][dim])
    return xs, ys


def stat_kappa(rows, dim, w):
    xs, ys = dim_pairs(rows, dim)
    return weighted_kappa(xs, ys, w)


def stat_exact(rows, dim):
    xs, ys = dim_pairs(rows, dim)
    return sum(x == y for x, y in zip(xs, ys)) / len(xs) if xs else None


def stat_within1(rows, dim):
    xs, ys = dim_pairs(rows, dim)
    return sum(abs(x - y) <= 1 for x, y in zip(xs, ys)) / len(xs) if xs else None


def lowest(values: dict[str, float | None]) -> list[str]:
    defined = {k: v for k, v in values.items() if v is not None}
    if not defined:
        return []
    m = min(defined.values())
    return [k for k, v in defined.items() if abs(v - m) < 1e-12]


def analyse_pairing(rows: list[dict[str, Any]], item_ids: list[str]) -> dict[str, Any]:
    clusters = [[r for r in rows if r["id"] == i] for i in item_ids]
    idx_sets = resamples(len(item_ids))  # fresh random.Random(SEED) each pairing

    def boot(fn: Callable) -> dict[str, Any]:
        draws = []
        for idx in idx_sets:
            sample = [r for i in idx for r in clusters[i]]
            draws.append(fn(sample))
        return interval(draws)

    def est(fn: Callable) -> dict[str, Any]:
        return {"value": fn(rows), **boot(fn)}

    out: dict[str, Any] = {
        "n_cells": len(rows),
        "n_paired": len(paired(rows)),
        "n_items": len(item_ids),
        "icc_2_2": est(stat_icc),
        "mean_abs_gap": est(stat_gap),
        "mean_signed_gap_a_minus_b": est(stat_signed),
        "per_dimension": {},
    }
    for d, _ in DIMS:
        xs, _ = dim_pairs(rows, d)
        out["per_dimension"][d] = {
            "n": len(xs),
            "kappa_linear": est(lambda rs, d=d: stat_kappa(rs, d, "linear")),
            "kappa_quadratic": est(lambda rs, d=d: stat_kappa(rs, d, "quadratic")),
            "exact": est(lambda rs, d=d: stat_exact(rs, d)),
            "within_one": est(lambda rs, d=d: stat_within1(rs, d)),
        }
    for w in ("linear", "quadratic"):
        ks = {d: out["per_dimension"][d][f"kappa_{w}"]["value"] for d, _ in DIMS}
        out[f"lowest_{w}"] = lowest(ks)
        out[f"ranking_low_to_high_{w}"] = sorted((d for d in ks if ks[d] is not None), key=lambda d: ks[d])
    return out


def per_run(rows: list[dict[str, Any]], runs: list[int]) -> dict[str, Any]:
    entries = []
    for run in runs:
        rs = [r for r in rows if r["run"] == run]
        e = {"run": run, "n_paired": len(paired(rs)), "icc_2_2": stat_icc(rs), "mean_abs_gap": stat_gap(rs)}
        for w in ("linear", "quadratic"):
            e[f"lowest_{w}"] = lowest({d: stat_kappa(rs, d, w) for d, _ in DIMS})
        entries.append(e)
    iccs = [e["icc_2_2"] for e in entries if e["icc_2_2"] is not None]
    return {
        "runs": entries,
        "icc_min": min(iccs) if iccs else None,
        "icc_max": max(iccs) if iccs else None,
        "icc_range": (max(iccs) - min(iccs)) if iccs else None,
    }


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------


def load_replication() -> dict[str, Any]:
    return json.loads(REPLICATION.read_text(encoding="utf-8"))


def grader_a_rows(rep: dict[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    out = {}
    for run in rep["runs"]:
        for r in run["rows"]:
            out[(run["run"], r["id"])] = {"a": r["a"], "a_overall": r["a_overall"]}
    return out


def reference_rows(rep: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": r["id"], "run": run["run"], "a": r["a"], "a_overall": r["a_overall"],
         "b": r.get("b"), "b_overall": r.get("b_overall")}
        for run in rep["runs"] for r in run["rows"]
    ]


def gate(rep: dict[str, Any]) -> dict[str, Any]:
    rows = reference_rows(rep)
    stored = rep["analysis"]
    icc = stat_icc(rows)
    ia = stat_kappa(rows, "iteration_awareness", "linear")
    for d, _ in DIMS:
        xs, ys = dim_pairs(rows, d)
        assert abs(weighted_kappa(xs, ys, "linear") - linear_kappa_helper(xs, ys)) < 1e-12
    run_checks = []
    for pr in stored["per_run"]:
        rs = [r for r in rows if r["run"] == pr["run"]]
        v = stat_icc(rs)
        run_checks.append({"run": pr["run"], "stored": pr["icc"], "recomputed": v,
                           "pass": v is not None and abs(v - pr["icc"]) < 1e-12})
    checks = {
        "pooled_icc_equals_stored": abs(icc - stored["icc"]) < 1e-12,
        "pooled_icc_rounds_to_0.973": round(icc, 3) == 0.973,
        "ia_linear_kappa_rounds_to_0.404": round(ia, 3) == 0.404,
        "per_run_icc_equal_stored": all(c["pass"] for c in run_checks),
        "grader_a_150_cells_all_six_dims": len(rows) == 150 and all(len(r["a"]) == 6 for r in rows),
        "grader_a_models": sorted({run["scorer"]["model"] for run in rep["runs"]}),
        "replication_grader_b_models": sorted({run["comparator"]["model"] for run in rep["runs"]}),
    }
    ok = all(v for k, v in checks.items() if isinstance(v, bool))
    return {"pass": ok, "checks": checks, "per_run": run_checks, "pooled_icc": icc, "ia_linear_kappa": ia}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def ci(e: dict[str, Any], places: int = 3, pct: bool = False) -> str:
    v = e["value"]
    if v is None:
        return "n/a"
    f = (lambda x: f"{100 * x:.1f}%") if pct else (lambda x: f"{x:.{places}f}")
    if e["lo"] is None:
        return f"{f(v)} [n/a]"
    return f"{f(v)} [{f(e['lo'])}, {f(e['hi'])}]"


def render_md(o: dict[str, Any]) -> str:
    L: list[str] = []
    p = L.append
    p("# Two-company grader check, 2026-11-14")
    p("")
    p("Agreement between AI graders from two companies (Google grader A, OpenAI grader B) on the "
      "replication's 30 author-written items. **Not agreement with teachers.** Intervals: 95% percentile, "
      f"item bootstrap, {REPS} resamples, seed {SEED}, all runs of an item resampled together; they cover "
      "item sampling only.")
    p("")
    p("Script: `eval/crossco_20261114.py` (protocol in its docstring, fixed before any API call).")
    p("")
    p("## Setup")
    p("")
    p(f"- Grader A: stored replication scores, {', '.join(o['gate']['checks']['grader_a_models'])} "
      "(3-temperature ensemble, rounded mean), no new calls. Replication run i paired with OpenAI run i.")
    p("- Grader B instruction: `promptcoach_ref.engines.gemini.SCORE_SYSTEM` (identical to the replication's "
      "grader B); inputs `stated_intent` + `prompt_text`; replication parser (`eval.benchmark.score_once`).")
    for key in ("primary", "secondary"):
        m = o["models"][key]
        p(f"- {key.capitalize()} grader B: requested `{m['model_requested']}`; response model(s) "
          f"{', '.join('`' + s + '`' for s in m['response_models']) or 'n/a'}; temperature used: "
          f"{m['temperature_used']}; runs {m['runs']}; API calls {m['stats']['calls']} "
          f"(HTTP/parse errors {m['stats']['errors'] or 'none'}).")
        if m["temperature_rejection"]:
            p(f"  - temperature rejection message: `{m['temperature_rejection'][:200]}`")
    p("")
    p("## Gate (stored replication data, before any API call)")
    p("")
    p(f"Gate: **{'PASS' if o['gate']['pass'] else 'FAIL'}**. Pooled Google-only ICC recomputed "
      f"{o['gate']['pooled_icc']:.4f}; Iteration Awareness linear kappa {o['gate']['ia_linear_kappa']:.4f}.")
    p("")
    p("## Overall agreement")
    p("")
    p("| Pairing | Cells paired | ICC(2,2) | Mean abs gap | Mean signed gap (A-B) |")
    p("|---|---|---|---|---|")
    for key, label in (("primary", f"A vs {o['models']['primary']['model_requested']} (5 runs pooled)"),
                       ("secondary", f"A vs {o['models']['secondary']['model_requested']} (run 1)"),
                       ("reference_google", "Reference: A vs gemini-3.8-flash (stored, 5 runs)")):
        a = o["analysis"][key]
        p(f"| {label} | {a['n_paired']} | {ci(a['icc_2_2'])} | {ci(a['mean_abs_gap'])} | "
          f"{ci(a['mean_signed_gap_a_minus_b'])} |")
    p("")
    pr = o["analysis"]["primary_per_run"]
    p("Primary per-run ICC(2,2): " + ", ".join(
        f"run {e['run']} {e['icc_2_2']:.3f}" if e["icc_2_2"] is not None else f"run {e['run']} n/a"
        for e in pr["runs"]))
    if pr["icc_min"] is not None:
        p(f"(range {pr['icc_min']:.3f} to {pr['icc_max']:.3f}, spread {pr['icc_range']:.3f}).")
    p("")
    for key in ("primary", "secondary", "reference_google"):
        a = o["analysis"][key]
        p(f"## Per dimension: {key}")
        p("")
        p("| Dimension | n | kappa linear | kappa quadratic | exact | within one |")
        p("|---|---|---|---|---|---|")
        for d, name in DIMS:
            e = a["per_dimension"][d]
            p(f"| {name} | {e['n']} | {ci(e['kappa_linear'])} | {ci(e['kappa_quadratic'])} | "
              f"{ci(e['exact'], pct=True)} | {ci(e['within_one'], pct=True)} |")
        p("")
        p(f"Lowest (linear): {', '.join(NAME[d] for d in a['lowest_linear'])}; "
          f"lowest (quadratic): {', '.join(NAME[d] for d in a['lowest_quadratic'])}.")
        p("")
    p("Primary per-run lowest dimension: " + "; ".join(
        f"run {e['run']} linear {', '.join(NAME[d] for d in e['lowest_linear'])} / quadratic "
        f"{', '.join(NAME[d] for d in e['lowest_quadratic'])}" for e in pr["runs"]) + ".")
    p("")
    p("## Comparison points (quoted, not recomputed here)")
    p("")
    p("- Build 1 (Gemini 3.1 Flash-Lite vs gpt-5.4-mini, 30 items, 1 run): ICC(2,2) 0.976; kappas are "
      "**quadratic**-weighted: " + ", ".join(f"{NAME[d]} {v:.3f}" for d, v in BUILD1_QUADRATIC_KAPPA.items()) + ".")
    p("- Replication (Google-only, 5 runs): ICC(2,2) 0.973 [0.936, 0.990] (seed 20260906); kappas are "
      "**linear**-weighted; Iteration Awareness 0.404 lowest.")
    p("")
    p("## Failures")
    p("")
    for key in ("primary", "secondary"):
        f = o["failures"][key]
        p(f"- {key}: {f['cells_total']} cells; unscored after 3 attempts {f['unscored']} "
          f"{f['unscored_cells'] or ''}; cells needing a retry {f['retried']}; "
          f"missing dimension values in scored cells {f['missing_dimension_values']}.")
    p("")
    p("## Caveats")
    for c in o["caveats"]:
        p(f"- {c}")
    p("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def failures(cells: list[dict[str, Any]]) -> dict[str, Any]:
    uns = [f"{c['id']}/run{c['run']}" for c in cells if not c["b"]]
    return {
        "cells_total": len(cells),
        "unscored": len(uns),
        "unscored_cells": uns,
        "retried": sum(1 for c in cells if c["attempts"] > 1),
        "missing_dimension_values": sum(6 - len(c["b"]) for c in cells if c["b"]),
    }


def main() -> int:
    global _KEY
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="gate + offline reference only; no API call")
    args = ap.parse_args()

    rep = load_replication()
    g = gate(rep)
    print(f"gate: {'PASS' if g['pass'] else 'FAIL'}  pooled ICC {g['pooled_icc']:.4f}  IA linear {g['ia_linear_kappa']:.4f}")
    if not g["pass"]:
        print(json.dumps(g, indent=2, default=str))
        return 1

    payload = json.loads(ITEMS.read_text("utf-8"))
    items = [Item(**row) for row in payload["items"]]
    item_ids = sorted(it.id for it in items)
    ref = analyse_pairing(reference_rows(rep), item_ids)
    if args.dry_run:
        print("dry run: reference (Google-only) ICC", ci(ref["icc_2_2"]),
              "IA linear", ci(ref["per_dimension"]["iteration_awareness"]["kappa_linear"]))
        return 0

    load_env()
    _KEY = os.environ.get("OPENAI_API_KEY")
    if not _KEY:
        print("OPENAI_API_KEY is not set in .env")
        return 1

    with httpx.Client(timeout=30.0) as c:
        checks = [verify_model(c, _KEY, m) for m in (PRIMARY, SECONDARY)]
    print("model check:", json.dumps(checks))
    if not all(x["found"] for x in checks):
        print("a requested model id was not found; aborting without substitution")
        return 1

    a_rows = grader_a_rows(rep)
    models: dict[str, Any] = {}
    for key, model, n in (("primary", PRIMARY, PRIMARY_RUNS), ("secondary", SECONDARY, SECONDARY_RUNS)):
        print(f"scoring {model}: {n} run(s) x {len(items)} items")
        models[key] = run_model(model, n, items, _KEY)
        print(f"  done in {models[key]['wall_seconds']} s; temperature used: {models[key]['temperature_used']}")

    def join(cells):
        return [{**c, **a_rows[(c["run"], c["id"])]} for c in cells]

    prim_rows = join(models["primary"]["cells"])
    sec_rows = join(models["secondary"]["cells"])
    out: dict[str, Any] = {
        "protocol": "see module docstring of eval/crossco_20261114.py (fixed before any API call)",
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seed": SEED,
        "bootstrap_resamples": REPS,
        "interval": "percentile 95%, item-level resampling, all runs of an item together",
        "inputs": {
            "replication": {"path": str(REPLICATION), "sha256": sha256(REPLICATION)},
            "items": {"path": str(ITEMS), "sha256": sha256(ITEMS)},
            "score_system_sha256": hashlib.sha256(SCORE_SYSTEM.encode("utf-8")).hexdigest(),
            "score_system": SCORE_SYSTEM,
            "schema_sent": strict_schema(SCORE_SCHEMA),
        },
        "gate": g,
        "model_check": checks,
        "models": {k: {kk: vv for kk, vv in v.items() if kk not in ("cells", "calls_log")} for k, v in models.items()},
        "analysis": {
            "primary": analyse_pairing(prim_rows, item_ids),
            "primary_per_run": per_run(prim_rows, list(range(1, PRIMARY_RUNS + 1))),
            "secondary": analyse_pairing(sec_rows, item_ids),
            "reference_google": ref,
        },
        "failures": {"primary": failures(models["primary"]["cells"]),
                     "secondary": failures(models["secondary"]["cells"])},
        "cells": {"primary": prim_rows, "secondary": sec_rows},
        "calls_log": {k: v["calls_log"] for k, v in models.items()},
        "caveats": [
            "Agreement between AI graders from two companies, not agreement with teachers or any human rater.",
            "Items are author-written (30); intervals cover item sampling only, not prompt-version, "
            "model-version or population variance.",
            "Grader A is the replication's stored Gemini ensemble; its runs and OpenAI's runs were made two "
            "months apart, so run i pairing is by index, not by time.",
            "The secondary (gpt-5.5) is one run and a sensitivity check only.",
        ],
    }
    text = json.dumps(out, indent=2, default=str)
    md = render_md(out)
    if _KEY in text or _KEY in md:
        print("refusing to write: key material found in output")
        return 1
    OUT_JSON.write_text(text, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
