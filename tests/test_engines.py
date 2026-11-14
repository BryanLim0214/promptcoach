"""The live-model adapters, exercised against a fake transport.

No network. `httpx.MockTransport` lets the real request-building and
response-parsing code run against scripted replies, so these cover the parts
that actually go wrong: a model inventing a dimension, returning a value off the
scale, fabricating an evidence span, refusing, or timing out.

The rule these enforce is that nothing a model returns is trusted. Every one of
those failures has to be caught before it reaches the framework, because the
framework's guarantees are only worth what its inputs are.
"""

from __future__ import annotations

import json

import httpx
import pytest

from promptcoach_ref.engines.base import (
    ComposeRequest,
    DiagnosisRequest,
    EngineError,
    ScoringRequest,
)
from promptcoach_ref.engines.gemini import GeminiEngine
from promptcoach_ref.framework import rubric
from promptcoach_ref.framework.taxonomy import Category

pytestmark = pytest.mark.engine


def gemini_reply(payload: dict | str) -> httpx.Response:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
        },
    )


def engine_with(handler) -> GeminiEngine:
    e = GeminiEngine(
        model="test-model",
        api_key="fake-key",
        read_env_file=False,
        backoff_base=0.001,
    )
    e._client = httpx.Client(transport=httpx.MockTransport(handler))
    return e


def scoring_request() -> ScoringRequest:
    return ScoringRequest(
        prompt_text="explain why the sky is blue",
        stated_intent="telling my cousin, she is seven",
        task_scenario="",
    )


# --- what the model returns is never trusted ------------------------------


def test_a_dimension_the_model_invents_is_discarded():
    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_reply(
            {
                "dimensions": [
                    {"dimension": "specificity", "value": 3, "evidence_span": ""},
                    {"dimension": "vibes", "value": 4, "evidence_span": ""},
                ]
            }
        )

    sample = engine_with(handler).sample_scores(scoring_request(), 0.2)
    ids = {d.dimension_id for d in sample.dimensions}
    assert "vibes" not in ids
    assert ids == {d.id for d in rubric.DIMENSIONS}


def test_a_dimension_the_model_omits_becomes_none_not_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_reply(
            {"dimensions": [{"dimension": "specificity", "value": 3, "evidence_span": ""}]}
        )

    sample = engine_with(handler).sample_scores(scoring_request(), 0.2)
    by_id = {d.dimension_id: d for d in sample.dimensions}
    assert by_id["specificity"].value == 3
    assert by_id["reflection"].value is None


def test_an_empty_evidence_span_becomes_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_reply(
            {
                "dimensions": [
                    {"dimension": "specificity", "value": 2, "evidence_span": "   "}
                ]
            }
        )

    sample = engine_with(handler).sample_scores(scoring_request(), 0.2)
    by_id = {d.dimension_id: d for d in sample.dimensions}
    assert by_id["specificity"].evidence_span is None


def test_an_out_of_range_value_survives_the_engine_and_dies_at_the_layer():
    """The engine passes it through; MeasureLayer discards it. Checking both
    ends means neither can quietly start clamping."""
    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_reply(
            {"dimensions": [{"dimension": "specificity", "value": 9, "evidence_span": ""}]}
        )

    sample = engine_with(handler).sample_scores(scoring_request(), 0.2)
    by_id = {d.dimension_id: d for d in sample.dimensions}
    assert by_id["specificity"].value == 9

    from promptcoach_ref.framework.contracts import MeasureInput, PairedRecord
    from promptcoach_ref.layers import MeasureLayer

    layer = MeasureLayer(engine_with(handler))
    record = PairedRecord(
        attempt_id="a",
        task_id="t",
        stated_intent="i",
        prompt_text="explain why the sky is blue",
        intent_modality="typed",
        transcript_reviewed=True,
        student_ms=0,
        system_ms=0,
    )
    out = layer.run(MeasureInput(record=record))
    assert out.overall is None
    assert all(s.unable_to_score for s in out.scores.values())


def test_a_category_the_model_invents_is_discarded():
    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_reply(
            {
                "assignments": [
                    {"category": "intent_drift", "confidence": 0.9, "trigger": "t"},
                    {"category": "student_is_lazy", "confidence": 1.0, "trigger": "t"},
                ]
            }
        )

    out = engine_with(handler).diagnose(
        DiagnosisRequest(
            prompt_text="p",
            stated_intent="i",
            intent_modality="typed",
            scores={},
            task_scenario="",
        )
    )
    assert [a.category for a in out] == [Category.INTENT_DRIFT]


def test_an_assignment_with_no_trigger_is_discarded():
    """sec:diagnose requires confidence and evidence. An assignment nobody can point at
    is not reportable to a student."""
    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_reply(
            {
                "assignments": [
                    {"category": "intent_drift", "confidence": 0.9, "trigger": "  "}
                ]
            }
        )

    out = engine_with(handler).diagnose(
        DiagnosisRequest(
            prompt_text="p",
            stated_intent="i",
            intent_modality="typed",
            scores={},
            task_scenario="",
        )
    )
    assert out == []


# --- failures stay failures -----------------------------------------------


def test_invalid_json_raises_rather_than_returning_a_guess():
    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_reply("this is not json at all")

    with pytest.raises(EngineError, match="invalid JSON"):
        engine_with(handler).sample_scores(scoring_request(), 0.2)


def test_a_transport_failure_raises_engine_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with pytest.raises(EngineError, match="transport failure"):
        engine_with(handler).sample_scores(scoring_request(), 0.2)


def test_a_blocked_response_raises_rather_than_scoring_nothing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY"}]})

    with pytest.raises(EngineError, match="no content"):
        engine_with(handler).sample_scores(scoring_request(), 0.2)


def test_compose_returns_none_on_failure_so_the_template_floor_takes_over():
    """sec:respond - the floor is served "whenever the model call fails". A raised
    exception here would break the loop instead of falling back."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream on fire")

    out = engine_with(handler).compose(
        ComposeRequest(
            level=1,
            category=Category.INTENT_DRIFT,
            prompt_text="p",
            stated_intent="i",
            weakest_dimension_id=rubric.AUDIENCE_AWARENESS.id,
            protected_judgment="what counts as a good explanation",
        )
    )
    assert out is None


def test_rate_limiting_is_retried_then_reported():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text="quota")

    e = engine_with(handler)
    with pytest.raises(EngineError, match="429"):
        e.sample_scores(scoring_request(), 0.2)
    assert calls["n"] > 1, "a 429 must be retried, not dropped"
    assert e.errors.get("rate_limited", 0) >= 1


def test_errors_are_counted_so_a_run_cannot_silently_lose_cases():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="nope")

    e = engine_with(handler)
    with pytest.raises(EngineError):
        e.sample_scores(scoring_request(), 0.2)
    assert e.stats()["errors"]["http_500"] == 1


# --- the request itself ---------------------------------------------------


def test_the_request_carries_the_schema_and_the_temperature():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return gemini_reply({"dimensions": []})

    engine_with(handler).sample_scores(scoring_request(), 0.5)
    config = seen["generationConfig"]
    assert config["temperature"] == 0.5
    assert config["responseMimeType"] == "application/json"
    assert config["responseSchema"]["properties"]["dimensions"]["items"]["properties"][
        "dimension"
    ]["enum"] == [d.id for d in rubric.DIMENSIONS]


def test_the_scoring_prompt_forbids_repairing_her_prompt():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return gemini_reply({"dimensions": []})

    engine_with(handler).sample_scores(scoring_request(), 0.2)
    system = seen["systemInstruction"]["parts"][0]["text"].lower()
    assert "never rewrite" in system
    assert "verbatim" in system


def test_the_compose_prompt_names_the_protected_judgment():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return gemini_reply("Which part matters most?")

    engine_with(handler).compose(
        ComposeRequest(
            level=1,
            category=Category.UNDER_SPECIFICATION,
            prompt_text="p",
            stated_intent="i",
            weakest_dimension_id=rubric.AUDIENCE_AWARENESS.id,
            protected_judgment="which weakness is worth fixing",
        )
    )
    system = seen["systemInstruction"]["parts"][0]["text"]
    assert "which weakness is worth fixing" in system
    assert "may not close it" in system


def test_the_answer_path_does_not_coach_or_repair():
    """The student has to receive the answer her actual prompt deserves. A
    system prompt that improved it first would destroy the only lesson the
    application teaches."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return gemini_reply("The sky is blue because of scattering.")

    engine_with(handler).answer("explain why the sky is blue")
    system = seen["systemInstruction"]["parts"][0]["text"].lower()
    assert "do not coach" in system
    assert "vague" in system
    assert seen["contents"][0]["parts"][0]["text"] == "explain why the sky is blue"


def test_every_gemini_model_reports_the_same_organisation():
    """Layer 2 checks this before calling anything the cross-model bar. Two
    Gemini versions are not two vendors."""
    a = GeminiEngine(model="gemini-3.1-flash-lite", api_key="k", read_env_file=False)
    b = GeminiEngine(model="gemini-3.8-flash", api_key="k", read_env_file=False)
    assert a.organisation == b.organisation == "google"


def test_a_missing_key_fails_loudly_at_construction(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(EngineError, match="GEMINI_API_KEY"):
        GeminiEngine(model="m", api_key="", read_env_file=False)


def test_a_project_env_file_beats_a_stale_machine_variable(tmp_path, monkeypatch):
    """A machine-wide GEMINI_API_KEY left over from another project shadowed
    this one's and produced 90 consecutive HTTP 400s that read like rate
    limiting. The project-local file is the more specific statement of intent."""
    from promptcoach_ref.engines.gemini import load_env

    monkeypatch.setenv("GEMINI_API_KEY", "stale-machine-key")
    env = tmp_path / ".env"
    env.write_text("# comment\nGEMINI_API_KEY=project-key\n", encoding="utf-8")
    load_env(env)
    import os

    assert os.environ["GEMINI_API_KEY"] == "project-key"
