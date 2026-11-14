"""Does help climb across revisions in a live session?

    .venv/Scripts/python -m eval.live_climb

PROTOCOL (fixed on 2026-11-14, before the first and only run)
==============================================================

Why. The thesis says help climbing across revisions "has been exercised only
in end-to-end tests" (offline, DeterministicEngine; tests/test_review_r3.py).
This run asks whether the ladder climbs when the judge and generator are live.

Items. The 11 items with tier "weak" in eval/benchmark.json (w01-w11),
author-written. No student data. These are scripted revisions of
author-written items, not students.

Per item, one fresh Session (session defaults otherwise, exactly as
eval/layers34.py: task b3-babysitting, consent platform yes / research no /
audio no, selection mode default, no predicted rating, no inserted spans,
asked_for_help False). Four submissions through Session.submit, the real path:

    1. prompt_text   (first attempt, no parent, no reason)
    2. paraphrase    (revision of 1: parent_attempt_id = 1, reason REASON)
    3. prompt_text   (revision of 2: parent_attempt_id = 2, reason REASON)
    4. paraphrase    (revision of 3: parent_attempt_id = 3, reason REASON)

stated_intent = the item's stated_intent, intent_modality "typed". REASON is
the fixed string "I tried to make it clearer" for every revision. The item's
`history` field (w07-w09) is NOT submitted: this protocol is the four attempts
above and nothing else. If an attempt stops at Elicit (no record), it is
recorded; the next attempt revises the last attempt that was recorded (or is a
fresh attempt without a reason if none was).

Live configuration, exactly as eval/layers34.py `_preflight`: judge
`gemini.build("scorer")` = gemini-3.1-flash-lite (scores, diagnoses, composes,
sentinel), generator `gemini.build("generator")` = gemini-3.1-pro-preview
(policy default), no comparator, independence checked, one ping per model. The
judge is wrapped in layers34's pass-through Recorder (delegates every call
unchanged, logs per-call latency and the raw compose output). Items run in
parallel (5 workers, as layers34); the four attempts within an item are
sequential.

Recorded per attempt: stage stopped at; whether it is a revision; routing;
top-ranked category and the ranked list; help level issued (None if Layer 4 did
not run); whether the authorship check (`validate`) blocked the generated reply
(selection_reason contains "generated response rejected"); whether the
generator's compose came back empty or failed; whether the template floor was
served; help_cycle note; Layer 5 paired delta; latency (wall ms of the submit
call, plus per engine call); any exception with traceback.

Per item: levels by attempt; highest level reached; whether level 4 (worked
contrast) was reached; whether the help cycle closed (any attempt's help_cycle
note begins "closed"), and the session's `unresolved` list.

Reported: per-item table of levels by attempt; counts of items reaching
level >= 2, >= 3, = 4; authorship blocks and template-floor uses by level;
attempt latency mean and 95th percentile (same P95 rule as layers34 `_lat`);
failures.

Rules. One run. No prompt, rule, threshold, template or code change during or
after. This script does no retries of its own: a failed submit is recorded and
the item moves on. (The engine's existing transport code backs off and retries
on HTTP 429 up to three times; that is the shipped configuration, not changed
here, and any 429 is counted in the engine stats.) Model sampling is not
seedable; a second run would differ. No API key or personal identifier is
written to the results.

Cost estimate (before running). layers34's live run used ~196 judge calls
(~68k in / 31k out tokens) and 34 generator calls for 30 single attempts.
44 attempts here: roughly 300-350 judge calls (~100-150k in / ~50k out) and 44
generator calls (a few thousand tokens). At list prices of the order of
$0.1-0.4 per million tokens for flash-lite and $2-12 per million for
pro-preview, the run is expected to cost well under US$1 (likely a few cents).

Outputs: eval/results/live_climb-<timestamp>.json and .md.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.layers34 import Recorder, _consent, _j, _lat, _preflight, _ranked  # noqa: E402
from promptcoach_ref.framework import ladder  # noqa: E402
from promptcoach_ref.session import Session  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CORPUS = HERE / "benchmark.json"
REASON = "I tried to make it clearer"
WORKERS = 5


def run_item(item: dict[str, Any], judge: Any, generator: Any) -> dict[str, Any]:
    rec = Recorder(judge)
    row: dict[str, Any] = {
        "id": item["id"],
        "noise_kind": item["noise_kind"],
        "stated_intent": item["stated_intent"],
        "attempts": [],
        "crash": None,
    }
    try:
        session = Session(
            session_id=f"climb-{item['id']}",
            consent=_consent(),
            engine=rec,
            generator=generator,
        )
    except Exception as exc:
        row["crash"] = f"{type(exc).__name__}: {exc}"
        row["traceback"] = traceback.format_exc()
        return row

    texts = [item["prompt_text"], item["paraphrase"], item["prompt_text"], item["paraphrase"]]
    parent: str | None = None
    for k, text in enumerate(texts, start=1):
        a: dict[str, Any] = {
            "n": k,
            "prompt_text": text,
            "parent_given": parent is not None,
            "error": None,
        }
        log_before = len(rec.log)
        t0 = time.perf_counter()
        try:
            res = session.submit(
                stated_intent=item["stated_intent"],
                prompt_text=text,
                intent_modality="typed",
                parent_attempt_id=parent,
                revision_reason=REASON if parent is not None else None,
            )
        except Exception as exc:  # recorded, never retried
            a["wall_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            a["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            a["traceback"] = traceback.format_exc()
            a["calls"] = rec.log[log_before:]
            row["attempts"].append(a)
            continue
        a["wall_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        calls = rec.log[log_before:]
        a["calls"] = [{k2: v for k2, v in c.items() if k2 != "returned"} for c in calls]

        a["stopped_at"] = res.stopped_at.value
        a["clarification"] = res.clarification
        record = res.elicit.record
        a["recorded"] = record is not None
        a["is_revision"] = bool(record and record.is_revision)
        m = res.measure
        if m is not None:
            a["routing"] = m.routing
            a["overall"] = m.overall
            a["scores"] = {d: s.value for d, s in m.scores.items()}
            a["measure_failure"] = m.failure_reason
        if res.answer is not None:
            a["answer_source"] = res.answer.source
            a["answer_latency_ms"] = getattr(res.answer, "latency_ms", None)
        d = res.diagnose
        a["top"] = d.target.value if d and d.target else None
        a["ranked"] = _ranked(d)
        r = res.respond
        a["level"] = r.level if r else None
        if r is not None:
            composes = [c for c in calls if c["op"] == "compose"]
            first = composes[0].get("returned") if composes else None
            a["compose_ok"] = bool(composes and composes[0]["ok"])
            a["first_reply"] = first
            a["first_reply_empty"] = not (first and str(first).strip())
            a["blocked"] = "generated response rejected" in r.selection_reason
            a["block_reason"] = (
                r.selection_reason.split("generated response rejected - ", 1)[1]
                if a["blocked"]
                else None
            )
            a["used_template_floor"] = r.used_template_floor
            a["selection_reason"] = r.selection_reason
            a["final_text"] = r.text
        c = res.calibrate
        a["paired_delta"] = getattr(c, "paired_delta", None) if c else None
        a["help_cycle"] = res.help_cycle
        a["levels_issued_after"] = list(session.levels_issued)
        row["attempts"].append(a)
        if record is not None:
            parent = record.attempt_id

    levels = [x.get("level") for x in row["attempts"]]
    issued = [lv for lv in levels if lv is not None]
    row["levels"] = levels
    row["highest_level"] = max(issued) if issued else None
    row["reached_level4"] = ladder.TERMINAL_LEVEL in issued
    notes = [x.get("help_cycle") for x in row["attempts"]]
    row["cycle_closed"] = any(n and n.startswith("closed") for n in notes)
    row["cycle_close_notes"] = [n for n in notes if n and n.startswith("closed")]
    row["unresolved"] = list(session.unresolved)
    return row


def analyse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    atts = [a for r in rows for a in r["attempts"]]
    responded = [a for a in atts if a.get("level") is not None]
    out: dict[str, Any] = {
        "n_items": len(rows),
        "n_attempts": len(atts),
        "stopped_at": dict(Counter(a.get("stopped_at", "(error)") for a in atts)),
        "elicit_stops": [
            f"{r['id']}#{a['n']}" for r in rows for a in r["attempts"] if a.get("stopped_at") == "elicit"
        ],
        "items_level_ge2": sum(1 for r in rows if (r.get("highest_level") or 0) >= 2),
        "items_level_ge3": sum(1 for r in rows if (r.get("highest_level") or 0) >= 3),
        "items_level4": sum(1 for r in rows if r.get("reached_level4")),
        "items_cycle_closed": sum(1 for r in rows if r.get("cycle_closed")),
        "highest_level_dist": dict(Counter(str(r.get("highest_level")) for r in rows)),
        "level_sequences": dict(
            Counter(" ".join("-" if lv is None else str(lv) for lv in r.get("levels", [])) for r in rows)
        ),
    }
    by_level: dict[str, dict[str, int]] = {}
    for a in responded:
        b = by_level.setdefault(
            str(a["level"]), {"issued": 0, "blocked": 0, "empty_or_failed": 0, "template_floor": 0}
        )
        b["issued"] += 1
        b["blocked"] += int(bool(a.get("blocked")))
        b["empty_or_failed"] += int(bool(a.get("first_reply_empty")))
        b["template_floor"] += int(bool(a.get("used_template_floor")))
    out["respond_by_level"] = dict(sorted(by_level.items()))
    out["block_reasons"] = {
        f"{r['id']}#{a['n']} L{a['level']}": a["block_reason"]
        for r in rows
        for a in r["attempts"]
        if a.get("blocked")
    }
    out["top_by_attempt"] = {
        str(n): dict(Counter(a.get("top") or f"(none; {a.get('stopped_at')})" for a in atts if a["n"] == n))
        for n in (1, 2, 3, 4)
    }
    calls = [c for a in atts for c in a.get("calls", [])]
    out["latency"] = {
        "attempt_wall": _lat([a.get("wall_ms") for a in atts]),
        "score_call": _lat([c["ms"] for c in calls if c["op"] == "score"]),
        "diagnose_call": _lat([c["ms"] for c in calls if c["op"] == "diagnose"]),
        "compose_call": _lat([c["ms"] for c in calls if c["op"] == "compose"]),
        "sentinel_call": _lat([c["ms"] for c in calls if c["op"] == "sentinel"]),
        "generator_answer": _lat([a.get("answer_latency_ms") for a in atts]),
        "failed_judge_calls": sum(1 for c in calls if not c["ok"]),
    }
    out["errors"] = {
        f"{r['id']}#{a['n']}": a["error"] for r in rows for a in r["attempts"] if a.get("error")
    }
    out["crashes"] = {r["id"]: r["crash"] for r in rows if r.get("crash")}
    return out


def report(res: dict[str, Any]) -> str:
    L: list[str] = []
    p = L.append
    a = res.get("analysis")
    p(f"# Live climb across revisions ({res['stamp']})")
    p("")
    p("Protocol: the docstring of `eval/live_climb.py`, fixed before this run. One run, nothing tuned.")
    p("Items: the 11 weak items of `eval/benchmark.json`. These are scripted revisions of "
      "author-written items, not students.")
    p(f"Sequence per item: prompt_text, paraphrase, prompt_text, paraphrase; revisions carry "
      f"parent_attempt_id and the reason \"{REASON}\".")
    p("")
    p(f"Live status: {res['live_status']}")
    if not a:
        return "\n".join(L) + "\n"
    p(f"Judge `{res['judge']}`, generator `{res['generator']}`. Wall {res['wall_seconds']} s.")
    p("")
    p("## Per item (help level by attempt; '-' = no Layer 4 response)")
    p("")
    p("| id | noise | levels 1-4 | top by attempt | stopped at | highest | L4 | cycle closed | blocked (attempt) | floor (attempt) |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    for r in res["rows"]:
        at = r["attempts"]
        lv = " ".join("-" if x.get("level") is None else str(x["level"]) for x in at)
        tops = " / ".join(x.get("top") or "none" for x in at)
        stops = " / ".join(x.get("stopped_at") or "error" for x in at)
        blk = ",".join(str(x["n"]) for x in at if x.get("blocked")) or "none"
        flr = ",".join(str(x["n"]) for x in at if x.get("used_template_floor")) or "none"
        p(f"| {r['id']} | {r['noise_kind'] or 'clean'} | {lv} | {tops} | {stops} | "
          f"{r.get('highest_level')} | {r.get('reached_level4')} | {r.get('cycle_closed')} | {blk} | {flr} |")
    p("")
    p("## Counts")
    p("")
    p(f"- attempts {a['n_attempts']}; stopped at: {a['stopped_at']}; Elicit stops: {a['elicit_stops'] or 'none'}")
    p(f"- items reaching level >= 2: {a['items_level_ge2']}; >= 3: {a['items_level_ge3']}; level 4: {a['items_level4']} (of {a['n_items']})")
    p(f"- highest level per item: {a['highest_level_dist']}")
    p(f"- level sequences: {a['level_sequences']}")
    p(f"- items whose help cycle closed: {a['items_cycle_closed']}")
    p(f"- top category by attempt: {a['top_by_attempt']}")
    p("")
    p("## Authorship check and template floor by level")
    p("")
    p("| level | issued | blocked | empty/failed generation | template floor |")
    p("|---|---|---|---|---|")
    for k, b in a["respond_by_level"].items():
        p(f"| {k} | {b['issued']} | {b['blocked']} | {b['empty_or_failed']} | {b['template_floor']} |")
    if a["block_reasons"]:
        p("")
        p("Block reasons:")
        for k, v in a["block_reasons"].items():
            p(f"- {k}: {v}")
    p("")
    p("## Latency (ms)")
    p("")
    p("| | n | mean | P95 | max |")
    p("|---|---|---|---|---|")
    for k in ("attempt_wall", "score_call", "diagnose_call", "compose_call", "sentinel_call", "generator_answer"):
        x = a["latency"][k]
        p(f"| {k} | {x['n']} | {x['mean_ms']} | {x['p95_ms']} | {x['max_ms']} |")
    p("")
    p(f"Failed judge calls: {a['latency']['failed_judge_calls']}. Judge stats: {res['judge_stats']}. "
      f"Generator stats: {res['generator_stats']}.")
    p("")
    p("## Failures")
    p("")
    p(f"- attempt errors: {a['errors'] or 'none'}")
    p(f"- item crashes: {a['crashes'] or 'none'}")
    p("")
    p("## Cycle notes")
    p("")
    for r in res["rows"]:
        p(f"- {r['id']}: " + " | ".join(f"{x['n']}: {x.get('help_cycle')}" for x in r["attempts"])
          + (f"; unresolved {r['unresolved']}" if r.get("unresolved") else ""))
    p("")
    p("## Limits")
    p("")
    p("- Eleven author-written weak items; the revisions are scripted alternations of the item's own prompt and paraphrase, not student revisions.")
    p("- One live run; sampling is not seedable, a second run would differ.")
    p("- Every item runs under the session-default task (b3-babysitting).")
    return "\n".join(L) + "\n"


def main() -> int:
    items = [it for it in json.loads(CORPUS.read_text("utf-8"))["items"] if it["tier"] == "weak"]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    res: dict[str, Any] = {"stamp": stamp, "corpus": CORPUS.name, "reason": REASON,
                           "item_ids": [it["id"] for it in items]}
    ok, status, judge, generator = _preflight()
    res["live_status"] = status
    print(status)
    if ok:
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            rows = list(pool.map(lambda it: run_item(it, judge, generator), items))
        res["wall_seconds"] = round(time.perf_counter() - t0, 1)
        res["judge"] = judge.name
        res["generator"] = generator.name
        res["judge_stats"] = judge.stats()
        res["generator_stats"] = generator.stats()
        res["rows"] = rows
        res["analysis"] = analyse(rows)
    RESULTS.mkdir(exist_ok=True)
    jpath = RESULTS / f"live_climb-{stamp}.json"
    mpath = RESULTS / f"live_climb-{stamp}.md"
    jpath.write_text(json.dumps(_j(res), indent=2, default=str), encoding="utf-8")
    text = report(res)
    mpath.write_text(text, encoding="utf-8")
    print(text)
    print(f"written to {jpath} and {mpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
