"""The seam between the framework and whatever produces judgements.

Three operations, because the framework needs three: score an artifact, classify
a failure, and compose a response within a level's constraints. Anything
satisfying this Protocol can drive the layers - a rule engine with no network, a
single model, or two models from different organisations running the cross-model
protocol.

Nothing in `layers/` imports a concrete engine. That is what makes the offline
path and the live path the same code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..framework.taxonomy import Category


@dataclass(frozen=True)
class ScoringRequest:
    prompt_text: str
    stated_intent: str
    task_scenario: str
    #: Present only at band 4, where she is evaluating something she can see.
    provided_model_output: str = ""


@dataclass(frozen=True)
class DimensionSample:
    """One judge's read of one dimension.

    `value` is None when the judge could not score it. That stays None all the
    way through; a dimension nobody could score is not a dimension that scored 1.
    """

    dimension_id: str
    value: int | None
    evidence_span: str | None = None


@dataclass(frozen=True)
class ScoringSample:
    """One pass of the whole rubric. The ensemble runs several."""

    judge: str
    temperature: float
    dimensions: tuple[DimensionSample, ...]
    latency_ms: int = 0


@dataclass(frozen=True)
class DiagnosisRequest:
    prompt_text: str
    stated_intent: str
    intent_modality: str
    scores: dict[str, int | None]
    task_scenario: str
    #: Prior prompts in this session, oldest first. Three of the seven categories
    #: are invisible without it.
    history: tuple[str, ...] = ()
    history_had_intervention: bool = False


@dataclass(frozen=True)
class RawAssignment:
    category: Category
    confidence: float
    trigger: str


@dataclass(frozen=True)
class ComposeRequest:
    level: int
    category: Category
    prompt_text: str
    stated_intent: str
    weakest_dimension_id: str
    #: The decision the task exists to make the student practise. No level may
    #: make it for her.
    protected_judgment: str
    missing_from_prompt: tuple[str, ...] = ()
    #: Dimensions present in what she said and absent from what she typed.
    #: Distinct from `missing_from_prompt`, which is everything the prompt
    #: lacks: these are the ones she already had and dropped, and naming them
    #: is what separates intent-drift coaching from teaching her the rubric.
    dropped_from_intent: tuple[str, ...] = ()


@runtime_checkable
class Engine(Protocol):
    name: str
    #: Organisation that built the model. The cross-model bar means nothing
    #: unless two engines differ here.
    organisation: str

    def sample_scores(self, request: ScoringRequest, temperature: float) -> ScoringSample: ...

    def diagnose(self, request: DiagnosisRequest) -> list[RawAssignment]: ...

    def compose(self, request: ComposeRequest) -> str | None: ...


class EngineError(RuntimeError):
    """Raised when an engine cannot answer.

    Callers convert this into a recorded failure, never into a score. A timeout
    stays a timeout.
    """
