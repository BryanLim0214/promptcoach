"""Everything the thesis does not specify.

The manuscript states output contracts for Layers 1-4 and leaves twenty-four other
things open. An implementation has to choose anyway. This package is where those
choices live, and every one of them declares:

    thesis_says    - the passage proving the thesis leaves this open
    borrowed_from  - where the number came from, or "none"
    caveat         - what the thesis says about relying on it

Nothing in `promptcoach_ref.framework` imports from here. The dependency runs one
way, so the transcription of the thesis can be read without the choices mixed in.

Some choices are refusals or removals rather than values, and they are the ones
worth arguing with:

  - `affect.latency_inference` is removed: the framework dropped affective state
    inference after this implementation had to switch it off.
  - `escalation.inactivity` is removed for the same reason.
  - `gating.may_cross_axis_join` is off: bands 3 and 4 sit on two separate
    scales with no promotion rule across the join.

Four choices are new with the redesigned framework: `revision.*` (the reasoned
revision rule's minimum length and exit), `calibration.*` (whether she sees her
calibration gap; never the teacher), and `generator.*` (which model answers her
prompt, separate from the judge).
"""

from . import (
    affect,
    base,
    calibration,
    classifier,
    confidence,
    decomposition,
    escalation,
    gating,
    generator,
    response,
    revision,
    taskbank,
)
from .base import Choice, all_choices, UNSPECIFIED_BY_THESIS

__all__ = [
    "affect",
    "base",
    "calibration",
    "classifier",
    "confidence",
    "decomposition",
    "escalation",
    "gating",
    "generator",
    "response",
    "revision",
    "taskbank",
    "Choice",
    "all_choices",
    "UNSPECIFIED_BY_THESIS",
]
