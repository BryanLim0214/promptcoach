"""Layer contracts.

The thesis states an output contract for Layers 1-4 in a sentence beginning
"Requirement passed downstream:". Those four sentences are reproduced verbatim
on each Output class below.

Three things the thesis does NOT state, marked as such everywhere they appear:

1. **Per-layer inputs.** Only outputs are specified. Each Input class below is
   inferred from the previous layer's output plus the Chapter 11 walkthrough, and
   carries `THESIS_SPECIFIED = False`.
2. **Layer 5's output.** Layers 1-4 each have a "Requirement passed downstream"
   line; Layer 5 has none. `CalibrateOutput.THESIS_SPECIFIED` is False.
3. **Any state machine.** There are no named states in the manuscript. The only
   state vocabulary is the two prose phrases "the escalation state" and "the
   difficulty state". `session.py` defines states; they are ours, and they say so.

The dependency is a DAG, not a pipeline. sec:framework:

    "The dependency is not a single chain: Layer 3 reads Layer 1's paired record
    and the session history directly, because four of its seven categories are
    invisible in the prompt text that Layer 2 scores."

`READS` on each protocol records which upstream outputs that layer may see. A
contract test asserts no layer reads anything not declared there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .rubric import RUBRIC_MAX, RUBRIC_MIN
from .taxonomy import Category

#: sec:framework - in the student's attempt cycle she "rates how good she thinks
#: it is, 1 to 4" before she sees the output. The scale is the rubric's own, so
#: the prediction and the measured score can be subtracted.
PREDICTED_MIN = RUBRIC_MIN
PREDICTED_MAX = RUBRIC_MAX


# ---------------------------------------------------------------------------
# Selecting is not composing (sec:measure, component 24)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Span:
    """A half-open character range [start, end) of the prompt that the interface
    inserted (a chip, a template, a pasted suggestion) rather than she typed."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span [{self.start}, {self.end})")


def composed_text(prompt_text: str, inserted_spans: tuple[Span, ...]) -> str:
    """The part of the prompt she wrote herself.

    sec:measure, component 24 - "Selecting is not composing: only text she wrote
    is scored as hers." Inserted spans are removed, never repaired around: what
    remains is exactly her words, in order, with whitespace collapsed where a
    removal left a double gap.
    """
    if not inserted_spans:
        return prompt_text
    keep = [True] * len(prompt_text)
    for span in inserted_spans:
        for i in range(max(0, span.start), min(len(prompt_text), span.end)):
            keep[i] = False
    kept = "".join(ch for ch, k in zip(prompt_text, keep) if k)
    return " ".join(kept.split())


def inserted_text(prompt_text: str, inserted_spans: tuple[Span, ...]) -> str:
    """The part of the prompt the interface put there."""
    return " ".join(
        prompt_text[max(0, s.start) : min(len(prompt_text), s.end)].strip()
        for s in sorted(inserted_spans, key=lambda s: s.start)
    ).strip()


# ---------------------------------------------------------------------------
# Records that cross layer boundaries
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairedRecord:
    """Layer 1's product. "A paired record of intent and artifact, plus timing."

    The two halves must be genuinely different records. sec:build1:
    "The student is planning aloud, not dictating: she is not reading out the
    prompt she is about to type. If she were, the two records would be the same
    record and the comparison between them would carry no information."
    """

    attempt_id: str
    task_id: str
    stated_intent: str
    prompt_text: str
    intent_modality: str  # "speech" | "typed"
    #: True only when a speech transcript has been shown to the student and
    #: confirmed. Unreviewed transcripts do not reach Layer 2.
    transcript_reviewed: bool
    student_ms: int
    system_ms: int
    parent_attempt_id: str | None = None
    triggering_intervention_id: str | None = None
    #: Her prediction of how good the prompt is, 1 to 4, made before she sees
    #: the output. Optional: a student who skips it is not blocked.
    predicted_rating: int | None = None
    #: Why she changed the prompt, when this is a revision of the same task.
    revision_reason: str | None = None
    #: What the interface inserted rather than she typed. Never scored as hers.
    inserted_spans: tuple[Span, ...] = ()

    def __post_init__(self) -> None:
        if self.predicted_rating is not None and not (
            PREDICTED_MIN <= self.predicted_rating <= PREDICTED_MAX
        ):
            raise ValueError(
                f"predicted rating {self.predicted_rating} is outside "
                f"{PREDICTED_MIN}-{PREDICTED_MAX}"
            )
        for span in self.inserted_spans:
            if span.end > len(self.prompt_text):
                raise ValueError("an inserted span runs past the end of the prompt")

    @property
    def is_revision(self) -> bool:
        return self.parent_attempt_id is not None

    @property
    def composed_text(self) -> str:
        """Only what she wrote. Measure scores this, Respond treats only this
        as hers."""
        return composed_text(self.prompt_text, self.inserted_spans)

    @property
    def intent_is_degraded(self) -> bool:
        """A typed statement of intent preserves the paired record at lower
        fidelity. sec:elicit - it "degrades the diagnosis rather
        than blocking it"."""
        return self.intent_modality == "typed"


@dataclass(frozen=True)
class DimensionScore:
    dimension_id: str
    #: None when the dimension could not be scored. Never coerced to zero - a
    #: failure to score is not evidence of absence.
    value: int | None
    confidence: float
    #: A span quoted from the student's own artifact. Dropped when it cannot be
    #: found there verbatim, because a fabricated span is worse than none.
    evidence_span: str | None
    unable_to_score: bool = False
    span_verified: bool = True
    #: True for Iteration Awareness and Reflection. sec:measure makes lowering
    #: confidence on these normative.
    evaluative: bool = False

    def __post_init__(self) -> None:
        if self.value is not None and not (RUBRIC_MIN <= self.value <= RUBRIC_MAX):
            raise ValueError(
                f"{self.dimension_id}: {self.value} is outside the rubric. "
                "Out-of-range values are discarded upstream, never clamped into "
                "a score."
            )


@dataclass(frozen=True)
class CategoryAssignment:
    category: Category
    rank: int
    confidence: float
    #: The observation that fired this assignment, in the student's own words
    #: where possible. An assignment with no trigger is not reportable.
    trigger: str
    overlaps_with: tuple[Category, ...] = ()


# ---------------------------------------------------------------------------
# Layer 1 - Elicit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElicitInput:
    THESIS_SPECIFIED = False  # inferred from Ch. 11's walkthrough

    session_id: str
    task_id: str
    #: Her plan, given BEFORE she writes the prompt, on every attempt including
    #: the first. Spoken (`intent_modality="speech"`, transcript reviewed) or
    #: typed (`intent_modality="typed"`): the typed plan is the microphone-free
    #: path, and it is a separate field from `revision_reason`.
    stated_intent: str
    prompt_text: str
    intent_modality: str = "typed"
    transcript_reviewed: bool = True
    student_ms: int = 0
    parent_attempt_id: str | None = None
    triggering_intervention_id: str | None = None
    #: 1 to 4, optional. Range-checked by Layer 1, which asks again rather than
    #: raising, because a slip on a control is not a reason to lose the attempt.
    predicted_rating: int | None = None
    #: Why she changed the prompt, given AFTER she has seen an output, on a
    #: revision only. It never stands in for the plan: a revision still needs
    #: its own `stated_intent`.
    revision_reason: str | None = None
    inserted_spans: tuple[Span, ...] = ()


@dataclass(frozen=True)
class ElicitOutput:
    REQUIREMENT_PASSED_DOWNSTREAM = (
        "a paired record of intent and artifact, plus timing"
    )
    THESIS_SPECIFIED = True

    record: PairedRecord | None
    #: Set when capture did not produce a usable paired record. The cycle stops
    #: here and the student is asked for something specific; nothing is inferred
    #: on her behalf.
    clarification_required: str | None = None


# ---------------------------------------------------------------------------
# Layer 2 - Measure
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeasureInput:
    THESIS_SPECIFIED = False

    record: PairedRecord


@dataclass(frozen=True)
class MeasureOutput:
    REQUIREMENT_PASSED_DOWNSTREAM = (
        "six dimension scores with per dimension confidence"
    )
    THESIS_SPECIFIED = True

    scores: dict[str, DimensionScore]
    overall: float | None
    #: Populated when the cross-model protocol ran. Absent is not failure; it
    #: means the second scorer was off.
    agreement: "Agreement | None" = None
    #: A scoring failure stays a failure. It is not a zero and it is not a low
    #: score.
    failure_reason: str | None = None
    routing: str = "score_available"
    #: sec:measure, component 23 - the judge that scores her work is not the
    #: model that produced the output she read. Both are recorded on every
    #: result so independence is checked per attempt, not assumed.
    judge_model: str = ""
    generator_model: str = ""
    judge_independent_of_generator: bool = False
    #: Characters of the prompt the interface inserted and Measure did not
    #: score (component 24).
    excluded_inserted_chars: int = 0


@dataclass(frozen=True)
class Agreement:
    """Measure's first bar: cross model agreement.

    The second scorer must come from a different organisation for this number to
    mean what sec:measure says it means - "A score two models from different vendors
    agree on is not an artifact of one model's idiosyncrasy".
    """

    scorer_a: str
    scorer_b: str
    different_organisations: bool
    per_dimension_gap: dict[str, float]
    mean_gap: float
    #: The shared-prior threat applies no matter how high this is.
    caveat: str


# ---------------------------------------------------------------------------
# Layer 3 - Diagnose
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiagnoseInput:
    THESIS_SPECIFIED = False

    #: Layer 3 reads Layer 1 directly. This is the DAG edge, not a convenience:
    #: four of seven categories are invisible in the prompt text Layer 2 scores.
    record: PairedRecord
    scores: dict[str, DimensionScore]
    session_history: tuple[PairedRecord, ...] = ()


@dataclass(frozen=True)
class DiagnoseOutput:
    REQUIREMENT_PASSED_DOWNSTREAM = (
        "a ranked list of failure categories with confidence"
    )
    THESIS_SPECIFIED = True

    #: Ranked, never a single label. sec:diagnose requires this because the categories
    #: overlap; a bare label would hide the overlap the thesis says is constant.
    assignments: tuple[CategoryAssignment, ...]
    #: The top-ranked assignment, or None when nothing cleared threshold.
    target: Category | None
    #: Distinct from "no failure". Insufficient evidence means the system could
    #: not tell, and saying so is more honest than defaulting to a category.
    insufficient_evidence: bool = False
    reason_trace: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        ranks = [a.rank for a in self.assignments]
        if ranks != sorted(ranks):
            raise ValueError("assignments must be in rank order")
        if self.target is not None and self.assignments:
            if self.assignments[0].category is not self.target:
                raise ValueError(
                    "target must be the top ranked assignment: sec:diagnose requires the "
                    "response layer to act on the top ranked failure only"
                )


# ---------------------------------------------------------------------------
# Layer 4 - Respond
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RespondInput:
    THESIS_SPECIFIED = False

    record: PairedRecord
    target: Category
    scores: dict[str, DimensionScore]
    #: How far up the ladder this help cycle has already gone.
    levels_already_issued: tuple[int, ...] = ()
    #: Consecutive attempts on this task, this one included, whose top-ranked
    #: category is `target` (first attempts and revisions alike). The session
    #: counts it; 0 means the caller did not. It is not the number of help
    #: responses already issued.
    consecutive_same_top: int = 0
    escalation_signals: tuple[str, ...] = ()
    #: Her own words (composed text) on the previous attempt in this task
    #: cycle, or None on the first. Lets escalation tell an unchanged prompt
    #: from a changed one without reading any score.
    previous_composed_text: str | None = None


@dataclass(frozen=True)
class RespondOutput:
    REQUIREMENT_PASSED_DOWNSTREAM = (
        "the level issued, and whether the student's next attempt improved on the "
        "dimension that Table 7 pairs with the diagnosed category"
    )
    THESIS_SPECIFIED = True

    level: int
    target: Category
    text: str
    expected_action: str
    #: True when generation failed or violated the constraints and the template
    #: floor was served instead. The floor is the specified safe path, not a bug.
    used_template_floor: bool = False
    selection_reason: str = ""


# ---------------------------------------------------------------------------
# Layer 5 - Calibrate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrateInput:
    THESIS_SPECIFIED = False

    parent: PairedRecord
    child: PairedRecord | None
    target: Category
    level_issued: int
    parent_scores: dict[str, DimensionScore]
    child_scores: dict[str, DimensionScore] | None
    band: int
    recent_outcomes: tuple[bool, ...] = ()
    #: How many revisions of the current task carried a stated reason, counting
    #: this one. The revision rule (framework/revision.py) reads it.
    reasoned_revisions_on_task: int = 0
    #: Whether the policy exit from the revision hold applies (policy/revision).
    revision_exit_applies: bool = False
    #: Whether the reasoned-revision requirement is switched on. Off only for the
    #: control arm of F7.
    revision_required: bool = True
    #: Her earlier composed prompts this session, oldest first, for the
    #: over-reliance detector. Empty means "use the parent only".
    prior_prompts: tuple[str, ...] = ()


def calibration_gap(
    predicted_rating: int | None, measured_overall: float | None
) -> float | None:
    """Predicted minus measured, on the shared 1-4 scale.

    sec:calibrate - Calibrate "now covers ... the gap between her predicted
    rating and the measured score". Positive means she rated the prompt higher
    than it scored. None when either side is missing: a missing prediction is
    not a prediction of zero, and a scoring failure is not a score.

    "Measured" means model-scored, so the shared-priors threat applies to the
    gap exactly as it applies to the score.
    """
    if predicted_rating is None or measured_overall is None:
        return None
    return round(float(predicted_rating) - float(measured_overall), 2)


@dataclass(frozen=True)
class CalibrateOutput:
    #: Layers 1-4 each end with a "Requirement passed downstream" sentence.
    #: Layer 5 has none. This shape is ours.
    REQUIREMENT_PASSED_DOWNSTREAM = None
    THESIS_SPECIFIED = False

    band: int
    band_changed: bool
    crossed_axis_join: bool
    reason: str
    #: The paired dimension's movement, and every unpaired dimension's movement
    #: beside it. F2 is a *comparative* test - "the paired dimension should move
    #: more than the unpaired dimensions do" - so storing only the paired delta
    #: would make the thesis's own refutation impossible to run.
    paired_delta: float | None = None
    unpaired_deltas: dict[str, float] = field(default_factory=dict)
    pairing_strictness: str = "unknown"
    sentinel: dict[str, float] = field(default_factory=dict)
    #: Which detector produced `sentinel`: the model-based detector the
    #: benchmark measured (live), the offline keyword stand-in (never
    #: benchmarked), or none, with the reason.
    sentinel_source: str = ""
    next_task_id: str | None = None
    #: Her predicted rating minus the measured score of the attempt being
    #: calibrated, or None. Goes to her and nowhere else.
    calibration_gap: float | None = None
    predicted_rating: int | None = None
    measured_overall: float | None = None
    #: True while the current task still needs one reasoned revision before a
    #: new task is offered (component 21).
    revision_pending: bool = False
    #: What this attempt added to the rate-and-streak window. The rule that
    #: decides it is policy (`gating.success`), not the thesis's.
    attempt_succeeded: bool = False


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class Elicit(Protocol):
    READS: tuple[str, ...] = ()

    def run(self, data: ElicitInput) -> ElicitOutput: ...


@runtime_checkable
class Measure(Protocol):
    READS: tuple[str, ...] = ("elicit",)

    def run(self, data: MeasureInput) -> MeasureOutput: ...


@runtime_checkable
class Diagnose(Protocol):
    #: Reads Layer 2 *and* Layer 1 directly, plus history. The DAG edge.
    READS: tuple[str, ...] = ("elicit", "measure", "history")

    def run(self, data: DiagnoseInput) -> DiagnoseOutput: ...


@runtime_checkable
class Respond(Protocol):
    READS: tuple[str, ...] = ("elicit", "measure", "diagnose")

    def run(self, data: RespondInput) -> RespondOutput: ...


@runtime_checkable
class Calibrate(Protocol):
    READS: tuple[str, ...] = ("elicit", "measure", "diagnose", "respond", "history")

    def run(self, data: CalibrateInput) -> CalibrateOutput: ...


#: Every layer, in the order Chapter 10 states, with what it may read. The
#: contract test walks this.
LAYER_READS: dict[str, tuple[str, ...]] = {
    "elicit": Elicit.READS,
    "measure": Measure.READS,
    "diagnose": Diagnose.READS,
    "respond": Respond.READS,
    "calibrate": Calibrate.READS,
}

DEPENDENCY_IS_NOT_A_CHAIN = (
    "The ordering is functional. Each layer consumes what earlier layers produce "
    "and cannot be built without them. The dependency is not a single chain: Layer 3 "
    "reads Layer 1's paired record and the session history directly, because four of "
    "its seven categories are invisible in the prompt text that Layer 2 scores."
)
