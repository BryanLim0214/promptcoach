"""Layer 5 - Calibrate.

    "The layer does two things: it adjusts task difficulty, and it watches for
    over reliance."
    - sec:calibrate

Layers 1-4 each end with a "Requirement passed downstream" sentence. **Layer 5
has none.** The shape of `CalibrateOutput` is therefore ours, and it says so.

Two things this layer must do that a smaller implementation would skip:

**It records unpaired deltas.** F2 asks whether the paired dimension moves *more*
than the others - "for each diagnosis, the paired dimension should move more than
the unpaired dimensions do. If it does not, Layer 5 is measuring the derivation
and not the coaching." A system that stored only the paired delta could never run
that test on itself.

**It records pairing strictness.** sec:design - the pairings
"differ in strictness, and a system that treated them as equivalent would find
more improvement after some diagnoses than others for reasons that have nothing
to do with the student." Intent drift counts any of six dimensions; delegated
judgment counts Reflection alone, the least reliable of the six.

**It records the calibration gap.** sec:calibrate now covers "the gap between
her predicted rating and the measured score" (component 22): predicted minus
measured, on the shared 1-4 scale, or None when either is missing. Whether she
is shown it is policy (F8); where it goes is not - it is hers.

**It reports whether a reasoned revision is still pending.** The new task is
held until one exists (component 21, framework/revision.py), unless the policy
exit applies.

**Which over-reliance detector runs.** Layer 5 calls the judge engine's
detector. In a live session that is the model-based detector
(`GeminiEngine.sentinel`), the one `eval/benchmark.py` measured. Offline, the
judge is the rule engine and its detector is a set of keyword rules
(`DeterministicEngine.sentinel`): an author-tested stand-in, labelled as such in
`CalibrateOutput.sentinel_source`. Layer 3 does not read either; it diagnoses
from its own rules over the plan, the prompt and the session history.

The sentinel and the calibration gap go to the student. There is no argument,
parameter, or return path in this module that sends them anywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass

import statistics

from ..engines.base import Engine, EngineError
from ..engines.deterministic import DeterministicEngine
from ..framework import progression, revision, rubric, sentinel
from ..framework.contracts import (
    CalibrateInput,
    CalibrateOutput,
    DimensionScore,
    calibration_gap,
)
from ..framework.taxonomy import BY_ID as TAXONOMY, Category
from ..policy import gating, taskbank


@dataclass
class CalibrateLayer:
    READS: tuple[str, ...] = ("elicit", "measure", "diagnose", "respond", "history")

    def __init__(self, engine: Engine | None = None) -> None:
        # The judge engine, for its over-reliance detector. With none given,
        # the offline rule engine - and so its author-tested keyword stand-in.
        self.engine = engine if engine is not None else DeterministicEngine()

    def run(self, data: CalibrateInput) -> CalibrateOutput:
        paired_delta, unpaired = self._deltas(data)
        strictness = _strictness(data.target)

        # The attempt being calibrated: the revision when there is one.
        attempt = data.child or data.parent
        scores = data.child_scores if data.child is not None else data.parent_scores
        measured = _overall(scores)

        # One outcome per closed cycle (gating.streak_unit), judged by the
        # gating.success rule against the band of the task she attempted.
        task = taskbank.BY_ID.get(attempt.task_id)
        succeeded = (
            gating.attempt_succeeded(task.band, task.named_dimensions, scores)
            if task is not None
            else False
        )
        outcomes = data.recent_outcomes + (succeeded,)

        decision = gating.evaluate(outcomes)
        band, crossed, reason = gating.apply(data.band, decision)

        signals, signals_source = self._detect(data)

        next_task = taskbank.next_task(
            band, exclude=frozenset({data.parent.task_id})
        )
        gap = calibration_gap(attempt.predicted_rating, measured)

        pending = revision.new_task_held(
            reasoned_revisions_on_task=data.reasoned_revisions_on_task,
            required=data.revision_required,
            exit_applies=data.revision_exit_applies,
        )

        return CalibrateOutput(
            band=band,
            band_changed=band != data.band,
            crossed_axis_join=crossed,
            reason=reason,
            paired_delta=paired_delta,
            unpaired_deltas=unpaired,
            pairing_strictness=strictness,
            sentinel=signals,
            sentinel_source=signals_source,
            next_task_id=next_task.id if next_task else None,
            calibration_gap=gap,
            predicted_rating=attempt.predicted_rating,
            measured_overall=measured,
            revision_pending=pending,
            attempt_succeeded=succeeded,
        )

    # -- the comparative measurement F2 needs ----------------------------

    def _deltas(
        self, data: CalibrateInput
    ) -> tuple[float | None, dict[str, float]]:
        if data.child_scores is None:
            return None, {}

        paired_ids = set(TAXONOMY[data.target].paired.dimension_ids)
        paired_moves: list[float] = []
        unpaired: dict[str, float] = {}

        for dim in rubric.DIMENSIONS:
            before = data.parent_scores.get(dim.id)
            after = data.child_scores.get(dim.id)
            delta = _delta(before, after)
            if delta is None:
                continue
            if dim.id in paired_ids:
                paired_moves.append(delta)
            else:
                unpaired[dim.id] = delta

        if not paired_moves:
            return None, unpaired

        # A broad pairing counts as improved if any of its dimensions moved,
        # which is exactly the leniency STRICTNESS_WARNING is about.
        return max(paired_moves), unpaired

    # -- over reliance ---------------------------------------------------

    def _sentinel(self, data: CalibrateInput) -> dict[str, float]:
        """Four signals, all four returned. To the student only."""
        return self._detect(data)[0]

    def _detect(self, data: CalibrateInput) -> tuple[dict[str, float], str]:
        """(signals, which detector produced them).

        Layer 5 calls the judge engine's own detector. Live, that is the
        model-based detector `eval/benchmark.py` measures. Offline, the judge is
        the rule engine, whose detector is a keyword stand-in tested only on the authors' own
        items; `sentinel_source` says so on every result. An engine with no
        detector returns no signals rather than borrowing the keyword rules,
        because those would then be shown as if they were the measured detector.
        """
        attempt = data.child or data.parent
        history = data.prior_prompts or (
            (data.parent.composed_text,) if data.child is not None else ()
        )
        detect = getattr(self.engine, "sentinel", None)
        source = getattr(self.engine, "SENTINEL_SOURCE", None) or getattr(
            self.engine, "name", "engine"
        )
        if detect is None:
            return {}, (
                f"none: the judge engine ({getattr(self.engine, 'name', '?')}) has "
                "no over-reliance detector"
            )
        try:
            raw = detect(attempt.stated_intent, attempt.composed_text, tuple(history))
        except EngineError as exc:
            # A failed call stays a failure; it is not a zero and it is not
            # replaced with the keyword rules.
            return {}, f"none: the detector call failed ({exc})"
        signals = {
            s.id: float(raw[s.id]) for s in sentinel.SIGNALS if s.id in raw
        }
        return signals, str(source)


def _overall(scores: dict[str, DimensionScore] | None) -> float | None:
    """The measured score on the 1-4 scale, as Layer 2 reports `overall`."""
    if not scores:
        return None
    values = [s.value for s in scores.values() if s.value is not None]
    if not values:
        return None
    return round(statistics.fmean(values), 3)


def _delta(before: DimensionScore | None, after: DimensionScore | None) -> float | None:
    if before is None or after is None:
        return None
    if before.value is None or after.value is None:
        return None
    return float(after.value - before.value)


def _strictness(target: Category) -> str:
    """How easy the paired check is to pass.

    Reported alongside every improvement result, because a broad pairing and a
    narrow one are not comparable evidence.
    """
    paired = TAXONOMY[target].paired
    n = len(paired.dimension_ids)
    if paired.dynamic and n > 3:
        return "broad"
    if n == 1 and paired.dimension_ids[0] in {
        rubric.REFLECTION.id,
        rubric.ITERATION_AWARENESS.id,
    }:
        return "narrow, and on one of the two least reliable dimensions"
    if n == 1:
        return "narrow"
    return "moderate"
