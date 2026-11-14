"""Engines.

`DeterministicEngine` runs the whole loop with no key and no network. It is not a
test double: its `compose` half is the template floor sec:respond
specifies, which the live engine falls back to whenever generation fails or
violates the constraints.

`OpenRouterEngine` routes to a named model. Two instances from different
organisations give Layer 2 its cross-model bar.
"""

from .base import (
    ComposeRequest,
    DiagnosisRequest,
    DimensionSample,
    Engine,
    EngineError,
    RawAssignment,
    ScoringRequest,
    ScoringSample,
)
from .deterministic import DeterministicEngine, template_floor

__all__ = [
    "ComposeRequest",
    "DeterministicEngine",
    "DiagnosisRequest",
    "DimensionSample",
    "Engine",
    "EngineError",
    "RawAssignment",
    "ScoringRequest",
    "ScoringSample",
    "template_floor",
]
