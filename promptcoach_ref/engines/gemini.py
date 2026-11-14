"""Gemini-backed engine.

Model choice reproduces Build 1 rather than picking by preference:

    sec:build1 - "For the cross model comparison, PatternLens was
    configured on Gemini 3.1 Flash-Lite and run as the three judge ensemble."

so `SCORER` is `gemini-3.1-flash-lite`. The same passage gives the deployment
configuration as Gemini 3.1 Pro, which is `AGENT` - but see the latency note
below before using it on the scoring path.

Measured on this key, three calls each, structured output, same 115-token input:

    gemini-3.1-flash-lite     1242 ms mean
    gemini-3.8-flash          3231 ms mean
    gemini-3.1-pro-preview   11896 ms mean

sec:threats gives the whole five-agent pipeline a budget of
5.7 s mean and 8.6 s at the 95th percentile, and warns it "may exceed middle
school patience". A single Pro call is roughly twice the entire P95 budget, so
Pro is not used for per-attempt scoring here. That is a measurement, not a
preference.

Structured output uses `responseMimeType: application/json` with a
`responseSchema`, which constrains the shape at the API rather than in the
prompt - the same reason the OpenRouter engine uses `strict: true`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..framework import ladder, rubric
from ..framework.taxonomy import BY_ID as TAXONOMY, Category
from ..policy.response import MAX_MOVES
from .base import (
    ComposeRequest,
    DiagnosisRequest,
    DimensionSample,
    EngineError,
    RawAssignment,
    ScoringRequest,
    ScoringSample,
)

BASE = "https://generativelanguage.googleapis.com/v1beta/models"

#: Build 1's cross-model grader A. Fast and cheap enough to run as a three-judge
#: ensemble on every attempt.
SCORER = "gemini-3.1-flash-lite"
#: Build 1's deployment configuration. Measured at ~11.9 s per call.
AGENT = "gemini-3.1-pro-preview"
#: A current mid-tier alternative, used as the cross-version comparator.
COMPARATOR = "gemini-3.8-flash"
#: The generator - the model that answers her prompt - is a separate setting
#: from the scorer (policy/generator.py, PROMPTCOACH_GENERATOR), so the judge is
#: never the model whose output she read (component 23).
GENERATOR_ENV = "PROMPTCOACH_GENERATOR"


def load_env(path: Path | None = None, override: bool = True) -> None:
    """Read .env if present. No dependency on python-dotenv.

    `override` defaults to True, which is the opposite of the usual convention
    and deliberate: a machine-wide GEMINI_API_KEY left over from another project
    silently shadowed this one's and produced 90 consecutive HTTP 400s that
    looked like rate limiting. A project-local .env is the more specific
    statement of intent, so it wins.
    """
    path = path or Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "dimensions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dimension": {
                        "type": "string",
                        "enum": [d.id for d in rubric.DIMENSIONS],
                    },
                    "value": {"type": "integer"},
                    "evidence_span": {"type": "string"},
                },
                "required": ["dimension", "value", "evidence_span"],
            },
        }
    },
    "required": ["dimensions"],
}

DIAGNOSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [c.value for c in Category],
                    },
                    "confidence": {"type": "number"},
                    "trigger": {"type": "string"},
                },
                "required": ["category", "confidence", "trigger"],
            },
        }
    },
    "required": ["assignments"],
}

SENTINEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "signal": {
                        "type": "string",
                        "enum": [
                            "transcript_prompt_disconnect",
                            "excessive_deference",
                            "mindless_retry",
                            "copied_ai_content",
                        ],
                    },
                    "value": {"type": "number"},
                },
                "required": ["signal", "value"],
            },
        }
    },
    "required": ["signals"],
}


def _anchors() -> str:
    rows = []
    for d in rubric.DIMENSIONS:
        low, _, high = d.one_against_four.partition(" against ")
        rows.append(f"- {d.id} ({d.name}): {d.measures}. 1 = {low}. 4 = {high}.")
    return "\n".join(rows)


SCORE_SYSTEM = f"""You score a middle school student's prompt on six dimensions.

{_anchors()}

Scale: {rubric.RUBRIC_MIN} (no evidence) to {rubric.RUBRIC_MAX} (strong).

Rules:
- Never rewrite, repair or complete her prompt. Score it exactly as written.
- Score metacognitive content, not grammar or spelling. A prompt written in a
  second language with strong content scores high.
- evidence_span must be copied verbatim from her prompt. If there is none, use
  an empty string. Never paraphrase it and never invent it.
- Reason about each dimension before committing to its number.
"""

DIAGNOSE_SYSTEM = f"""You identify which construction failures a prompt shows.

You get two records: what she SAID she was trying to do, and what she actually
TYPED. Comparing them is the first thing you do, and it is the reason you are
given both.

Work in this order.

1. List what her spoken account contains: who the answer is for, how long it
   should be, what it must avoid, why she wants it, what would make it good.
2. Check each one against her typed prompt.
3. If something is present in what she said and absent from what she typed,
   that is INTENT DRIFT, and it outranks every other category. She is not
   missing the knowledge; she failed to transfer it, and those two failures
   need opposite responses. Under-specification means teaching her what a
   prompt should contain. Intent drift means pointing out that she already
   knew.
4. Only if nothing was dropped should under-specification be your top category.

The categories:

{chr(10).join(f"- {c.id.value}: {c.student_did}" for c in TAXONOMY.values())}

Rules:
- Return several categories in rank order, most confident first. Never exactly
  one; the categories overlap by design.
- Every assignment needs a trigger: the observation that fired it. For intent
  drift, name the specific things she said aloud and did not type.
- Only assign what you can point at evidence for. Returning nothing is valid.
- Describe the prompt, never the student. No trait labels.
"""

SENTINEL_SYSTEM = """Rate four over-reliance signals from 0 to 1.

- transcript_prompt_disconnect: she describes one intention aloud and types
  something generic.
- excessive_deference: judgment offloaded, as in asking the tool to just make it
  good.
- mindless_retry: a prior response rejected and resubmitted without diagnosis.
- copied_ai_content: phrasing pasted from a previous model output, not composed.

These are values to show her, not a verdict on her. Rate what the evidence
supports and use 0 when there is none.
"""


@dataclass
class GeminiEngine:
    model: str = SCORER
    api_key: str | None = None
    timeout: float = 120.0
    #: Seconds to wait before the first 429 retry, doubling thereafter. Kept as
    #: a field so tests can exercise the retry path without sleeping through it.
    backoff_base: float = 2.0
    #: Skip reading .env. Tests use this to assert the no-credentials path.
    read_env_file: bool = True
    #: Every call's latency, so a run can report the distribution rather than a
    #: single number. sec:threats makes latency an ecological threat, not a footnote.
    latencies_ms: list[float] = field(default_factory=list)
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    #: Counted by kind. A run that silently dropped a third of its calls would
    #: report a mean over whatever survived, which is a different number than it
    #: appears to be.
    errors: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.read_env_file:
            load_env()
        self.api_key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise EngineError("GEMINI_API_KEY is not set")
        self.name = f"gemini:{self.model}"
        #: Every Gemini model is one vendor. Layer 2 checks this before calling
        #: anything the cross-model bar.
        self.organisation = "google"
        self._client = httpx.Client(timeout=self.timeout)

    # -- transport -------------------------------------------------------

    def _generate(
        self,
        system: str,
        user: str,
        temperature: float,
        schema: dict | None = None,
        max_output_tokens: int = 2048,
    ) -> tuple[str, float]:
        config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        if schema is not None:
            config["responseMimeType"] = "application/json"
            config["responseSchema"] = schema

        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": config,
        }

        # A 429 is a quota signal, not a failure of the method. Back off and
        # retry rather than dropping the case, because a benchmark that silently
        # loses its rate-limited cases reports a mean over a biased remainder.
        attempts = 4
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                response = self._client.post(
                    f"{BASE}/{self.model}:generateContent",
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": self.api_key or "",
                    },
                    json=body,
                )
            except httpx.HTTPError as exc:
                self._note("transport")
                raise EngineError(f"transport failure: {exc}") from exc
            elapsed_ms = (time.perf_counter() - started) * 1000

            if response.status_code == 429 and attempt < attempts - 1:
                self._note("rate_limited")
                time.sleep(self.backoff_base * (2 ** attempt))
                continue
            break

        if response.status_code >= 400:
            self._note(f"http_{response.status_code}")
            raise EngineError(f"HTTP {response.status_code}: {response.text[:300]}")

        payload = response.json()
        usage = payload.get("usageMetadata", {})
        self.calls += 1
        self.input_tokens += usage.get("promptTokenCount", 0) or 0
        self.output_tokens += usage.get("candidatesTokenCount", 0) or 0
        self.latencies_ms.append(elapsed_ms)

        try:
            parts = payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as exc:
            finish = (payload.get("candidates") or [{}])[0].get("finishReason")
            self._note(f"no_content_{finish}")
            raise EngineError(f"no content (finishReason={finish})") from exc

        return "".join(p.get("text", "") for p in parts), elapsed_ms

    def _note(self, kind: str) -> None:
        self.errors[kind] = self.errors.get(kind, 0) + 1

    def _json(self, system: str, user: str, temperature: float, schema: dict) -> dict:
        text, _ = self._generate(system, user, temperature, schema)
        try:
            return json.loads(text)
        except ValueError as exc:
            raise EngineError(f"model returned invalid JSON: {exc}") from exc

    # -- Engine ----------------------------------------------------------

    def sample_scores(
        self, request: ScoringRequest, temperature: float
    ) -> ScoringSample:
        user = (
            f"What she said she was trying to do:\n{request.stated_intent}\n\n"
            f"What she typed:\n{request.prompt_text}"
        )
        payload = self._json(SCORE_SYSTEM, user, temperature, SCORE_SCHEMA)

        seen: dict[str, DimensionSample] = {}
        for row in payload.get("dimensions", []):
            dim_id = row.get("dimension")
            if dim_id not in rubric.BY_ID:
                continue  # a dimension the model invented never reaches Layer 2
            span = (row.get("evidence_span") or "").strip() or None
            seen[dim_id] = DimensionSample(
                dimension_id=dim_id, value=row.get("value"), evidence_span=span
            )

        for dim in rubric.DIMENSIONS:
            seen.setdefault(dim.id, DimensionSample(dimension_id=dim.id, value=None))

        return ScoringSample(
            judge=self.name,
            temperature=temperature,
            dimensions=tuple(seen[d.id] for d in rubric.DIMENSIONS),
            latency_ms=int(self.latencies_ms[-1]) if self.latencies_ms else 0,
        )

    def diagnose(self, request: DiagnosisRequest) -> list[RawAssignment]:
        history = "\n".join(f"  - {h}" for h in request.history) or "  (none)"
        user = (
            f"What she said ({request.intent_modality}):\n{request.stated_intent}\n\n"
            f"What she typed:\n{request.prompt_text}\n\n"
            f"Her earlier prompts this session:\n{history}"
        )
        payload = self._json(DIAGNOSE_SYSTEM, user, 0.2, DIAGNOSE_SCHEMA)

        out: list[RawAssignment] = []
        for row in payload.get("assignments", []):
            try:
                category = Category(row["category"])
            except (KeyError, ValueError):
                continue  # a category the model invented is discarded
            trigger = str(row.get("trigger", "")).strip()
            if not trigger:
                continue
            out.append(
                RawAssignment(
                    category=category,
                    confidence=float(row.get("confidence", 0.0)),
                    trigger=trigger,
                )
            )
        return out

    @property
    def SENTINEL_SOURCE(self) -> str:  # noqa: N802 - read like the class constant elsewhere
        return (
            f"model-based detector ({self.name}); the detector eval/benchmark.py "
            "measures"
        )

    def sentinel(self, stated_intent: str, prompt_text: str, history: tuple[str, ...]) -> dict[str, float]:
        """The model-based over-reliance detector.

        This is the detector `eval/benchmark.py` scores (`scorer.sentinel`), the
        one the replication AUC describes. In a live session Layer 5 calls it
        on the judge engine (`layers/calibrate.py`).
        """
        past ="\n".join(f"  - {h}" for h in history) or "  (none)"
        user = (
            f"What she said:\n{stated_intent}\n\nWhat she typed:\n{prompt_text}\n\n"
            f"Her earlier prompts:\n{past}"
        )
        payload = self._json(SENTINEL_SYSTEM, user, 0.2, SENTINEL_SCHEMA)
        out: dict[str, float] = {}
        for row in payload.get("signals", []):
            name = row.get("signal")
            if name:
                out[name] = max(0.0, min(1.0, float(row.get("value", 0.0))))
        return out

    def compose(self, request: ComposeRequest) -> str | None:
        level = ladder.BY_NUMBER[request.level]
        category = TAXONOMY[request.category]
        dim = rubric.BY_ID.get(request.weakest_dimension_id)

        system = (
            "You are coaching a middle school student on the prompt she just "
            "wrote. You are not writing it for her.\n\n"
            f"Diagnosed failure: {category.name} - {category.student_did}\n"
            f"The response this implies: {category.response_implied}\n"
            f"Help level {level.number}: {level.gives}\n"
            f"What she must still do: {level.student_still_does}\n\n"
            "Absolute rules:\n"
            "- You may narrow her search space. You may not close it.\n"
            "- Never supply a missing element for her. Inventing a concrete "
            "audience, length, format or constraint she never mentioned means "
            "you have written that part of her prompt.\n"
            "- Quoting back something she said out loud herself is not "
            "supplying it. It is the one move that shows her the gap, so use "
            "her own words when she gave you words to use.\n"
            f"- Never make this decision for her: {request.protected_judgment}\n"
            "- Address one failure only.\n"
            "- Speak to a twelve year old. Short sentences, no jargon.\n"
            f"- At most {MAX_MOVES[level.number]} sentences in total.\n"
        )
        if request.dropped_from_intent:
            said = ", ".join(
                rubric.BY_ID[d].name
                for d in request.dropped_from_intent
                if d in rubric.BY_ID
            )
            system += (
                f"- She said these out loud and left them out of the prompt: "
                f"{said}. Name them in her words, not the rubric's.\n"
            )
        if level.number == 1:
            system += "- Your whole reply is one question. End with '?'.\n"
        elif level.number == 2:
            system += (
                f"- Name the dimension at fault ({dim.name if dim else 'the weak part'}) "
                "without saying what to add.\n"
            )
        elif level.number == 3:
            system += (
                "- Show her prompt back with the weak part marked by a blank slot "
                "written as ____. Do not fill it.\n"
            )
        else:
            system += (
                "- Give two prompts labelled 'A.' and 'B.' differing only on that "
                "dimension, then ask which is better and why, and require her to "
                "write a new prompt of her own.\n"
            )

        user = (
            f"What she said:\n{request.stated_intent}\n\n"
            f"What she typed:\n{request.prompt_text}"
        )
        try:
            text, _ = self._generate(system, user, 0.3, None, max_output_tokens=700)
        except EngineError:
            return None
        return text.strip() or None

    # -- what she came for -----------------------------------------------

    def answer(self, prompt_text: str, max_output_tokens: int = 700) -> str:
        """Run the student's prompt as written and return what it produced.

        Deliberately no system prompt beyond a safety frame: the point of the
        whole application is that a vague prompt produces a vague answer, and
        quietly improving her prompt before sending it would destroy the lesson.
        """
        system = (
            "You are the assistant a middle school student is practising on. "
            "Answer exactly what she asked, no more. Do not coach her, do not "
            "comment on her prompt, and do not ask what she meant. If her "
            "request is vague, give the answer that vague request deserves."
        )
        text, _ = self._generate(system, prompt_text, 0.7, None, max_output_tokens)
        return text.strip()

    # -- run accounting --------------------------------------------------

    def stats(self) -> dict[str, Any]:
        import statistics

        lat = sorted(self.latencies_ms)
        return {
            "model": self.model,
            "calls": self.calls,
            "errors": dict(self.errors),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_mean_ms": round(statistics.fmean(lat), 1) if lat else None,
            "latency_p95_ms": round(lat[int(len(lat) * 0.95) - 1], 1) if lat else None,
            "latency_max_ms": round(max(lat), 1) if lat else None,
        }


def build(role: str = "scorer", generator_model: str | None = None, **kwargs: Any) -> GeminiEngine:
    """Build an engine for one role.

    `role="generator"` builds the engine that answers her prompt. Its model is
    `generator_model` if given, else PROMPTCOACH_GENERATOR, else the policy
    default - never the scorer's setting.
    """
    from ..policy import generator as generator_policy

    load_env()
    model = {
        "scorer": lambda: os.environ.get("PROMPTCOACH_SCORER", SCORER),
        "agent": lambda: os.environ.get("PROMPTCOACH_AGENT", AGENT),
        "comparator": lambda: COMPARATOR,
        "generator": lambda: generator_model or generator_policy.model_for("gemini"),
    }[role]()
    return GeminiEngine(model=model, **kwargs)


def available() -> bool:
    load_env()
    return bool(os.environ.get("GEMINI_API_KEY"))
