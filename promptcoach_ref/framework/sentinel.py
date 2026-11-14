"""The OverRelianceSentinel: four signals, each rated 0 to 1.

Transcribed from sec:build1. Caption of the signal table: "The four
signals rated by the OverRelianceSentinel on a zero to one scale."

Each of the four is the derivation source for exactly one taxonomy category,
which is why the taxonomy's circularity warning matters: the categories were
read off these signals.

The routing rule at sec:build1 is normative and absolute:

    "Sentinel output goes to the student. It does not populate a teacher
    dashboard, generate an alert, or restrict what the student can do next. A
    system that monitors under served students on behalf of adults is a
    different artifact with a different politics regardless of how similar the
    code looks."

There is deliberately no function in this module that returns sentinel data to a
teacher-facing caller, and a rejection test asserts no such path exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from .grades import Cite, Grade, OVER_RELIANCE_SEPARABLE
from .taxonomy import Category

SIGNAL_MIN = 0.0
SIGNAL_MAX = 1.0


@dataclass(frozen=True)
class Signal:
    id: str
    name: str
    detects: str
    #: The taxonomy category this signal was the derivation source for.
    derives_category: Category
    cite: Cite



TRANSCRIPT_PROMPT_DISCONNECT = Signal(
    id="transcript_prompt_disconnect",
    name="Transcript prompt disconnect",
    detects="The student describes one intention aloud and types something generic",
    derives_category=Category.INTENT_DRIFT,
    cite=Cite("sec:build1", "tab:sentinel row 1"),
)

EXCESSIVE_DEFERENCE = Signal(
    id="excessive_deference",
    name="Excessive deference",
    detects="Judgment offloaded, as in asking the tool to just make it good",
    derives_category=Category.DELEGATED_JUDGMENT,
    cite=Cite("sec:build1", "tab:sentinel row 2"),
)

MINDLESS_RETRY = Signal(
    id="mindless_retry",
    name="Mindless retry",
    detects="A prior response rejected and resubmitted without diagnosis",
    derives_category=Category.UNDIAGNOSED_RETRY,
    cite=Cite("sec:build1", "tab:sentinel row 3"),
)

COPIED_AI_CONTENT = Signal(
    id="copied_ai_content",
    name="Copied AI content",
    detects="Phrasing pasted from a previous model output, not composed",
    derives_category=Category.BORROWED_PHRASING,
    cite=Cite("sec:build1", "tab:sentinel row 4"),
)


SIGNALS: tuple[Signal, ...] = (
    TRANSCRIPT_PROMPT_DISCONNECT,
    EXCESSIVE_DEFERENCE,
    MINDLESS_RETRY,
    COPIED_AI_CONTENT,
)

BY_ID: dict[str, Signal] = {s.id: s for s in SIGNALS}


# ---------------------------------------------------------------------------
# Reported results, sec:build1
# ---------------------------------------------------------------------------

HIGH_RISK_MEAN = 0.62
LOW_RISK_MEAN = 0.27
N_HIGH_RISK = 9
N_LOW_RISK = 21
MANN_WHITNEY_P = 3.75e-3
AUC = 0.81
CROSS_MODEL_PEARSON = 0.749

#: The replication: pooled over five runs of a new corpus (45 high-risk against
#: 105 low-risk scorings). Pooled, not an average of runs, and no pooled interval
#: was computed.
REPLICATION_AUC_POOLED = 0.882
REPLICATION_AUC_RUN_RANGE = (0.825, 0.929)

#: Print both, never as an improvement. The run-to-run range (0.103) is larger
#: than the gap between the two studies.
AUC_READING = (
    "The sentinel separated the researchers' risk labels in both studies: AUC "
    "0.81 in Proem (one run, 9 high-risk items) and 0.882 pooled over five runs "
    "in the replication, where single runs ranged from 0.825 to 0.929. The "
    "run-to-run range is larger than the gap between the two studies."
)

#: The detail the thesis says matters more than the aggregate.
ONE_SIGNAL_CARRIES_IT = (
    "Excessive deference fired on seven of the nine, which is the per signal detail "
    "that matters: the aggregate figure is carried by one signal, and a detector "
    "resting on one signal is a detector with one failure mode."
)

THIN_BASIS = (
    "Nine positives is also a thin basis for an area under the curve, so the figure "
    "should be read as a first indication that the construct is separable at all."
)

WHY_AGREEMENT_IS_LOWER = (
    "Sentinel agreement at 0.749 is materially lower, and that is expected: over "
    "reliance is a judgment about intent inferred from behavior, and more inter "
    "subjective than the surface features the six dimensions read."
)

#: sec:method. Discrimination is reported as area
#: under the curve, "which avoids committing to a threshold". The thesis names no
#: alerting threshold and neither does this module - see policy/confidence.py for
#: the implementation choice and its justification.
NO_THRESHOLD_COMMITTED = (
    "Discrimination is reported as area under the curve, which avoids committing to "
    "a threshold."
)

ROUTING_RULE = (
    "Sentinel output goes to the student. It does not populate a teacher dashboard, "
    "generate an alert, or restrict what the student can do next."
)

COMPONENT = OVER_RELIANCE_SEPARABLE
