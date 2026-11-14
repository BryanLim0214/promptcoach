"""Layer 3's taxonomy: seven categories of middle school prompt construction failure.

Transcribed from sec:framework tab:taxonomy, crossed with tab:improvement
for the dimension Layer 5 checks after each diagnosis.

tab:taxonomy's own caption, verbatim: "Proposed taxonomy of middle school prompt
construction failures. Derived, not validated."

Four properties of this taxonomy are stated as attackable (sec:diagnose) and are
encoded here rather than left in prose:

1. The categories overlap. Under specification and social framing co-occur
   constantly. Build 2 established that rule based classification fails exactly
   on overlapping signatures, so the diagnosis must return several categories in
   rank order and never a single label. See `Diagnosis` in contracts.py.
2. Much of it is behavioral rather than linguistic - `DetectableFrom` records
   which.
3. None of it is validated.
4. The derivation is close to circular, and the tab:improvement pairing is close
   to true by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from . import rubric
from .grades import Cite, Grade, SEVEN_CATEGORY_TAXONOMY


class Category(str, Enum):
    UNDER_SPECIFICATION = "under_specification"
    SOCIAL_FRAMING = "social_framing"
    INTENT_DRIFT = "intent_drift"
    BLIND_ACCEPTANCE = "blind_acceptance"
    UNDIAGNOSED_RETRY = "undiagnosed_retry"
    DELEGATED_JUDGMENT = "delegated_judgment"
    BORROWED_PHRASING = "borrowed_phrasing"


class DetectableFrom(str, Enum):
    """sec:diagnose - "Four of the seven categories... cannot be
    detected from the prompt text alone."

    This is why the layers cannot be reordered and why Layer 3 reads Layer 1
    directly. A system that captured only the artifact could detect three of
    seven.
    """

    PROMPT_TEXT = "prompt_text"
    PAIRED_SPOKEN_RECORD = "paired_spoken_record"
    SESSION_HISTORY = "session_history"


@dataclass(frozen=True)
class PairedDimension:
    """tab:improvement - which dimension Layer 5 checks for improvement.

    `dimension_ids` empty with a `rule` set means the pairing is dynamic: the
    dimension is chosen per attempt rather than fixed. Two of the seven are like
    this, and their strictness differs from the fixed ones - see STRICTNESS_WARNING.
    """

    description: str
    dimension_ids: tuple[str, ...] = ()
    dynamic: bool = False


@dataclass(frozen=True)
class FailureCategory:
    id: Category
    name: str
    student_did: str
    derived_from: str
    response_implied: str
    detectable_from: DetectableFrom
    paired: PairedDimension
    cite: Cite

    @property
    def grade(self) -> Grade:
        # The whole taxonomy carries one grade; no category is better evidenced
        # than any other.
        return SEVEN_CATEGORY_TAXONOMY.grade




UNDER_SPECIFICATION = FailureCategory(
    id=Category.UNDER_SPECIFICATION,
    name="Under specification",
    student_did="Omitted format, length, audience, or purpose",
    derived_from="Context Clarity, Specificity, Constraint Setting, Audience Awareness",
    response_implied="Ask which missing element would most change the answer",
    detectable_from=DetectableFrom.PROMPT_TEXT,
    paired=PairedDimension(
        description=(
            "Whichever of the four planning dimensions the coaching question named"
        ),
        dimension_ids=tuple(d.id for d in rubric.PLANNING_DIMENSIONS),
        dynamic=True,
    ),
    cite=Cite("sec:diagnose", "tab:taxonomy row 1"),
)

SOCIAL_FRAMING = FailureCategory(
    id=Category.SOCIAL_FRAMING,
    name="Social framing",
    student_did=(
        "Addressed the model as a person, with pleasantries and explanation of motives"
    ),
    derived_from="Knoth et al.",
    response_implied="Contrast two prompts differing only in social content",
    detectable_from=DetectableFrom.PROMPT_TEXT,
    paired=PairedDimension(
        description="Context Clarity",
        dimension_ids=(rubric.CONTEXT_CLARITY.id,),
    ),
    cite=Cite("sec:diagnose", "tab:taxonomy row 2"),
)

INTENT_DRIFT = FailureCategory(
    id=Category.INTENT_DRIFT,
    name="Intent drift",
    student_did="Said one thing aloud, typed something generic",
    derived_from="Transcript prompt disconnect signal",
    response_implied="Replay her own stated intent beside her prompt",
    detectable_from=DetectableFrom.PAIRED_SPOKEN_RECORD,
    paired=PairedDimension(
        description=(
            "Any dimension present in the spoken record and absent from the prompt"
        ),
        dimension_ids=tuple(d.id for d in rubric.DIMENSIONS),
        dynamic=True,
    ),
    cite=Cite("sec:diagnose", "tab:taxonomy row 3"),
)

BLIND_ACCEPTANCE = FailureCategory(
    id=Category.BLIND_ACCEPTANCE,
    name="Blind acceptance",
    student_did="Treated the first output as final",
    derived_from="Iteration Awareness dimension",
    response_implied="Ask what she would change if she could ask again",
    detectable_from=DetectableFrom.SESSION_HISTORY,
    paired=PairedDimension(
        description="Iteration Awareness",
        dimension_ids=(rubric.ITERATION_AWARENESS.id,),
    ),
    cite=Cite("sec:diagnose", "tab:taxonomy row 4"),
)

UNDIAGNOSED_RETRY = FailureCategory(
    id=Category.UNDIAGNOSED_RETRY,
    name="Undiagnosed retry",
    student_did="Rejected and resubmitted without changing the diagnosis",
    derived_from="Mindless retry signal",
    response_implied="Require naming what was wrong before resubmission",
    detectable_from=DetectableFrom.SESSION_HISTORY,
    paired=PairedDimension(
        description="Iteration Awareness",
        dimension_ids=(rubric.ITERATION_AWARENESS.id,),
    ),
    cite=Cite("sec:diagnose", "tab:taxonomy row 5"),
)

DELEGATED_JUDGMENT = FailureCategory(
    id=Category.DELEGATED_JUDGMENT,
    name="Delegated judgment",
    student_did="Asked the model to decide what good means",
    derived_from="Excessive deference signal; Reflection dimension",
    response_implied="Ask her to state the standard before the model answers",
    detectable_from=DetectableFrom.PROMPT_TEXT,
    paired=PairedDimension(
        description="Reflection",
        dimension_ids=(rubric.REFLECTION.id,),
    ),
    cite=Cite("sec:diagnose", "tab:taxonomy row 6"),
)

BORROWED_PHRASING = FailureCategory(
    id=Category.BORROWED_PHRASING,
    name="Borrowed phrasing",
    student_did="Submitted text pasted from a prior model output",
    derived_from="Copied AI content signal",
    response_implied="Ask which part she wrote and why it is there",
    detectable_from=DetectableFrom.SESSION_HISTORY,
    paired=PairedDimension(
        description="Context Clarity, scored on the words the student wrote herself",
        dimension_ids=(rubric.CONTEXT_CLARITY.id,),
    ),
    cite=Cite("sec:diagnose", "tab:taxonomy row 7"),
)


CATEGORIES: tuple[FailureCategory, ...] = (
    UNDER_SPECIFICATION,
    SOCIAL_FRAMING,
    INTENT_DRIFT,
    BLIND_ACCEPTANCE,
    UNDIAGNOSED_RETRY,
    DELEGATED_JUDGMENT,
    BORROWED_PHRASING,
)

BY_ID: dict[Category, FailureCategory] = {c.id: c for c in CATEGORIES}


def detectable_from_prompt_alone() -> tuple[FailureCategory, ...]:
    return tuple(
        c for c in CATEGORIES if c.detectable_from is DetectableFrom.PROMPT_TEXT
    )


def requires_spoken_record() -> tuple[FailureCategory, ...]:
    return tuple(
        c
        for c in CATEGORIES
        if c.detectable_from is DetectableFrom.PAIRED_SPOKEN_RECORD
    )


def requires_session_history() -> tuple[FailureCategory, ...]:
    return tuple(
        c for c in CATEGORIES if c.detectable_from is DetectableFrom.SESSION_HISTORY
    )


# ---------------------------------------------------------------------------
# The properties the thesis says to attack. Kept as data so the UI can show them.
# ---------------------------------------------------------------------------

OVERLAP_IS_MANDATORY = (
    "The categories overlap. Under specification and social framing co occur "
    "constantly. Build 2 established that rule based classification fails exactly "
    "on overlapping signatures, when a magnitude error was also a reciprocal error. "
    "The framework therefore requires the diagnosis to return several categories in "
    "rank order and never a single label, and requires the response layer to act on "
    "the top ranked failure only."
)

CIRCULARITY_WARNING = (
    "The derivation is close to circular, and the pairing in tab:improvement is "
    "close to true by construction. Every category was read off the instrument, so "
    "it would be surprising if the instrument could not detect the categories, and "
    "Layer 5 then checks improvement on the very dimension the category was derived "
    "from. The taxonomy cannot be validated by showing that the system can apply it."
)

#: sec:design. Two pairings are broad and five are narrow, so
#: "a system that treated them as equivalent would find more improvement after
#: some diagnoses than others for reasons that have nothing to do with the
#: student." The app records strictness alongside every improvement check rather
#: than pretending the checks are comparable.
STRICTNESS_WARNING = (
    "The pairings differ in strictness. Intent drift is broad, so three different "
    "revisions all count as improvement, which makes the check easy to pass. "
    "Reflection after delegated judgment is much harder to pass and rests on the "
    "least reliable dimension of the six."
)

CONTRAST_WITH_PRIOR_WORK = (
    "The nearest prior work is Tian and colleagues' taxonomy of prompt defects, and "
    "three differences matter. Theirs was built to be orthogonal, with categories "
    "deliberately non overlapping; this one is not. Theirs classifies the prompt; "
    "four of the seven categories here cannot be seen in the prompt at all. And "
    "theirs terminates in a mitigation a developer applies, while each category here "
    "terminates in a question a student is asked."
)
