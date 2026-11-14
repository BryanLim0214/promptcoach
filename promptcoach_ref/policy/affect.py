"""Affective inference: tried, switched off, and removed.

Build 2 inferred affect from timing: "High error rate with long response times,
difficulty decreases" and "Fast correct answers, difficulty increases". An
earlier draft of the framework carried this as a Transferred component
("Affective state inference") and warned in the same passage that the reading
may be backwards for prompting: a long pause on an arithmetic problem is
evidence of struggle, and a long pause before submitting a prompt may be
evidence of planning, which is the behavior the whole system is trying to
produce.

This reference implementation shipped the mechanism switched off, because the
honest response to a signal that may be inverted is not to tune it but to
decline to act on it. The thesis then removed the component from the framework
and lists it under "tried and not carried over" (sec:not-adopted). It is absent
from `framework/`; this module is the note that it was tried, and the one
affect-like signal that remains, which is what the student says herself.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Choice, register

LATENCY_INFERENCE_REMOVED = register(
    Choice(
        id="affect.latency_inference",
        value="removed",
        thesis_says=(
            "sec:not-adopted lists affective state inference as tried and not "
            "carried over; the framework no longer contains it."
        ),
        borrowed_from=(
            "sec:build2 - Build 2 read long latency with errors as frustration and "
            "fast success as boredom."
        ),
        caveat=(
            "Removed, not tuned. This implementation first shipped it disabled, "
            "because reading a pause as struggle 'would reduce difficulty for "
            "exactly the students who are doing the work'. Latency is still "
            "recorded with each attempt and drives nothing."
        ),
    )
)

EXPLICIT_ONLY = register(
    Choice(
        id="affect.explicit_signals_only",
        value=True,
        thesis_says=(
            "With affect inference removed, the framework escalates on repeated "
            "failed attempts and explicit requests for help (sec:respond)."
        ),
        borrowed_from="none",
        caveat=(
            "Only what the student says counts - a request for help, or a statement "
            "that she is stuck. This gives up the responsiveness Build 2 had."
        ),
    )
)


@dataclass(frozen=True)
class AffectReading:
    frustration: bool
    boredom: bool
    basis: str
    #: Always recorded, never acted on.
    observed_latency_ms: int = 0


def read(
    *,
    student_said_stuck: bool = False,
    student_asked_for_help: bool = False,
    latency_ms: int = 0,
) -> AffectReading:
    if student_said_stuck or student_asked_for_help:
        return AffectReading(
            frustration=True,
            boredom=False,
            basis="the student said so",
            observed_latency_ms=latency_ms,
        )
    return AffectReading(
        frustration=False,
        boredom=False,
        basis=(
            "no explicit signal; latency is recorded but not read as affect, because "
            "a pause before a prompt may be planning"
        ),
        observed_latency_ms=latency_ms,
    )
