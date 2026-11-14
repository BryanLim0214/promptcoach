"""Third-company grader check on the replication's 30 items (Google grader A vs Anthropic grader B).

    .venv/Scripts/python -m eval.crossco_claude_20261114 --dry-run   # gate + offline rows only, no API call
    .venv/Scripts/python -m eval.crossco_claude_20261114             # the run

PROTOCOL (written 2026-11-14, before this script made any API call; not changed after)
======================================================================================

Why
---
eval/crossco_20261114.py ran the two-company check (Google grader A vs OpenAI grader B)
on the replication's 30 items. This script adds a third company, Anthropic, as grader B,
with everything else held the same as that script. It reuses that script's own code
(imported, not copied) for grader-A loading, the gate, the cell retry loop, every
statistic, the bootstrap and the report formatting; only the transport is new.

Items and inputs
----------------
* The same 30 items, eval/benchmark.json, loaded as eval.benchmark.Item.
* Inputs to grader B are exactly the replication's: the user message built by
  GeminiEngine.sample_scores from `stated_intent` and `prompt_text` (no history, no
  paraphrase, as in the replication and in crossco_20261114).

Grader A (no new Gemini call)
-----------------------------
The stored replication grader-A scores (`rows[*].a`, `rows[*].a_overall`, model
gemini-3.1-flash-lite, 3-temperature ensemble rounded). Pairing: grader B's single run
is paired with replication RUN 1 (the same pairing crossco_20261114 used for its
one-run gpt-5.5 secondary).

Grader B (only the transport changes)
-------------------------------------
* Model: claude-sonnet-5-5, 1 run x 30 items (30 cells). The model id is checked first
  with GET https://api.anthropic.com/v1/models/claude-sonnet-5-5; a missing id aborts
  the run and no other model is substituted. The model id each response reports is
  recorded.
* Endpoint: POST https://api.anthropic.com/v1/messages, headers x-api-key,
  anthropic-version: 2023-06-01, content-type: application/json. Raw HTTP (httpx), as
  in crossco_20261114.
* Scoring instruction: promptcoach_ref.engines.gemini.SCORE_SYSTEM, byte-identical, sent
  as the top-level `system`. messages = [user: the replication's user message].
* Call path: eval.benchmark.score_once (via crossco_20261114.score_cell) on a subclass
  of GeminiEngine whose ONLY override is the `_json` transport (plus name/organisation
  labels). So the user message, the response parsing (unknown dimensions dropped,
  missing -> None) and the score_once rules (None skipped, values outside 1..4
  discarded never clamped, an empty result = unscored) are the replication's own code.
* Schema method (chosen now, not changed later): JSON-only output, parsed with the
  replication's parser rules. It is enforced at the API with structured outputs,
  `output_config: {format: {type: "json_schema", schema: S}}`, where S is
  gemini.SCORE_SCHEMA with `additionalProperties: false` added on every object (the
  same schema crossco_20261114 sent to OpenAI, produced by its strict_schema; same
  properties, types, enum and required lists). The forced-tool option is NOT used:
  Anthropic documents that claude-sonnet-5-5 returns HTTP 400 for tool_choice
  {type: "tool"} / {type: "any"}. No extra "reply in JSON" text is added, so the
  scoring instruction stays byte-identical. The reply's `text` blocks are joined and
  parsed with json.loads; anything that does not parse is a failed call.
* Temperature: 0.2 requested (the replication's grader-B temperature). The first call
  is made alone, before any parallel call. If the API rejects it with HTTP 400 naming
  `temperature`, temperature is omitted (API default) for every call and the rejection
  is recorded; that rejected request does not count as an attempt. (Anthropic documents
  that claude-sonnet-5-5 rejects non-default sampling values, so this is expected.)
* Other parameters: max_tokens 16000 (required by the API; the documented default for
  non-streaming requests). `thinking` and `effort` are not sent (API defaults: adaptive
  thinking, effort high), mirroring crossco_20261114, which sent no reasoning-effort
  parameter. No refusal `fallbacks` are sent, because a fallback would let a different
  model grade the cell. Nothing else is changed in response to an error.
* A response with stop_reason `refusal` or `max_tokens`, or with no text block, is a
  failed call.

Failures
--------
A call that errors or yields no usable score (score_once returns None) is retried at
most twice (3 attempts per cell, 2 s then 4 s pause; crossco_20261114.score_cell). A
cell still unscored after that is recorded and excluded from the pairing; counts are
reported. A partially scored cell is kept (overall = mean of the dimensions present)
and missing dimension values are counted.

Measures (crossco_20261114.analyse_pairing, unchanged)
------------------------------------------------------
* Overall ICC(2,2), absolute agreement (eval.benchmark.icc_2_2) on (a_overall, b_overall).
* Mean absolute gap |a_overall - b_overall| and mean signed gap (A - B).
* Per dimension: weighted kappa, linear and quadratic weights, exact %, within-one %, n.
* Lowest dimension = smallest kappa under each weighting; ties reported as ties.
* 95% percentile intervals: item bootstrap, 4000 resamples of the 30 items from a fresh
  random.Random(20261114) per pairing (eval.reanalysis_20261114.resamples); all runs
  of an item travel together; undefined draws dropped and counted.
* Comparison rows (no API call), same code, same resamples, all paired with replication
  run 1: Google-only (A vs stored gemini-3.8-flash run 1); OpenAI gpt-5.4-mini run 1
  and gpt-5.5 run 1 from eval/results/crossco_20261114.json. Plus the pooled 5-run
  Google-only reference used by the gate.

Gate (before any API call; on failure the script stops without calling anything)
--------------------------------------------------------------------------------
crossco_20261114.gate: from the stored replication data, reproduce the stored pooled
ICC (to 1e-12) and 0.973 at 3 decimals, Iteration Awareness linear kappa 0.404, each
stored per-run ICC, and 150 grader-A cells with all six dimensions.

Fixed in advance
----------------
Nothing is tuned and nothing is changed after seeing results; whatever comes out is
reported. What this is: agreement between AI graders from Google and Anthropic on 30
author-written items, one Anthropic run. It is not agreement with teachers, and the
intervals cover item sampling only. ANTHROPIC_API_KEY is read from .env and is never
printed, logged or written; every output is checked for it before writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import crossco_20261114 as cc  # noqa: E402
from eval.benchmark import Item  # noqa: E402
from promptcoach_ref.engines.base import EngineError  # noqa: E402
from promptcoach_ref.engines.gemini import SCORE_SCHEMA, SCORE_SYSTEM, GeminiEngine, load_env  # noqa: E402

MODEL = "claude-sonnet-5-5"
RUNS = 1
PAIRED_RUN = 1
TEMPERATURE = cc.TEMPERATURE  # 0.2
MAX_TOKENS = 16000
WORKERS = 6
ANTHROPIC_VERSION = "2023-06-01"
MESSAGES_URL = "https://api.anthropic.com/v1/messages"
MODELS_URL = "https://api.anthropic.com/v1/models/"

OUT_JSON = cc.RESULTS / "crossco_claude_20261114.json"
OUT_MD = cc.RESULTS / "crossco_claude_20261114.md"
OPENAI_RESULTS = cc.RESULTS / "crossco_20261114.json"

_KEY: str | None = None


def redact(text: str) -> str:
    if _KEY:
        text = text.replace(_KEY, "[redacted]")
    return re.sub(r"sk-[A-Za-z0-9_\-\*]{4,}", "sk-[redacted]", text)


def headers(key: str) -> dict[str, str]:
    return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}


class AnthropicGrader(GeminiEngine):
    """Replication grader B with the transport pointed at Anthropic. Prompt, user message
    and parsing are inherited unchanged from GeminiEngine."""

    def __post_init__(self) -> None:  # noqa: D401
        super().__post_init__()
        self.name = f"anthropic:{self.model}"
        self.organisation = "anthropic"
        self.send_temperature = True
        self.temperature_rejection: str | None = None
        self.call_log: list[dict[str, Any]] = []
        self._local = threading.local()
        self._lock = threading.Lock()

    def set_cell(self, tag: dict[str, Any]) -> None:
        self._local.cell = tag

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        return self._client.post(MESSAGES_URL, headers=headers(self.api_key or ""), json=body)

    def _fail(self, entry: dict[str, Any], kind: str, msg: str) -> EngineError:
        self._note(kind)
        entry.update(ok=False, error=redact(msg))
        with self._lock:
            self.call_log.append(entry)
        return EngineError(entry["error"])

    def _json(self, system: str, user: str, temperature: float, schema: dict) -> dict:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"format": {"type": "json_schema", "schema": cc.strict_schema(schema)}},
        }
        if self.send_temperature:
            body["temperature"] = temperature
        entry: dict[str, Any] = dict(getattr(self._local, "cell", {}) or {})
        entry["temperature_sent"] = body.get("temperature")
        started = time.perf_counter()
        try:
            response = self._post(body)
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
            raise self._fail(entry, "transport", f"transport failure: {exc}") from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        entry["latency_ms"] = round(elapsed_ms, 1)

        if response.status_code >= 400:
            raise self._fail(entry, f"http_{response.status_code}",
                             f"HTTP {response.status_code}: {response.text[:400]}")

        data = response.json()
        usage = data.get("usage") or {}
        with self._lock:
            self.calls += 1
            self.input_tokens += usage.get("input_tokens", 0) or 0
            self.output_tokens += usage.get("output_tokens", 0) or 0
            self.latencies_ms.append(elapsed_ms)
        entry.update(response_model=data.get("model"), request_id=data.get("id"),
                     stop_reason=data.get("stop_reason"), usage=usage)
        if data.get("stop_reason") == "refusal":
            entry["stop_details"] = data.get("stop_details")
            raise self._fail(entry, "refusal", "stop_reason refusal")
        if data.get("stop_reason") == "max_tokens":
            raise self._fail(entry, "max_tokens", "stop_reason max_tokens")
        blocks = data.get("content") or []
        entry["block_types"] = [b.get("type") for b in blocks]
        content = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        entry["content"] = content
        if not content:
            raise self._fail(entry, "no_text", "no text block")
        try:
            parsed = json.loads(content)
        except ValueError as exc:
            raise self._fail(entry, "invalid_json", "model returned invalid JSON") from exc
        entry["ok"] = True
        with self._lock:
            self.call_log.append(entry)
        return parsed


def verify_model(key: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as c:
        r = c.get(MODELS_URL + MODEL, headers=headers(key))
    if r.status_code != 200:
        return {"model": MODEL, "found": False, "status": r.status_code, "detail": redact(r.text[:300])}
    j = r.json()
    return {"model": MODEL, "found": True, "id": j.get("id"), "display_name": j.get("display_name")}


def run_model(items: list[Item], key: str) -> dict[str, Any]:
    engine = AnthropicGrader(model=MODEL, api_key=key, timeout=300.0)
    cells = [(it, PAIRED_RUN) for it in items]
    started = time.perf_counter()
    first = cc.score_cell(engine, *cells[0])  # alone, so the temperature rule settles first
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rest = list(pool.map(lambda c: cc.score_cell(engine, *c), cells[1:]))
    wall = time.perf_counter() - started
    return {
        "model_requested": MODEL,
        "response_models": sorted({c["response_model"] for c in engine.call_log if c.get("response_model")}),
        "temperature_requested": TEMPERATURE,
        "temperature_used": TEMPERATURE if engine.send_temperature else "API default (temperature rejected)",
        "temperature_rejection": engine.temperature_rejection,
        "schema_method": "structured outputs: output_config.format json_schema (SCORE_SCHEMA + additionalProperties:false)",
        "max_tokens": MAX_TOKENS,
        "thinking_effort": "not sent (API defaults)",
        "runs": RUNS,
        "paired_with_replication_run": PAIRED_RUN,
        "cells": [first] + rest,
        "calls_log": engine.call_log,
        "stats": engine.stats(),
        "wall_seconds": round(wall, 1),
    }


def comparison_rows(rep: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Run-1 pairings already on disk, recomputed with the same code (no API call)."""
    out = {"google_gemini-3.8-flash_run1": [r for r in cc.reference_rows(rep) if r["run"] == PAIRED_RUN]}
    if OPENAI_RESULTS.exists():
        o = json.loads(OPENAI_RESULTS.read_text(encoding="utf-8"))
        out["openai_gpt-5.4-mini_run1"] = [r for r in o["cells"]["primary"] if r["run"] == PAIRED_RUN]
        out["openai_gpt-5.5_run1"] = [r for r in o["cells"]["secondary"] if r["run"] == PAIRED_RUN]
    return out


def render_md(o: dict[str, Any]) -> str:
    L: list[str] = []
    p = L.append
    m = o["model"]
    a = o["analysis"]["claude"]
    p("# Third-company grader check (Anthropic), 2026-11-14")
    p("")
    p("Agreement between AI graders from Google (grader A) and Anthropic (grader B) on the replication's "
      "30 author-written items, **one Anthropic run**. **Not agreement with teachers.** Intervals: 95% "
      f"percentile, item bootstrap, {cc.REPS} resamples, seed {cc.SEED}; they cover item sampling only.")
    p("")
    p("Script: `eval/crossco_claude_20261114.py` (protocol in its docstring, fixed before any API call).")
    p("")
    p("## Setup")
    p("")
    p(f"- Grader A: stored replication run {PAIRED_RUN}, {', '.join(o['gate']['checks']['grader_a_models'])} "
      "(3-temperature ensemble, rounded mean), no new calls.")
    p("- Grader B instruction: `promptcoach_ref.engines.gemini.SCORE_SYSTEM` (byte-identical); inputs "
      "`stated_intent` + `prompt_text`; replication parser (`eval.benchmark.score_once`).")
    p(f"- Grader B: requested `{m['model_requested']}`; response model(s) "
      f"{', '.join('`' + s + '`' for s in m['response_models']) or 'n/a'}; temperature used: "
      f"{m['temperature_used']}; schema method: {m['schema_method']}; max_tokens {m['max_tokens']}; "
      f"thinking/effort {m['thinking_effort']}; API calls {m['stats']['calls']} "
      f"(errors {m['stats']['errors'] or 'none'}).")
    if m["temperature_rejection"]:
        p(f"  - temperature rejection message: `{m['temperature_rejection'][:200]}`")
    p("")
    p(f"Gate: **{'PASS' if o['gate']['pass'] else 'FAIL'}**. Pooled Google-only ICC recomputed "
      f"{o['gate']['pooled_icc']:.4f}; Iteration Awareness linear kappa {o['gate']['ia_linear_kappa']:.4f}.")
    p("")
    p("## Overall agreement (all rows paired with replication grader-A run 1 unless noted)")
    p("")
    p("| Pairing | Cells paired | ICC(2,2) | Mean abs gap | Mean signed gap (A-B) |")
    p("|---|---|---|---|---|")
    rows = [("claude", f"A vs {m['model_requested']} (this run)")]
    rows += [(k, f"A vs {k.split('_', 1)[1].replace('_run1', '')} (stored, run 1)") for k in o["analysis"]["comparison"]]
    for key, label in rows:
        x = a if key == "claude" else o["analysis"]["comparison"][key]
        p(f"| {label} | {x['n_paired']} | {cc.ci(x['icc_2_2'])} | {cc.ci(x['mean_abs_gap'])} | "
          f"{cc.ci(x['mean_signed_gap_a_minus_b'])} |")
    r = o["analysis"]["reference_google_pooled"]
    p(f"| Reference: A vs gemini-3.8-flash (stored, 5 runs pooled) | {r['n_paired']} | {cc.ci(r['icc_2_2'])} | "
      f"{cc.ci(r['mean_abs_gap'])} | {cc.ci(r['mean_signed_gap_a_minus_b'])} |")
    p("")
    p(f"## Per dimension: A vs {m['model_requested']}")
    p("")
    p("| Dimension | n | kappa linear | kappa quadratic | exact | within one |")
    p("|---|---|---|---|---|---|")
    for d, name in cc.DIMS:
        e = a["per_dimension"][d]
        p(f"| {name} | {e['n']} | {cc.ci(e['kappa_linear'])} | {cc.ci(e['kappa_quadratic'])} | "
          f"{cc.ci(e['exact'], pct=True)} | {cc.ci(e['within_one'], pct=True)} |")
    p("")
    p(f"Lowest (linear): {', '.join(cc.NAME[d] for d in a['lowest_linear'])}; "
      f"lowest (quadratic): {', '.join(cc.NAME[d] for d in a['lowest_quadratic'])}.")
    p("")
    p("Lowest dimension in the comparison rows: " + "; ".join(
        f"{k}: linear {', '.join(cc.NAME[d] for d in x['lowest_linear'])} / quadratic "
        f"{', '.join(cc.NAME[d] for d in x['lowest_quadratic'])}"
        for k, x in o["analysis"]["comparison"].items()) + ".")
    p("")
    p("## Failures")
    p("")
    f = o["failures"]
    p(f"- {f['cells_total']} cells; unscored after 3 attempts {f['unscored']} {f['unscored_cells'] or ''}; "
      f"cells needing a retry {f['retried']}; missing dimension values in scored cells "
      f"{f['missing_dimension_values']}.")
    p("")
    p("## Caveats")
    for c in o["caveats"]:
        p(f"- {c}")
    p("")
    return "\n".join(L)


def main() -> int:
    global _KEY
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="gate + offline rows only; no API call")
    args = ap.parse_args()

    rep = cc.load_replication()
    g = cc.gate(rep)
    print(f"gate: {'PASS' if g['pass'] else 'FAIL'}  pooled ICC {g['pooled_icc']:.4f}  IA linear {g['ia_linear_kappa']:.4f}")
    if not g["pass"]:
        print(json.dumps(g, indent=2, default=str))
        return 1

    payload = json.loads(cc.ITEMS.read_text("utf-8"))
    items = [Item(**row) for row in payload["items"]]
    item_ids = sorted(it.id for it in items)
    ref = cc.analyse_pairing(cc.reference_rows(rep), item_ids)
    comp = {k: cc.analyse_pairing(v, item_ids) for k, v in comparison_rows(rep).items()}
    if args.dry_run:
        print("dry run: reference pooled ICC", cc.ci(ref["icc_2_2"]))
        for k, v in comp.items():
            print(f"dry run: {k} ICC {cc.ci(v['icc_2_2'])}")
        return 0

    load_env()
    _KEY = os.environ.get("ANTHROPIC_API_KEY")
    if not _KEY:
        print("ANTHROPIC_API_KEY is not set in .env")
        return 1

    check = verify_model(_KEY)
    print("model check:", json.dumps(check))
    if not check["found"]:
        print("requested model id was not found; aborting without substitution")
        return 1

    print(f"scoring {MODEL}: {RUNS} run x {len(items)} items")
    model = run_model(items, _KEY)
    print(f"  done in {model['wall_seconds']} s; temperature used: {model['temperature_used']}")

    a_rows = cc.grader_a_rows(rep)
    rows = [{**c, **a_rows[(c["run"], c["id"])]} for c in model["cells"]]
    out: dict[str, Any] = {
        "protocol": "see module docstring of eval/crossco_claude_20261114.py (fixed before any API call)",
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seed": cc.SEED,
        "bootstrap_resamples": cc.REPS,
        "interval": "percentile 95%, item-level resampling",
        "inputs": {
            "replication": {"path": str(cc.REPLICATION), "sha256": cc.sha256(cc.REPLICATION)},
            "items": {"path": str(cc.ITEMS), "sha256": cc.sha256(cc.ITEMS)},
            "openai_results": {"path": str(OPENAI_RESULTS), "sha256": cc.sha256(OPENAI_RESULTS)}
            if OPENAI_RESULTS.exists() else None,
            "score_system_sha256": hashlib.sha256(SCORE_SYSTEM.encode("utf-8")).hexdigest(),
            "score_system": SCORE_SYSTEM,
            "schema_sent": cc.strict_schema(SCORE_SCHEMA),
            "anthropic_version": ANTHROPIC_VERSION,
        },
        "gate": g,
        "model_check": check,
        "model": {k: v for k, v in model.items() if k not in ("cells", "calls_log")},
        "analysis": {
            "claude": cc.analyse_pairing(rows, item_ids),
            "comparison": comp,
            "reference_google_pooled": ref,
        },
        "failures": cc.failures(model["cells"]),
        "cells": rows,
        "calls_log": model["calls_log"],
        "caveats": [
            "Agreement between AI graders from Google and Anthropic, not agreement with teachers or any human rater.",
            "Items are author-written (30); intervals cover item sampling only, not prompt-version, "
            "model-version or population variance.",
            "One Anthropic run, paired with replication grader-A run 1; run-to-run spread of the Anthropic "
            "grader is not measured here.",
            "Grader A was scored two months before grader B; pairing is by run index, not by time.",
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
