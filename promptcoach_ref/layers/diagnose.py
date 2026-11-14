"""Layer 3 - Diagnose.

    "A score says how weak an artifact is. It does not say what went wrong, and
    therefore cannot select a response."
    - sec:diagnose

    "Requirement passed downstream: a ranked list of failure categories with
    confidence."
    - sec:diagnose

This layer reads Layer 1 directly, not only Layer 2. That is the DAG edge, and
sec:diagnose gives the reason: four of the seven categories - intent drift, blind
acceptance, undiagnosed retry, borrowed phrasing - "cannot be detected from the
prompt text alone".

The output is a ranked list and never a single label. sec:diagnose:

    "The categories overlap... The framework therefore requires the diagnosis to
    return several categories in rank order and never a single label, and
    requires the response layer to act on the top ranked failure only."

**Layer 3 does not read the over-reliance sentinel.** Four categories are
derived from sentinel signals (intent drift, undiagnosed retry, delegated
judgment, borrowed phrasing), but Layer 3 detects them with its own rules over
the plan (`stated_intent`), the prompt and the session history: the rule set in
`DeterministicEngine.diagnose` offline, and the judge model's diagnosis call,
with its own instructions, live. The sentinel is computed afterwards, in Layer
5, and goes only to the student.

**Help already given is part of the history.** Blind acceptance needs to know
that an earlier attempt received help. The session records, on each attempt,
the help response that preceded it (`triggering_intervention_id`), and this
layer passes "help was given earlier on this task" to the diagnosis when the
attempt or any earlier one carries it. Before this was recorded, blind
acceptance could not fire through `Session.submit` at all.

Below-threshold observations are kept in the reason trace rather than dropped, so
"the system saw this and did not act on it" stays visible. Insufficient evidence
is a distinct outcome from no failure; conflating them would let the system claim
a clean prompt whenever it simply could not tell.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..engines.base import DiagnosisRequest, Engine, EngineError
from ..framework.contracts import (
    CategoryAssignment,
    DiagnoseInput,
    DiagnoseOutput,
)
from ..framework.taxonomy import BY_ID as TAXONOMY, Category
from ..policy import classifier


@dataclass
class DiagnoseLayer:
    READS: tuple[str, ...] = ("elicit", "measure", "history")

    engine: Engine = None  # type: ignore[assignment]
    fallback: Engine | None = None

    def __init__(self, engine: Engine, fallback: Engine | None = None) -> None:
        self.engine = engine
        self.fallback = fallback

    def run(self, data: DiagnoseInput) -> DiagnoseOutput:
        record = data.record
        # Diagnose reads what she composed. A chip the interface inserted is not
        # evidence about her construction (component 24).
        request = DiagnosisRequest(
            prompt_text=record.composed_text,
            stated_intent=record.stated_intent,
            intent_modality=record.intent_modality,
            scores={k: v.value for k, v in data.scores.items()},
            task_scenario="",
            history=tuple(h.composed_text for h in data.session_history),
            # Help was given before this attempt: either this attempt follows a
            # help response, or an earlier one in the history did.
            history_had_intervention=bool(record.triggering_intervention_id)
            or any(h.triggering_intervention_id for h in data.session_history),
        )

        trace: list[str] = []

        try:
            raw = self.engine.diagnose(request)
        except EngineError as exc:
            if self.fallback is None:
                raise
            trace.append(
                f"primary engine failed ({exc}); fell back to {self.fallback.name}"
            )
            raw = self.fallback.diagnose(request)

        if record.inserted_spans:
            trace.append(
                "part of the prompt was inserted by the interface; only the text "
                "she composed was read"
            )

        if record.intent_is_degraded:
            trace.append(
                "intent was typed rather than spoken, so the paired record is at "
                "lower fidelity and intent drift is harder to see"
            )

        scored: dict[Category, tuple[float, str]] = {}
        for item in raw:
            existing = scored.get(item.category)
            if existing is None or item.confidence > existing[0]:
                scored[item.category] = (item.confidence, item.trigger)

        ranked = classifier.rank(scored)
        dropped = classifier.below_threshold(scored)

        for cat, conf, trigger in dropped:
            trace.append(
                f"{cat.value} seen at confidence {conf:.2f}, below the threshold of "
                f"{classifier.MIN_CONFIDENCE}: recorded as insufficient evidence, "
                f"not as a failure ({trigger})"
            )

        if not ranked:
            return DiagnoseOutput(
                assignments=(),
                target=None,
                insufficient_evidence=bool(dropped),
                reason_trace=tuple(
                    trace
                    or ["no category cleared its trigger; nothing to respond to"]
                ),
            )

        top_ids = {cat for cat, _, _ in ranked}
        assignments: list[CategoryAssignment] = []
        for rank_index, (cat, conf, trigger) in enumerate(ranked, start=1):
            overlaps = tuple(sorted(top_ids - {cat}, key=lambda c: c.value))
            if overlaps:
                trace.append(
                    f"{cat.value} co-occurs with "
                    + ", ".join(c.value for c in overlaps)
                )
            assignments.append(
                CategoryAssignment(
                    category=cat,
                    rank=rank_index,
                    confidence=conf,
                    trigger=trigger,
                    overlaps_with=overlaps,
                )
            )

        target = assignments[0].category
        trace.append(
            f"responding to {target.value} only: "
            + TAXONOMY[target].response_implied
        )

        return DiagnoseOutput(
            assignments=tuple(assignments),
            target=target,
            insufficient_evidence=False,
            reason_trace=tuple(trace),
        )


#: sec:diagnose. Kept beside the code that applies it, because a
#: reader of this layer should know the categories were read off the instrument
#: they are being detected with.
DERIVATION_NOTE = (
    "The taxonomy is derived, not invented. Each category traces to at least one "
    "of: a rubric dimension from Build 1, an over reliance signal from Build 1, or "
    "a documented finding in the literature. The derivation is close to circular, "
    "and the taxonomy cannot be validated by showing that the system can apply it."
)
