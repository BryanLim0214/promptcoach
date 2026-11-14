"""Per-dimension confidence, and how the four sentinel signals combine.

The thesis makes confidence normative without defining it. sec:measure
requires "six dimension scores with per dimension confidence", and sec:measure requires
that a system "attach lower confidence to [the evaluative dimensions] and should
not escalate on their basis alone". It gives no formula, threshold, or scale.

The only mechanism the manuscript actually names is the ensemble spread:
sec:build1 - PatternLens "runs the same per dimension scoring prompt
three times at temperatures 0.2, 0.5, and 0.8 and reports the mean along with the
spread". That is what is used here.

Sentinel aggregation is a separate gap. sec:method says
discrimination "is reported as area under the curve, which avoids committing to a
threshold" - so the thesis deliberately declines to give one, and any threshold
here is ours.
"""

from __future__ import annotations

import statistics

from ..framework import rubric, sentinel
from .base import Choice, register

#: sec:build1 - the three judge ensemble.
ENSEMBLE_TEMPERATURES: tuple[float, ...] = (0.2, 0.5, 0.8)

ENSEMBLE = register(
    Choice(
        id="confidence.ensemble_temperatures",
        value=list(ENSEMBLE_TEMPERATURES),
        thesis_says=(
            "sec:measure requires per dimension confidence and gives no "
            "formula."
        ),
        borrowed_from=(
            "sec:build1 - the PatternLens three judge ensemble at "
            "temperatures 0.2, 0.5, and 0.8, reporting mean and spread. This is the "
            "only confidence mechanism the manuscript names."
        ),
        caveat=(
            "Spread across three samples of one model measures that model's "
            "self-consistency, not correctness. It is not the cross model bar and it "
            "is certainly not agreement with a teacher."
        ),
    )
)

EVALUATIVE_PENALTY = 0.15

EVALUATIVE = register(
    Choice(
        id="confidence.evaluative_penalty",
        value=EVALUATIVE_PENALTY,
        thesis_says=(
            "sec:measure requires lower confidence on evaluative "
            "dimensions and names no amount."
        ),
        borrowed_from=(
            "Scaled loosely against tab:agreement, where Reflection's weighted kappa "
            "is 0.645 against Specificity's 0.967."
        ),
        caveat=(
            "A flat penalty is cruder than the data. tab:agreement's own caveat "
            "applies: the ordering of the six dimensions is indicative rather than "
            "established at n=30 with no intervals."
        ),
    )
)

CLARIFICATION_FLOOR = 0.45

FLOOR = register(
    Choice(
        id="confidence.clarification_floor",
        value=CLARIFICATION_FLOOR,
        thesis_says="No confidence threshold is specified anywhere.",
        borrowed_from="none",
        caveat=(
            "Below this the system asks the student for something specific rather "
            "than diagnosing on weak evidence. Set too high it nags; set too low it "
            "diagnoses noise. Nothing in the thesis settles where it belongs."
        ),
    )
)


def for_dimension(dimension_id: str, samples: list[int | None]) -> float:
    """Mean-agreement across the ensemble, penalised for evaluative dimensions.

    Returns 0.0 when nothing scored - which routes to clarification rather than
    to a confident zero.
    """
    values = [v for v in samples if v is not None]
    if not values:
        return 0.0

    if len(values) == 1:
        base = 0.6
    else:
        spread = statistics.pstdev(values)
        # Full agreement across the ensemble reads as 1.0; a spread of one whole
        # rubric point halves it.
        base = max(0.0, 1.0 - (spread / rubric.RUBRIC_SPAN) * 3.0)
        base = min(1.0, base)

    if rubric.is_evaluative(dimension_id):
        base = max(0.0, base - EVALUATIVE_PENALTY)

    return round(base, 3)


# ---------------------------------------------------------------------------
# Sentinel aggregation
# ---------------------------------------------------------------------------

AGGREGATION = register(
    Choice(
        id="sentinel.aggregation",
        value="max_with_all_four_retained",
        thesis_says=(
            "The thesis does not specify how the four 0-1 signal scores aggregate "
            "into a single sentinel score."
        ),
        borrowed_from="none",
        caveat=(
            "sec:build1 records that excessive deference fired on "
            "seven of the nine positives - 'the aggregate figure is carried by one "
            "signal, and a detector resting on one signal is a detector with one "
            "failure mode'. Taking the maximum would repeat that failure silently, "
            "so all four are always returned alongside it and the UI shows all four."
        ),
    )
)

SENTINEL_THRESHOLD = register(
    Choice(
        id="sentinel.threshold",
        value=None,
        thesis_says=(
            "sec:method - discrimination 'is reported as "
            "area under the curve, which avoids committing to a threshold'."
        ),
        borrowed_from="none",
        caveat=(
            "No threshold is set. Signals are shown to the student as values, never "
            "as a fired/not-fired alert, because an alert is the thing "
            "sec:build1 forbids."
        ),
    )
)


def aggregate_sentinel(signals: dict[str, float]) -> dict[str, float]:
    """Return every signal plus a summary, never a summary alone."""
    for key in signals:
        if key not in sentinel.BY_ID:
            raise KeyError(f"{key} is not one of the four sentinel signals")
    out = dict(signals)
    if signals:
        out["_highest"] = max(signals.values())
        out["_carried_by"] = max(signals, key=lambda k: signals[k])  # type: ignore[assignment]
    return out
