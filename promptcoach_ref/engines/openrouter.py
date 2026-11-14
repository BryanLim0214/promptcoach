"""OpenRouter-backed engine.

The request shape below was read off the live API and docs, not recalled:

    POST https://openrouter.ai/api/v1/chat/completions
    Authorization: Bearer $OPENROUTER_API_KEY
    Content-Type: application/json

    {"response_format": {"type": "json_schema",
       "json_schema": {"name": ..., "strict": true,
         "schema": {"type": "object", "properties": {...}, "required": [...],
                    "additionalProperties": false}}},
     "provider": {"require_parameters": true}}

`require_parameters` makes OpenRouter route only to endpoints that actually
honour the schema, rather than silently falling through to one that ignores it.

**Why this provider.** Layer 2's first bar is agreement between models built by
different organisations - sec:measure, "A score two models from different vendors agree
on is not an artifact of one model's idiosyncrasy". Reproducing that needs two
vendors behind one interface. `organisation` is derived from the slug prefix and
Layer 2 checks it, so pointing both scorers at the same vendor is detected and
reported rather than passed off as the cross-model bar.

Every model id lives in MODELS below. None appears at a call site.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from ..framework import ladder, rubric
from ..framework.taxonomy import BY_ID as TAXONOMY, Category
from .base import (
    ComposeRequest,
    DiagnosisRequest,
    DimensionSample,
    EngineError,
    RawAssignment,
    ScoringRequest,
    ScoringSample,
)

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

#: Verified present in GET https://openrouter.ai/api/v1/models.
MODELS: dict[str, str] = {
    #: Diagnose and Respond are the judgment-heavy layers: ranked multi-label
    #: classification, and generation inside a constraint that must not be
    #: crossed.
    "primary": "anthropic/claude-opus-5",
    #: The comparator has to be a different organisation or the agreement number
    #: means nothing. Build 1's grader A was itself Gemini-family.
    "comparator": "google/gemini-3.8-flash",
}

#: The generator answers her prompt and is configured separately from the
#: judges (policy/generator.py, PROMPTCOACH_GENERATOR): the model that writes
#: the answer she reads never scores her prompt (component 23).
GENERATOR_ENV = "PROMPTCOACH_GENERATOR"


def organisation_of(slug: str) -> str:
    return slug.split("/", 1)[0] if "/" in slug else slug


# ---------------------------------------------------------------------------
# Schemas. strict + additionalProperties:false, so a model cannot invent a
# dimension or a category and have it reach the framework.
# ---------------------------------------------------------------------------

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
                    "value": {
                        "type": ["integer", "null"],
                        "minimum": rubric.RUBRIC_MIN,
                        "maximum": rubric.RUBRIC_MAX,
                    },
                    "evidence_span": {"type": ["string", "null"]},
                },
                "required": ["dimension", "value", "evidence_span"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["dimensions"],
    "additionalProperties": False,
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
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "trigger": {"type": "string"},
                },
                "required": ["category", "confidence", "trigger"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["assignments"],
    "additionalProperties": False,
}


SCORE_SYSTEM = f"""You score a middle school student's prompt on six dimensions.

{chr(10).join(f"- {d.name} ({d.id}): {d.measures}. 1 = {d.one_against_four.split(' against ')[0]}; 4 = {d.one_against_four.split(' against ')[-1]}." for d in rubric.DIMENSIONS)}

Scale: {rubric.RUBRIC_MIN} (no evidence) to {rubric.RUBRIC_MAX} (strong).

Rules you must follow:
- Never rewrite, repair, complete or improve the student's prompt. Score it verbatim.
- Score metacognitive content, not grammar or spelling. A prompt written in a
  second language with strong content scores high. An instrument that did the
  opposite would be actively harmful.
- evidence_span must be text copied verbatim from the student's prompt. If you
  cannot find one, return null. Never paraphrase it and never invent it.
- If you cannot score a dimension, return null. Do not return 1 to mean "I could
  not tell"; those are different facts.
"""

DIAGNOSE_SYSTEM = f"""You identify which construction failures a student's prompt shows.

You are given what she said she was trying to do and what she actually typed.
The gap between them is the most informative signal available.

{chr(10).join(f"- {c.id.value}: {c.student_did}" for c in TAXONOMY.values())}

Rules:
- Return several categories in rank order. Never return exactly one. The
  categories overlap by design and a single label hides that.
- Every assignment needs a trigger: the specific observation that fired it,
  quoting her words where you can.
- Only assign a category you can point at evidence for. Assigning nothing is a
  valid answer and is better than guessing.
- Never describe the student. Describe the prompt. No trait labels.
"""


@dataclass
class OpenRouterEngine:
    slug: str
    api_key: str | None = None
    timeout: float = 60.0

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise EngineError(
                "OPENROUTER_API_KEY is not set. The deterministic engine runs the "
                "whole loop offline if you do not have one."
            )
        self.name = f"openrouter:{self.slug}"
        self.organisation = organisation_of(self.slug)

    # -- transport -------------------------------------------------------

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise EngineError(f"transport failure: {exc}") from exc

        if response.status_code >= 400:
            raise EngineError(f"HTTP {response.status_code}: {response.text[:400]}")

        try:
            return response.json()
        except ValueError as exc:
            raise EngineError(f"non-JSON response: {exc}") from exc

    def _structured(
        self, system: str, user: str, schema_name: str, schema: dict, temperature: float
    ) -> dict[str, Any]:
        data = self._post(
            {
                "model": self.slug,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                },
                "provider": {"require_parameters": True},
            }
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise EngineError(f"unexpected response shape: {exc}") from exc
        try:
            return json.loads(content)
        except ValueError as exc:
            raise EngineError(f"model returned invalid JSON: {exc}") from exc

    # -- Engine ----------------------------------------------------------

    def sample_scores(
        self, request: ScoringRequest, temperature: float
    ) -> ScoringSample:
        user = (
            f"Task the student was given:\n{request.task_scenario}\n\n"
            f"What she said she was trying to do:\n{request.stated_intent}\n\n"
            f"What she typed:\n{request.prompt_text}"
        )
        payload = self._structured(
            SCORE_SYSTEM, user, "rubric_scores", SCORE_SCHEMA, temperature
        )

        seen: dict[str, DimensionSample] = {}
        for row in payload.get("dimensions", []):
            dim_id = row.get("dimension")
            # A dimension the model invented never reaches the framework.
            if dim_id not in rubric.BY_ID:
                continue
            seen[dim_id] = DimensionSample(
                dimension_id=dim_id,
                value=row.get("value"),
                evidence_span=row.get("evidence_span"),
            )

        for dim in rubric.DIMENSIONS:
            seen.setdefault(
                dim.id, DimensionSample(dimension_id=dim.id, value=None)
            )

        return ScoringSample(
            judge=self.name,
            temperature=temperature,
            dimensions=tuple(seen[d.id] for d in rubric.DIMENSIONS),
        )

    def diagnose(self, request: DiagnosisRequest) -> list[RawAssignment]:
        history = "\n".join(f"  - {h}" for h in request.history) or "  (none)"
        user = (
            f"What she said she was trying to do ({request.intent_modality}):\n"
            f"{request.stated_intent}\n\n"
            f"What she typed:\n{request.prompt_text}\n\n"
            f"Her earlier prompts this session:\n{history}\n\n"
            f"Her scores: {json.dumps(request.scores)}"
        )
        payload = self._structured(
            DIAGNOSE_SYSTEM, user, "diagnosis", DIAGNOSE_SCHEMA, 0.2
        )

        out: list[RawAssignment] = []
        for row in payload.get("assignments", []):
            try:
                category = Category(row["category"])
            except (KeyError, ValueError):
                # A category the model invented is discarded.
                continue
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

    def compose(self, request: ComposeRequest) -> str | None:
        """Generate within the level's constraint.

        The constraint is restated here, but it is *enforced* by
        `layers.respond.validate` over the returned text. sec:respond - "The constraint
        lives in code, not in the model's instructions." A model that ignores
        this prompt produces a rejected response and the template floor is served.
        """
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
            "- Never supply a missing element on her behalf. Naming a concrete "
            "audience, length, format or constraint she left out means you have "
            "written that part of her prompt.\n"
            f"- Never make this decision for her: {request.protected_judgment}\n"
            "- Address one failure only. Listing all six dimensions is a report "
            "card, not coaching.\n"
            "- Speak to a twelve year old. Short sentences, no jargon.\n"
        )
        if level.number == 1:
            system += "- Your entire response is one question. End with '?'.\n"
        elif level.number == 2:
            system += (
                f"- Name the dimension at fault ({dim.name if dim else 'the weak part'}) "
                "without saying what to add.\n"
            )
        elif level.number == 3:
            system += (
                "- Show her prompt back with the weak part marked by a blank slot. "
                "Do not fill the slot.\n"
            )
        else:
            system += (
                "- Give two prompts labelled 'A.' and 'B.' differing only on that "
                "dimension, then ask her which is better and why, and require her "
                "to write a new prompt of her own.\n"
            )

        user = (
            f"What she said:\n{request.stated_intent}\n\n"
            f"What she typed:\n{request.prompt_text}"
        )

        data = self._post(
            {
                "model": self.slug,
                "temperature": 0.3,
                "max_tokens": 600,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        )
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            return None


    # -- what she came for -----------------------------------------------

    def answer(self, prompt_text: str, max_tokens: int = 700) -> str:
        """Run her prompt as written. No coaching, no repair."""
        data = self._post(
            {
                "model": self.slug,
                "temperature": 0.7,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are the assistant a middle school student is "
                            "practising on. Answer exactly what she asked, no "
                            "more. Do not coach her, do not comment on her "
                            "prompt, and do not ask what she meant."
                        ),
                    },
                    {"role": "user", "content": prompt_text},
                ],
            }
        )
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise EngineError(f"unexpected response shape: {exc}") from exc


def build(role: str = "primary", generator_model: str | None = None, **kwargs: Any) -> OpenRouterEngine:
    """`role="generator"` takes `generator_model`, else PROMPTCOACH_GENERATOR,
    else the policy default - never the judge's slug."""
    if role == "generator":
        from ..policy import generator as generator_policy

        slug = generator_model or generator_policy.model_for("openrouter")
        return OpenRouterEngine(slug=slug, **kwargs)
    return OpenRouterEngine(slug=MODELS[role], **kwargs)


def available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))
