"""Layers 3 and 4 on all 30 benchmark items.

    .venv/Scripts/python -m eval.layers34              # offline, then live if the key works
    .venv/Scripts/python -m eval.layers34 --offline    # offline only

The protocol is fixed in `eval/layers34_protocol.md`, written before the first
run. This script implements it and changes nothing in the framework, the policy
or the engines: every call goes through `Session.submit`, the real path. The
only addition is a pass-through recorder around the judge engine that logs what
`compose` returned and how long each call took; it delegates every call
unchanged.

Results go to eval/results/layers34-<timestamp>.json and .md.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promptcoach_ref.engines import DeterministicEngine
from promptcoach_ref.engines.base import EngineError
from promptcoach_ref.framework import sentinel as sentinel_spec
from promptcoach_ref.framework.contracts import (
    CalibrateInput,
    DiagnoseInput,
    RespondInput,
)
from promptcoach_ref.framework.taxonomy import Category
from promptcoach_ref.layers import CalibrateLayer, Consent, DiagnoseLayer, RespondLayer
from promptcoach_ref.layers.measure import ROUTING_SCORE_AVAILABLE
from promptcoach_ref.policy import taskbank
from promptcoach_ref.session import Session, Stage

SEED = 20261024
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CORPUS = HERE / "benchmark.json"

#: sec:build1 / framework/sentinel.py: each signal and the category it derives.
SIGNAL_TO_CATEGORY = {s.id: s.derives_category.value for s in sentinel_spec.SIGNALS}

#: Protocol definition (a): the corpus noise label that corresponds to a signal.
#: transcript_prompt_disconnect has no corpus label; `sarcastic` is unmapped.
NOISE_TO_SIGNAL = {
    "mindless_retry": "mindless_retry",
    "pasted_ai_text": "copied_ai_content",
    "deferent": "excessive_deference",
}

#: The cut eval/benchmark.py uses for "fired"; the thesis commits to none.
FIRED_AT = 0.5


# ---------------------------------------------------------------------------
# pass-through recorder
# ---------------------------------------------------------------------------


class Recorder:
    """Delegates every Engine call unchanged; logs latency and compose output."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.name = inner.name
        self.organisation = inner.organisation
        self.log: list[dict[str, Any]] = []

    def _timed(self, op: str, fn, *args):
        started = time.perf_counter()
        ok = True
        out = None
        try:
            out = fn(*args)
            return out
        except Exception:
            ok = False
            raise
        finally:
            entry = {
                "op": op,
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "ok": ok,
            }
            if op == "compose":
                entry["returned"] = out
            self.log.append(entry)

    def sample_scores(self, request, temperature):
        return self._timed("score", self.inner.sample_scores, request, temperature)

    def diagnose(self, request):
        return self._timed("diagnose", self.inner.diagnose, request)

    def compose(self, request):
        return self._timed("compose", self.inner.compose, request)

    # Added for run 2: since E02, Layer 5 calls the judge engine's own
    # over-reliance detector. A recorder without this method would hide the
    # detector from the session and so stop delegating every call, which the
    # protocol requires. It delegates unchanged and is only logged.
    def sentinel(self, *args):
        return self._timed("sentinel", self.inner.sentinel, *args)

    @property
    def SENTINEL_SOURCE(self):  # noqa: N802
        return getattr(self.inner, "SENTINEL_SOURCE", None)


# ---------------------------------------------------------------------------
# serialisation
# ---------------------------------------------------------------------------


def _j(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _j(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {(_j(k) if isinstance(k, Enum) else k): _j(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_j(v) for v in obj]
    return obj


def _ranked(diag) -> list[dict[str, Any]]:
    if diag is None:
        return []
    return [
        {
            "rank": a.rank,
            "category": a.category.value,
            "confidence": a.confidence,
            "trigger": a.trigger,
        }
        for a in diag.assignments
    ]


# ---------------------------------------------------------------------------
# one item
# ---------------------------------------------------------------------------


def _consent() -> Consent:
    return Consent(platform_use=True, research_participation=False, audio_retention=False)


def _sentinel_offline(record, parent) -> dict[str, float]:
    """The implementation's own rule formula (CalibrateLayer._sentinel)."""
    data = CalibrateInput(
        parent=parent or record,
        child=record if parent else None,
        target=Category.UNDER_SPECIFICATION,
        level_issued=0,
        parent_scores={},
        child_scores=None,
        band=taskbank.BY_ID[taskbank.WORKED_EXAMPLE_ID].band,
    )
    return CalibrateLayer()._sentinel(data)


def run_item(item: dict[str, Any], judge: Any, generator: Any, live: bool) -> dict[str, Any]:
    rec = Recorder(judge)
    row: dict[str, Any] = {
        "id": item["id"],
        "tier": item["tier"],
        "noise_kind": item["noise_kind"],
        "risk": item["risk"],
        "clean": item["clean"],
        "plan_used": item["stated_intent"],
        "prompt_text": item["prompt_text"],
        "history": item.get("history", []),
        "crash": None,
    }
    started = time.perf_counter()
    try:
        session = Session(
            session_id=f"l34-{item['id']}",
            consent=_consent(),
            engine=rec,
            generator=generator,
        )
        task = taskbank.BY_ID[session.task_id]
        row["task_id"] = task.id
        row["protected_judgment"] = task.protected_judgment

        prior_records = []
        prior_turns = []
        for h in item.get("history", []):
            pr = session.submit(stated_intent=item["stated_intent"], prompt_text=h)
            prior_turns.append(
                {
                    "prompt_text": h,
                    "stopped_at": pr.stopped_at.value,
                    "top": pr.diagnose.target.value if pr.diagnose and pr.diagnose.target else None,
                    "level": pr.respond.level if pr.respond else None,
                }
            )
            if pr.elicit.record is not None:
                prior_records.append(pr.elicit.record)
        row["prior_turns"] = prior_turns

        compose_before = sum(1 for e in rec.log if e["op"] == "compose")
        log_before = len(rec.log)

        res = session.submit(stated_intent=item["stated_intent"], prompt_text=item["prompt_text"])

        row["stopped_at"] = res.stopped_at.value
        row["clarification"] = res.clarification
        record = res.elicit.record
        m = res.measure
        if m is not None:
            row["scores"] = {k: v.value for k, v in m.scores.items()}
            row["overall"] = m.overall
            row["routing"] = m.routing
            row["measure_failure"] = m.failure_reason
            row["judge_model"] = m.judge_model
            row["generator_model"] = m.generator_model
        if res.answer is not None:
            row["answer_source"] = res.answer.source
            row["answer_latency_ms"] = getattr(res.answer, "latency_ms", None)
            row["answer_excerpt"] = (res.answer.text or "")[:240]

        d = res.diagnose
        row["diagnosed"] = d is not None
        row["top"] = d.target.value if d and d.target else None
        row["ranked"] = _ranked(d)
        row["insufficient_evidence"] = d.insufficient_evidence if d else None
        row["diagnose_trace"] = list(d.reason_trace) if d else []

        r = res.respond
        row["respond_ran"] = r is not None
        composes = [e for e in rec.log if e["op"] == "compose"][compose_before:]
        if r is not None:
            first = composes[0]["returned"] if composes else None
            row["first_reply"] = first
            row["first_reply_empty"] = not (first and str(first).strip())
            row["blocked"] = "generated response rejected" in r.selection_reason
            row["block_reason"] = (
                r.selection_reason.split("generated response rejected - ", 1)[1]
                if row["blocked"]
                else None
            )
            row["used_template_floor"] = r.used_template_floor
            # Served text passed validate(): the generated text only reaches here
            # if it passed, and a floor that fails raises AssertionError.
            row["final_passed"] = True
            row["level"] = r.level
            row["final_text"] = r.text
            row["selection_reason"] = r.selection_reason

        # Source signal, definition (b): the implementation's own sentinel.
        parent = prior_records[-1] if prior_records else None
        if record is not None:
            if live:
                try:
                    row["sentinel"] = judge.sentinel(
                        item["stated_intent"], item["prompt_text"], tuple(item.get("history", []))
                    )
                except EngineError as exc:
                    row["sentinel"] = None
                    row["sentinel_error"] = str(exc)[:200]
            else:
                row["sentinel"] = _sentinel_offline(record, parent)

        # Secondary, forced path - only where the real session stopped early.
        if record is not None and m is not None and r is None:
            forced: dict[str, Any] = {"reason": f"session stopped at {res.stopped_at.value}"}
            try:
                fdiag = d
                if fdiag is None:
                    fdiag = DiagnoseLayer(rec).run(
                        DiagnoseInput(
                            record=record,
                            scores=m.scores,
                            session_history=tuple(prior_records),
                        )
                    )
                forced["top"] = fdiag.target.value if fdiag.target else None
                forced["ranked"] = _ranked(fdiag)
                if fdiag.target is not None:
                    fc_before = sum(1 for e in rec.log if e["op"] == "compose")
                    fr = RespondLayer(rec).run(
                        RespondInput(record=record, target=fdiag.target, scores=m.scores),
                        protected_judgment=task.protected_judgment,
                    )
                    fcomp = [e for e in rec.log if e["op"] == "compose"][fc_before:]
                    ffirst = fcomp[0]["returned"] if fcomp else None
                    forced.update(
                        level=fr.level,
                        first_reply=ffirst,
                        first_reply_empty=not (ffirst and str(ffirst).strip()),
                        blocked="generated response rejected" in fr.selection_reason,
                        used_template_floor=fr.used_template_floor,
                        final_passed=True,
                        final_text=fr.text,
                        selection_reason=fr.selection_reason,
                    )
            except Exception as exc:  # recorded, never hidden
                forced["crash"] = f"{type(exc).__name__}: {exc}"
                forced["traceback"] = traceback.format_exc()
            row["forced"] = forced

        row["calls"] = rec.log[log_before:]
    except Exception as exc:
        row["crash"] = f"{type(exc).__name__}: {exc}"
        row["traceback"] = traceback.format_exc()
        row["calls"] = rec.log
    row["wall_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return row


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------


def _lat(values: list[float]) -> dict[str, Any]:
    v = sorted(x for x in values if x is not None)
    if not v:
        return {"n": 0, "mean_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "n": len(v),
        "mean_ms": round(statistics.fmean(v), 1),
        "p95_ms": round(v[max(0, int(round(0.95 * len(v))) - 1)], 1),
        "max_ms": round(max(v), 1),
    }


def _top_label(r: dict[str, Any]) -> str:
    if r.get("crash"):
        return "(crash)"
    if r.get("top"):
        return r["top"]
    if r.get("diagnosed"):
        return "(no target)"
    return f"(stopped at {r.get('stopped_at')})"


def analyse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"n_items": len(rows)}
    out["stopped_at"] = dict(Counter(r.get("stopped_at", "(crash)") for r in rows))
    out["n_diagnosed"] = sum(1 for r in rows if r.get("diagnosed"))
    out["n_respond_ran"] = sum(1 for r in rows if r.get("respond_ran"))

    tops = [_top_label(r) for r in rows]
    out["top_overall"] = dict(Counter(tops).most_common())
    by_tier: dict[str, dict[str, int]] = {}
    for tier in ("weak", "medium", "strong"):
        by_tier[tier] = dict(
            Counter(_top_label(r) for r in rows if r["tier"] == tier).most_common()
        )
    out["top_by_tier"] = by_tier
    by_noise: dict[str, dict[str, int]] = {}
    for r in rows:
        key = r["noise_kind"] or "clean"
        by_noise.setdefault(key, Counter())[_top_label(r)] += 1  # type: ignore[index]
    out["top_by_noise"] = {k: dict(v) for k, v in sorted(by_noise.items())}

    anywhere = Counter()
    for r in rows:
        for a in r.get("ranked", []):
            anywhere[a["category"]] += 1
    out["category_anywhere_in_list"] = dict(anywhere.most_common())
    out["ranked_list_length"] = dict(Counter(len(r.get("ranked", [])) for r in rows))

    # Category given its source signal.
    sig: dict[str, Any] = {}
    for sid, cat in SIGNAL_TO_CATEGORY.items():
        a_items = [r for r in rows if NOISE_TO_SIGNAL.get(r["noise_kind"] or "") == sid]
        b_items = [
            r for r in rows if (r.get("sentinel") or {}).get(sid, 0.0) >= FIRED_AT
        ]

        def tally(items):
            return {
                "fired": len(items),
                "ids": [r["id"] for r in items],
                "category_top": sum(1 for r in items if r.get("top") == cat),
                "category_in_list": sum(
                    1 for r in items if any(a["category"] == cat for a in r.get("ranked", []))
                ),
                "tops_when_fired": dict(Counter(_top_label(r) for r in items)),
            }

        sig[sid] = {
            "derives": cat,
            "a_author_label": tally(a_items) if sid != "transcript_prompt_disconnect" else None,
            "b_implementation_sentinel": tally(b_items),
        }
    out["signal_to_category"] = sig
    out["unmapped_noise"] = {
        "sarcastic": [r["id"] for r in rows if r["noise_kind"] == "sarcastic"],
    }

    # Authorship check.
    l4 = [r for r in rows if r.get("respond_ran")]
    generated = [r for r in l4 if not r.get("first_reply_empty")]
    blocked = [r for r in generated if r.get("blocked")]
    empty = [r for r in l4 if r.get("first_reply_empty")]
    floors = [r for r in l4 if r.get("used_template_floor")]
    passed = [r for r in l4 if r.get("final_passed")]
    out["authorship"] = {
        "items_reaching_layer4": len(l4),
        "replies_generated": len(generated),
        "first_pass_blocked": len(blocked),
        "first_pass_block_rate": round(len(blocked) / len(generated), 4) if generated else None,
        "empty_generations": len(empty),
        "template_floor_served": len(floors),
        "floor_passed_after_block": sum(1 for r in blocked if r.get("used_template_floor")),
        "final_passed": len(passed),
        "final_pass_rate": round(len(passed) / len(l4), 4) if l4 else None,
        "block_reasons": {r["id"]: r.get("block_reason") for r in blocked},
    }
    out["levels"] = dict(Counter(r.get("level") for r in l4))
    out["crashes"] = {r["id"]: r["crash"] for r in rows if r.get("crash")}

    forced = [r for r in rows if "forced" in r]
    if forced:
        fl = [r["forced"] for r in forced]
        out["forced"] = {
            "n": len(forced),
            "ids": [r["id"] for r in forced],
            "why": {r["id"]: r["forced"]["reason"] for r in forced},
            "top": dict(Counter(f.get("top") or "(no target)" for f in fl)),
            "respond_ran": sum(1 for f in fl if "level" in f),
            "blocked": sum(1 for f in fl if f.get("blocked")),
            "empty": sum(1 for f in fl if f.get("first_reply_empty")),
            "floor": sum(1 for f in fl if f.get("used_template_floor")),
            "crashes": {r["id"]: r["forced"]["crash"] for r in forced if r["forced"].get("crash")},
        }

    calls = [c for r in rows for c in r.get("calls", [])]
    out["latency"] = {
        "item_wall": _lat([r.get("wall_ms") for r in rows]),
        "score_call": _lat([c["ms"] for c in calls if c["op"] == "score"]),
        "diagnose_call_layer3": _lat([c["ms"] for c in calls if c["op"] == "diagnose"]),
        "compose_call_layer4": _lat([c["ms"] for c in calls if c["op"] == "compose"]),
        "generator_answer": _lat([r.get("answer_latency_ms") for r in rows]),
        "failed_calls": sum(1 for c in calls if not c["ok"]),
    }
    return out


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def _table(d: dict[str, int]) -> str:
    return ", ".join(f"{k} {v}" for k, v in d.items()) or "none"


def report(results: dict[str, Any]) -> str:
    L: list[str] = []
    p = L.append
    title = f"# Layers 3 and 4 on the 30-item benchmark ({results['stamp']})"
    if results.get("label"):
        title = f"# Layers 3 and 4 on the 30-item benchmark, {results['label']} ({results['stamp']})"
    p(title)
    p("")
    if results.get("note"):
        p(results["note"])
        p("")
    p("Protocol: `eval/layers34_protocol.md`, fixed before the run. Nothing was tuned.")
    p(f"Corpus: `eval/benchmark.json` (30 author-written items). Seed {SEED}.")
    p("")
    if results.get("live_status"):
        p(f"Live status: {results['live_status']}")
        p("")
    for eng in results["engines"]:
        a = eng["analysis"]
        p(f"## Engine: {eng['label']}")
        p("")
        p(f"- judge `{eng['judge']}`, generator `{eng['generator']}`")
        p(f"- items {a['n_items']}; stopped at: {_table(a['stopped_at'])}")
        p(f"- reached Layer 3: {a['n_diagnosed']}; reached Layer 4: {a['n_respond_ran']}")
        p(f"- crashes: {len(a['crashes'])}" + (f" {a['crashes']}" if a["crashes"] else ""))
        p("")
        p("### Top category")
        p("")
        p(f"- overall: {_table(a['top_overall'])}")
        for t, d in a["top_by_tier"].items():
            p(f"- {t}: {_table(d)}")
        p("")
        p("By noise category:")
        p("")
        p("| noise | top categories |")
        p("|---|---|")
        for k, d in a["top_by_noise"].items():
            p(f"| {k} | {_table(d)} |")
        p("")
        p(f"Anywhere in the ranked list: {_table(a['category_anywhere_in_list'])}")
        p(f"Ranked-list length: {_table({str(k): v for k, v in a['ranked_list_length'].items()})}")
        p("")
        p("### Category when its source signal fired")
        p("")
        p("| signal -> category | (a) author label: fired / top / in list | (b) implementation sentinel >= 0.5: fired / top / in list |")
        p("|---|---|---|")
        for sid, s in a["signal_to_category"].items():
            aa = s["a_author_label"]
            bb = s["b_implementation_sentinel"]
            acell = "no corpus label" if aa is None else f"{aa['fired']} / {aa['category_top']} / {aa['category_in_list']}"
            p(f"| {sid} -> {s['derives']} | {acell} | {bb['fired']} / {bb['category_top']} / {bb['category_in_list']} |")
        p("")
        p(f"Unmapped noise label (no signal assigned in the corpus): sarcastic {a['unmapped_noise']['sarcastic']}.")
        p("")
        au = a["authorship"]
        p("### Authorship check (Layer 4)")
        p("")
        p(f"- items reaching Layer 4: {au['items_reaching_layer4']}")
        p(f"- replies generated (non-empty): {au['replies_generated']}; empty/failed generations: {au['empty_generations']}")
        p(f"- first-pass blocked: {au['first_pass_blocked']} (rate {au['first_pass_block_rate']})")
        p(f"- template floor served: {au['template_floor_served']}; floor passed after a block: {au['floor_passed_after_block']}")
        p(f"- final pass: {au['final_passed']} of {au['items_reaching_layer4']} (rate {au['final_pass_rate']})")
        p(f"- final level: {_table({str(k): v for k, v in a['levels'].items()})}")
        if au["block_reasons"]:
            p("- block reasons:")
            for k, v in au["block_reasons"].items():
                p(f"  - {k}: {v}")
        p("")
        if "forced" in a:
            f = a["forced"]
            p("### Secondary (forced) path, items where the session stopped before Layer 4")
            p("")
            p(f"- n {f['n']}: {f['why']}")
            p(f"- top: {_table(f['top'])}; Respond ran {f['respond_ran']}; blocked {f['blocked']}; empty {f['empty']}; floor {f['floor']}; crashes {f['crashes'] or 0}")
            p("")
        lat = a["latency"]
        if eng["live"]:
            p("### Latency (ms)")
            p("")
            p("| | n | mean | P95 | max |")
            p("|---|---|---|---|---|")
            for k in ("item_wall", "score_call", "diagnose_call_layer3", "compose_call_layer4", "generator_answer"):
                x = lat[k]
                p(f"| {k} | {x['n']} | {x['mean_ms']} | {x['p95_ms']} | {x['max_ms']} |")
            p(f"\nFailed engine calls: {lat['failed_calls']}")
            p("")
        p("### Per item")
        p("")
        p("| id | tier | noise | top | ranked | level | blocked | floor |")
        p("|---|---|---|---|---|---|---|---|")
        for r in eng["rows"]:
            ranked = " > ".join(f"{x['category']} {x['confidence']:.2f}" for x in r.get("ranked", []))
            p(
                f"| {r['id']} | {r['tier']} | {r['noise_kind'] or 'clean'} | {_top_label(r)} | {ranked} | "
                f"{r.get('level', '')} | {r.get('blocked', '')} | {r.get('used_template_floor', '')} |"
            )
        p("")
    p("## Limits")
    p("")
    p("- Thirty author-written items; tier and noise labels set by the same author. No student data.")
    p("- The offline engine is a surface-feature rule set; its compose is the template floor itself, so its authorship-check numbers test the floor, not a generator.")
    p("- Live: one run per item, model sampling not seedable; a second run will differ.")
    p("- Items carry no task, so every item runs under the session-default task (b3-babysitting) and its protected judgment.")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _preflight() -> tuple[bool, str, Any, Any]:
    from promptcoach_ref.engines import gemini
    from promptcoach_ref.policy import generator as generator_policy

    if not gemini.available():
        return False, "no GEMINI_API_KEY in the project .env", None, None
    try:
        judge = gemini.build("scorer")
        generator = gemini.build("generator")
        generator_policy.check_independent((judge.name,), generator.name)
        judge._generate("Reply with the single word OK.", "ping", 0.0, None, 16)
        generator._generate("Reply with the single word OK.", "ping", 0.0, None, 16)
    except Exception as exc:
        # The message can echo the request URL; keep only the type and status.
        msg = str(exc).split(":", 1)[0][:80]
        return False, f"live preflight failed ({type(exc).__name__}: {msg})", None, None
    return True, f"live preflight ok ({judge.model}, {generator.model})", judge, generator


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true", help="skip the live engine")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--label", default="", help="run label printed in the report title, e.g. 'run 2'")
    ap.add_argument("--note", default="", help="one paragraph printed under the title (what changed in the code)")
    args = ap.parse_args()

    random.seed(SEED)
    items = json.loads(CORPUS.read_text("utf-8"))["items"]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    results: dict[str, Any] = {"stamp": stamp, "seed": SEED, "corpus": str(CORPUS.name), "engines": []}
    if args.label:
        results["label"] = args.label
    if args.note:
        results["note"] = args.note

    # 1. offline, always.
    print("offline: deterministic engine")
    judge = DeterministicEngine()
    rows = [run_item(it, judge, None, live=False) for it in items]
    results["engines"].append(
        {
            "label": "offline deterministic",
            "live": False,
            "judge": judge.name,
            "generator": "scripted-responder",
            "rows": rows,
            "analysis": analyse(rows),
        }
    )

    # 2. live, if the key works.
    if args.offline:
        results["live_status"] = "skipped (--offline)"
    else:
        ok, status, lj, lg = _preflight()
        results["live_status"] = status
        print(status)
        if ok:
            t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                live_rows = list(pool.map(lambda it: run_item(it, lj, lg, live=True), items))
            wall = round(time.perf_counter() - t0, 1)
            results["engines"].append(
                {
                    "label": "live Gemini",
                    "live": True,
                    "judge": lj.name,
                    "generator": lg.name,
                    "wall_seconds": wall,
                    "judge_stats": lj.stats(),
                    "generator_stats": lg.stats(),
                    "rows": live_rows,
                    "analysis": analyse(live_rows),
                }
            )

    RESULTS.mkdir(exist_ok=True)
    jpath = RESULTS / f"layers34-{stamp}.json"
    mpath = RESULTS / f"layers34-{stamp}.md"
    jpath.write_text(json.dumps(_j(results), indent=2, default=str), encoding="utf-8")
    text = report(results)
    mpath.write_text(text, encoding="utf-8")
    print(text)
    print(f"written to {jpath} and {mpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
