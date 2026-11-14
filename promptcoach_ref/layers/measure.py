"""Layer 2 - Measure.

    "Requirement passed downstream: six dimension scores with per dimension
    confidence."
    - sec:measure

The layer's real content is three bars, not the rubric (sec:measure):

  1. cross model agreement - cleared at ICC 0.976 on 30 items
  2. paraphrase invariance - cleared at 0.134 points of movement
  3. agreement with a human rater - **not cleared**

The third one is why `MeasureOutput` never carries anything called "validated".
`teacher_calibrated` is stamped False on every result, because it is False.

Four deterministic checks run over whatever the engine returns, and they are the
reason a weak engine cannot fabricate a strong score:

  - a value outside 1-4 is discarded, never clamped
  - an evidence span not found verbatim in the artifact is dropped
  - a dimension nobody could score stays None, and is never read as zero
  - a failure is recorded as a failure, with its reason

Two rules from the redesigned framework (sec:measure):

  - **Selecting is not composing** (component 24). Only the text she composed is
    scored. Spans the interface inserted are removed before scoring, and an
    evidence span must be found in her composed text, not in an inserted chip.
  - **The judge is independent of the generator** (component 23). Every result
    records which model judged and which model generated the answer she read,
    and whether they differ. The check runs per attempt; it is not assumed.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from ..engines.base import Engine, EngineError, ScoringRequest, ScoringSample
from ..framework import rubric
from ..framework.contracts import (
    Agreement,
    DimensionScore,
    MeasureInput,
    MeasureOutput,
)
from ..policy import confidence as conf_policy
from ..policy import generator as generator_policy

ROUTING_SCORE_AVAILABLE = "score_available"
ROUTING_CLARIFICATION = "clarification_required"
ROUTING_HUMAN_REVIEW = "human_review_required"


@dataclass
class MeasureLayer:
    READS: tuple[str, ...] = ("elicit",)

    engine: Engine = None  # type: ignore[assignment]
    #: The cross-model comparator. Off by default: it doubles cost, and the
    #: thesis's own claim is about two *organisations*, not two calls.
    comparator: Engine | None = None

    #: Name of the model that generates the answer she reads. Set by the
    #: session from its generator, never from the scoring engine.
    generator_model: str = ""

    def __init__(
        self,
        engine: Engine,
        comparator: Engine | None = None,
        generator_model: str = "",
    ) -> None:
        self.engine = engine
        self.comparator = comparator
        self.generator_model = generator_model

    def _provenance(self, record) -> dict:
        judges = (self.engine.name,) + (
            (self.comparator.name,) if self.comparator is not None else ()
        )
        return {
            "judge_model": self.engine.name,
            "generator_model": self.generator_model,
            "judge_independent_of_generator": generator_policy.independent(
                judges, self.generator_model
            ),
            "excluded_inserted_chars": len(record.prompt_text)
            - len(record.composed_text),
        }

    def run(self, data: MeasureInput) -> MeasureOutput:
        record = data.record
        provenance = self._provenance(record)
        # Her words only. What the interface inserted is not hers to be scored on.
        mine = record.composed_text
        request = ScoringRequest(
            prompt_text=mine,
            stated_intent=record.stated_intent,
            task_scenario="",
        )

        try:
            samples = [
                self.engine.sample_scores(request, t)
                for t in conf_policy.ENSEMBLE_TEMPERATURES
            ]
        except EngineError as exc:
            return MeasureOutput(
                scores={},
                overall=None,
                failure_reason=f"{type(exc).__name__}: {exc}",
                routing=ROUTING_HUMAN_REVIEW,
                **provenance,
            )

        scores = self._aggregate(samples, mine)

        scored = [s for s in scores.values() if s.value is not None]
        if not scored:
            return MeasureOutput(
                scores=scores,
                overall=None,
                failure_reason="no dimension could be scored",
                routing=ROUTING_HUMAN_REVIEW,
                **provenance,
            )

        overall = round(statistics.fmean(s.value for s in scored), 3)  # type: ignore[misc]
        mean_conf = statistics.fmean(s.confidence for s in scores.values())

        agreement = self._agreement(request, scores)

        routing = ROUTING_SCORE_AVAILABLE
        if mean_conf < conf_policy.CLARIFICATION_FLOOR:
            routing = ROUTING_CLARIFICATION

        return MeasureOutput(
            scores=scores,
            overall=overall,
            agreement=agreement,
            routing=routing,
            **provenance,
        )

    # -- aggregation -----------------------------------------------------

    def _aggregate(
        self, samples: list[ScoringSample], artifact: str
    ) -> dict[str, DimensionScore]:
        haystack = artifact.lower()
        out: dict[str, DimensionScore] = {}

        for dim in rubric.DIMENSIONS:
            values: list[int | None] = []
            span: str | None = None

            for sample in samples:
                for ds in sample.dimensions:
                    if ds.dimension_id != dim.id:
                        continue
                    v = ds.value
                    # Outside the rubric is not a low score. It is not a score.
                    if v is not None and not (
                        rubric.RUBRIC_MIN <= v <= rubric.RUBRIC_MAX
                    ):
                        v = None
                    values.append(v)
                    if span is None and ds.evidence_span:
                        span = ds.evidence_span

            usable = [v for v in values if v is not None]

            span_verified = True
            if span is not None and span.lower().strip() not in haystack:
                # A span the model invented is worse than no span, because it
                # would show the student a quotation she never wrote.
                span = None
                span_verified = False

            if not usable:
                out[dim.id] = DimensionScore(
                    dimension_id=dim.id,
                    value=None,
                    confidence=0.0,
                    evidence_span=None,
                    unable_to_score=True,
                    span_verified=span_verified,
                    evaluative=dim.is_evaluative,
                )
                continue

            out[dim.id] = DimensionScore(
                dimension_id=dim.id,
                value=round(statistics.fmean(usable)),
                confidence=conf_policy.for_dimension(dim.id, values),
                evidence_span=span,
                unable_to_score=False,
                span_verified=span_verified,
                evaluative=dim.is_evaluative,
            )

        return out

    # -- the first bar ---------------------------------------------------

    def _agreement(
        self, request: ScoringRequest, primary: dict[str, DimensionScore]
    ) -> Agreement | None:
        if self.comparator is None:
            return None

        try:
            other = self.comparator.sample_scores(request, 0.2)
        except EngineError:
            return None

        gaps: dict[str, float] = {}
        for ds in other.dimensions:
            mine = primary.get(ds.dimension_id)
            if mine is None or mine.value is None or ds.value is None:
                continue
            gaps[ds.dimension_id] = abs(mine.value - ds.value)

        different_orgs = self.engine.organisation != self.comparator.organisation

        return Agreement(
            scorer_a=self.engine.name,
            scorer_b=self.comparator.name,
            different_organisations=different_orgs,
            per_dimension_gap=gaps,
            mean_gap=round(statistics.fmean(gaps.values()), 3) if gaps else 0.0,
            caveat=(
                rubric.SHARED_PRIOR_THREAT
                if different_orgs
                else "Both scorers are the same organisation. This is not the "
                "cross model bar; it measures one vendor's self consistency."
            ),
        )


#: Stamped on every result. It is not a disclaimer; it is a fact about what the
#: number is.
PROVENANCE = {
    "teacher_calibrated": False,
    "third_bar": rubric.THIRD_BAR_UNCLEARED,
    "reliability_expires": rubric.RELIABILITY_EXPIRY,
}
