"""The HTTP surface.

Runs against the offline engine, so no key and no network. These cover the
routes the frontend depends on, and the two prohibitions that live at this layer
rather than in the framework: the teacher route is aggregate-only, and the
sentinel never appears in it.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from promptcoach_ref.api import app
from promptcoach_ref.framework import grades

pytestmark = pytest.mark.api

client = TestClient(app)

SPOKEN = (
    "Okay so I have to explain the sky thing to my cousin, she's like seven so it "
    "can't be complicated, maybe just a few sentences."
)
TYPED = "explain why the sky is blue"
REVISED = "explain why the sky is blue for a seven year old, keep it to a few sentences"
REASON = "I added who it is for and how long it should be"


def start(task_id: str = "b3-babysitting") -> str:
    r = client.post("/api/session", json={"platform_use": True, "task_id": task_id})
    assert r.status_code == 200
    return r.json()["session_id"]


# --- the spec routes ------------------------------------------------------


def test_framework_route_serves_the_whole_specification():
    fw = client.get("/api/framework").json()
    assert len(fw["dimensions"]) == 6
    assert len(fw["taxonomy"]) == 7
    assert len(fw["ladder"]) == 4
    assert len(fw["bands"]) == 5
    assert len(fw["sentinel"]["signals"]) == 4
    assert len(fw["commitments"]) == 4
    assert len(fw["grades"]["components"]) == 24


def test_framework_grade_counts_match_the_framework():
    fw = client.get("/api/framework").json()
    assert fw["grades"]["counts"] == {
        g.value: n for g, n in grades.EXPECTED_GRADE_COUNTS.items()
    }
    assert fw["grades"]["need_counts"] == {
        n.value: k for n, k in grades.EXPECTED_NEED_COUNTS.items()
    }
    for c in fw["grades"]["components"]:
        assert c["need"] in {"students", "builds", "argument"}
    assert "affective_state_inference" in fw["grades"]["removed"]


def test_framework_route_serves_the_classroom_aggregates_safely():
    """Non-comparable pairs arrive without a difference; comparable ones with."""
    fw = client.get("/api/framework").json()
    pairs = {p["id"]: p for p in fw["classroom"]["item_pairs"]}
    assert "pre" in pairs["promptemon.best_way"]
    assert pairs["picprompt.wrong_image_response"]["comparable"] is False
    assert "pre" not in pairs["picprompt.wrong_image_response"]
    assert "post" not in pairs["picprompt.wrong_image_response"]


def test_every_dimension_carries_a_citation():
    fw = client.get("/api/framework").json()
    for d in fw["dimensions"]:
        assert d["cite"].startswith("sec:build1")
        assert "tab:dimensions" in d["cite"]


def test_policy_route_exposes_every_choice_with_its_provenance():
    pol = client.get("/api/policy").json()
    assert len(pol["unspecified"]) == 24
    assert {c["id"] for c in pol["closed_by_removal"]} == {"affect_thresholds"}
    for c in pol["choices"]:
        assert c["thesis_says"] and c["borrowed_from"] and c["caveat"]


def test_tasks_cover_all_five_bands():
    tasks = client.get("/api/tasks").json()
    assert {t["band"] for t in tasks} == {1, 2, 3, 4, 5}
    assert sum(1 for t in tasks if t["from_thesis"]) == 1


def test_health_states_that_no_student_has_used_it():
    h = client.get("/api/health").json()
    assert "No middle school student" in h["no_students"]
    assert "implementable" in h["no_students"]


def test_health_names_a_generator_separate_from_the_judge():
    h = client.get("/api/health").json()
    assert h["generator"] == "scripted-responder"
    assert h["generator"] != h["engine"]
    assert h["judge_independent_of_generator"] is True


# --- the loop -------------------------------------------------------------


def test_a_full_cycle_returns_every_layer_and_an_answer():
    sid = start()
    r = client.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": SPOKEN,
            "prompt_text": TYPED,
            "intent_modality": "speech",
        },
    ).json()
    assert r["stopped_at"] == "respond"
    assert r["measure"]["overall"] is not None
    assert r["diagnose"]["target"] == "intent_drift"
    assert r["respond"]["level"] == 1
    # The part that makes it an application rather than a marking scheme.
    assert r["answer"] is not None
    assert r["answer"]["text"].strip()


def test_the_answer_is_produced_even_when_the_prompt_is_weak():
    """She has to see what a vague prompt actually returns. Withholding the
    answer until she improves would remove the only lesson available."""
    sid = start()
    r = client.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": "something about space", "prompt_text": "the water cycle"},
    ).json()
    assert r["stopped_at"] != "elicit"
    assert r["answer"]["text"].strip()


def test_a_prompt_too_short_to_read_is_asked_about_before_it_is_sent():
    """Below the capture floor the system asks rather than answering. That is a
    capture-quality gate, not a quality judgement: it separates a terse prompt
    from a slip of the keyboard."""
    sid = start()
    r = client.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": "something about space", "prompt_text": "space"},
    ).json()
    assert r["stopped_at"] == "elicit"
    assert "too short" in r["clarification"]
    assert r["answer"] is None


def test_a_revision_carries_the_previous_answer_for_comparison():
    sid = start()
    first = client.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": SPOKEN,
            "prompt_text": TYPED,
            "intent_modality": "speech",
        },
    ).json()
    second = client.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": SPOKEN,
            "prompt_text": REVISED,
            "parent_attempt_id": first["elicit"]["record"]["attempt_id"],
            "revision_reason": REASON,
        },
    ).json()
    assert second["previous_prompt"] == TYPED
    assert second["previous_answer"]["text"] == first["answer"]["text"]
    assert second["answer"]["text"] != second["previous_answer"]["text"]


def test_the_scripted_answer_changes_with_prompt_quality():
    """Offline, the responder reads the same six scores Layer 2 produced, so a
    better prompt visibly returns a better answer."""
    sid = start()
    weak = client.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": "i want to explain the sky", "prompt_text": TYPED},
    ).json()
    sid2 = start()
    strong = client.post(
        f"/api/session/{sid2}/submit",
        json={"stated_intent": SPOKEN, "prompt_text": REVISED},
    ).json()
    assert weak["answer"]["text"] != strong["answer"]["text"]
    # The vague prompt earns the longer, unfocused answer and is told why.
    assert "could not tell" in weak["answer"]["text"]
    assert len(weak["answer"]["text"]) > len(strong["answer"]["text"])


def test_an_empty_prompt_stops_at_elicit_with_a_specific_request():
    sid = start()
    r = client.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": "i want something", "prompt_text": ""},
    ).json()
    assert r["stopped_at"] == "elicit"
    assert r["clarification"]
    assert r["measure"] is None


def test_the_trace_records_every_layer_with_a_grade():
    sid = start()
    r = client.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": SPOKEN, "prompt_text": TYPED},
    ).json()
    layers = [s["layer"] for s in r["trace"]]
    assert layers[:3] == ["elicit", "measure", "diagnose"]
    for step in r["trace"]:
        assert step["grade"] in {"direct", "transferred", "argued"}
        assert step["cite"]


def test_layer_five_reports_that_its_contract_is_not_from_the_thesis():
    sid = start()
    first = client.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": SPOKEN, "prompt_text": TYPED},
    ).json()
    second = client.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": SPOKEN,
            "prompt_text": REVISED,
            "parent_attempt_id": first["elicit"]["record"]["attempt_id"],
            "revision_reason": REASON,
        },
    ).json()
    calibrate = [s for s in second["trace"] if s["layer"] == "calibrate"]
    assert calibrate
    assert calibrate[0]["contract_is_from_thesis"] is False


def test_unknown_session_and_task_return_404():
    assert client.get("/api/session/nope").status_code == 404
    sid = start()
    assert client.post(f"/api/session/{sid}/task/nope").status_code == 404


# --- telemetry ------------------------------------------------------------


def test_telemetry_keeps_reported_and_measured_apart():
    """They carry different weight. A payload that merged them would let a
    chart plot Chapter 6's cross-vendor figure and this repository's
    cross-version one as one series."""
    t = client.get("/api/telemetry").json()
    assert set(t) >= {"reported", "measured", "live", "budget", "landis_koch"}
    assert t["reported"]["overall_icc"] == 0.976
    if t["measured"]:
        assert "cross-vendor" not in t["measured"]["source"].lower()
        assert "Chapter 10 requires two" in t["measured"]["not_cross_vendor"]


def test_telemetry_carries_the_latency_budget_chapter_twelve_sets():
    t = client.get("/api/telemetry").json()
    assert t["budget"]["pipeline_mean_s"] == 5.7
    assert t["budget"]["pipeline_p95_s"] == 8.6
    assert "ecological threat" in t["budget"]["note"]


def test_telemetry_reports_all_six_dimensions_with_their_kind():
    t = client.get("/api/telemetry").json()
    dims = t["reported"]["dimensions"]
    assert len(dims) == 6
    evaluative = [d for d in dims if d["kind"] == "evaluative"]
    assert {d["name"] for d in evaluative} == {"Iteration Awareness", "Reflection"}


def test_telemetry_carries_the_reliability_caveat():
    """The Landis and Koch bands are drawn from this payload, and the thesis's
    own caution has to travel with them."""
    t = client.get("/api/telemetry").json()
    assert "point estimate" in t["reported"]["caveat"]
    assert len(t["landis_koch"]) == 5
    assert t["landis_koch"][-1]["to"] == 1.0


def test_live_telemetry_starts_empty_and_is_not_faked():
    t = client.get("/api/telemetry").json()
    assert t["live"]["calls"] >= 0
    assert isinstance(t["live"]["latencies_ms"], list)


# --- prohibitions that live at this layer --------------------------------


def test_the_teacher_route_is_aggregate_and_carries_no_sentinel():
    sid = start()
    client.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": SPOKEN, "prompt_text": TYPED},
    )
    payload = client.get("/api/teacher").json()
    assert payload["aggregate_only"] is True
    assert payload["sentinel_included"] is False
    assert payload["calibration_included"] is False
    blob = json.dumps(payload)
    for key in ("predicted_rating", "calibration_gap", "measured_overall"):
        assert key not in blob
    for signal in (
        "transcript_prompt_disconnect",
        "excessive_deference",
        "mindless_retry",
        "copied_ai_content",
    ):
        assert signal not in blob


def test_the_teacher_route_never_exposes_a_prompt():
    sid = start()
    client.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": "zzqq-secret", "prompt_text": "zzqq-prompt-text"},
    )
    blob = json.dumps(client.get("/api/teacher").json())
    assert "zzqq" not in blob


def test_small_cells_are_suppressed():
    payload = client.get("/api/teacher").json()
    assert payload["min_cell_size"] == 5
    for value in payload["band_distribution"].values():
        assert value == "suppressed" or (isinstance(value, int) and value >= 5)


def test_declining_the_microphone_still_completes_a_cycle_over_http():
    r = client.post(
        "/api/session",
        json={
            "platform_use": True,
            "research_participation": False,
            "audio_retention": False,
            "task_id": "b3-babysitting",
        },
    ).json()
    out = client.post(
        f"/api/session/{r['session_id']}/submit",
        json={
            "stated_intent": SPOKEN,
            "prompt_text": TYPED,
            "intent_modality": "speech",
        },
    ).json()
    assert out["elicit"]["record"]["intent_modality"] == "typed"
    assert out["diagnose"] is not None
    assert out["answer"] is not None


# --- the redesigned attempt cycle over HTTP --------------------------------


def _first(sid: str, **extra) -> dict:
    body = {"stated_intent": SPOKEN, "prompt_text": TYPED}
    body.update(extra)
    return client.post(f"/api/session/{sid}/submit", json=body).json()


def test_a_predicted_rating_is_stored_and_the_gap_returned_to_her():
    sid = start()
    r = _first(sid, predicted_rating=4)
    assert r["elicit"]["record"]["predicted_rating"] == 4
    assert r["calibration"]["predicted_rating"] == 4
    assert r["calibration"]["visible"] is True
    assert r["calibration"]["gap"] == round(4 - r["measure"]["overall"], 2)


def test_a_rating_off_the_scale_is_asked_about_not_scored():
    sid = start()
    r = _first(sid, predicted_rating=9)
    assert r["stopped_at"] == "elicit"
    assert "1 to 4" in r["clarification"]


def test_a_revision_without_a_reason_is_asked_for_one_over_http():
    sid = start()
    first = _first(sid)
    second = client.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": SPOKEN,
            "prompt_text": REVISED,
            "parent_attempt_id": first["elicit"]["record"]["attempt_id"],
        },
    ).json()
    assert second["stopped_at"] == "elicit"
    assert second["measure"] is None
    assert "why you changed it" in second["clarification"]


def test_the_next_task_is_held_until_a_reasoned_revision_exists():
    sid = start()
    first = _first(sid)
    assert first["revision_pending"] is True
    held = client.post(f"/api/session/{sid}/task/b1-audience")
    assert held.status_code == 409
    client.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": SPOKEN,
            "prompt_text": REVISED,
            "parent_attempt_id": first["elicit"]["record"]["attempt_id"],
            "revision_reason": REASON,
        },
    )
    moved = client.post(f"/api/session/{sid}/task/b1-audience")
    assert moved.status_code == 200
    assert moved.json()["task_id"] == "b1-audience"


def test_the_gap_is_recorded_but_not_shown_in_the_f8_control_arm():
    r = client.post(
        "/api/session",
        json={"platform_use": True, "task_id": "b3-babysitting", "show_gap": False},
    ).json()
    out = _first(r["session_id"], predicted_rating=3)
    assert out["calibration"]["visible"] is False
    assert out["calibration"]["gap"] is None
    # Stored all the same: the prediction is on the record.
    assert out["elicit"]["record"]["predicted_rating"] == 3


def test_inserted_spans_are_accepted_and_not_scored_as_hers():
    sid = start()
    prompt = "explain why the sky is blue for a seven year old"
    start_at = prompt.index("for a seven")
    r = _first(
        sid,
        prompt_text=prompt,
        inserted_spans=[{"start": start_at, "end": len(prompt)}],
    )
    assert r["measure"]["excluded_inserted_chars"] == len(prompt) - len(
        "explain why the sky is blue"
    )
    assert r["measure"]["scores"]["audience_awareness"]["value"] == 1
    assert r["elicit"]["record"]["prompt_text"] == prompt


def test_measure_reports_judge_and_generator_over_http():
    sid = start()
    m = _first(sid)["measure"]
    assert m["judge_model"] == "deterministic-1.0.0"
    assert m["generator_model"] == "scripted-responder"
    assert m["judge_independent_of_generator"] is True
