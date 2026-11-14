"""Layer 2's instrument: the six dimension rubric.

Transcribed from sec:build1 tab:dimensions. The scale is stated at
sec:build1 - "each on a scale from 1, no evidence, to 4, strong."

The planning/evaluative split at sec:build1 is load-bearing for
three separate things: the confidence rule in Layer 2, the difficulty bands in
Layer 5, and the ordering of bands 1-3 against 4-5. It is not cosmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .grades import (
    Cite,
    Grade,
    LOWER_CONFIDENCE_ON_EVALUATIVE,
    SIX_DIMENSION_RUBRIC,
)

RUBRIC_MIN = 1
RUBRIC_MAX = 4
#: sec:build1 calls 0.134 "4.5 percent of the three point span
#: between the scale's extremes". The span is 3, not 4. Chapter sec:method records
#: that the published GHTC paper divided by 4 in two places and that the correct
#: figures are 4.5 and 8.7 percent. Anything reporting a shift as a proportion
#: must divide by this.
RUBRIC_SPAN = RUBRIC_MAX - RUBRIC_MIN


class Kind(str, Enum):
    """sec:build1 - the dimensions derive from Flavell's
    decomposition, and two of them sit at the evaluative end."""

    PLANNING = "planning"
    EVALUATIVE = "evaluative"


@dataclass(frozen=True)
class Dimension:
    id: str
    name: str
    measures: str
    one_against_four: str
    kind: Kind
    #: Cross model agreement per dimension, sec:build1 tab:agreement.
    #: Point estimates on 30 items with no intervals - see RELIABILITY_CAVEAT.
    weighted_kappa: float
    exact_pct: float
    within_one_pct: float
    icc_2_2: float

    @property
    def is_evaluative(self) -> bool:
        return self.kind is Kind.EVALUATIVE


CONTEXT_CLARITY = Dimension(
    id="context_clarity",
    name="Context Clarity",
    measures="States the task, its purpose, and who is asking",
    one_against_four="Bare topic word against a stated task with a stated reason",
    kind=Kind.PLANNING,
    weighted_kappa=0.851,
    exact_pct=53.3,
    within_one_pct=100.0,
    icc_2_2=0.925,
)

SPECIFICITY = Dimension(
    id="specificity",
    name="Specificity",
    measures="Requests a format, length, or level of detail",
    one_against_four="No format named against explicit format, length, and depth",
    kind=Kind.PLANNING,
    weighted_kappa=0.967,
    exact_pct=90.0,
    within_one_pct=100.0,
    icc_2_2=0.988,
)

ITERATION_AWARENESS = Dimension(
    id="iteration_awareness",
    name="Iteration Awareness",
    measures="Readiness to follow up or refine",
    one_against_four="Treats the first response as final against planning a follow up",
    kind=Kind.EVALUATIVE,
    weighted_kappa=0.841,
    exact_pct=73.3,
    within_one_pct=90.0,
    icc_2_2=0.913,
)

AUDIENCE_AWARENESS = Dimension(
    id="audience_awareness",
    name="Audience Awareness",
    measures="Identifies who will read or use the output",
    one_against_four="No reader named against a named reader with a knowledge level",
    kind=Kind.PLANNING,
    weighted_kappa=0.886,
    exact_pct=70.0,
    within_one_pct=96.7,
    icc_2_2=0.943,
)

CONSTRAINT_SETTING = Dimension(
    id="constraint_setting",
    name="Constraint Setting",
    measures="Sets limits such as word count or reading level",
    one_against_four="No limits against multiple explicit limits",
    kind=Kind.PLANNING,
    weighted_kappa=0.916,
    exact_pct=73.3,
    within_one_pct=100.0,
    icc_2_2=0.956,
)

REFLECTION = Dimension(
    id="reflection",
    name="Reflection",
    measures="Considered what a good response would look like",
    one_against_four="No stated standard against a stated standard for judging",
    kind=Kind.EVALUATIVE,
    weighted_kappa=0.645,
    exact_pct=50.0,
    within_one_pct=80.0,
    icc_2_2=0.786,
)


#: Ordered as tab:dimensions orders them.
DIMENSIONS: tuple[Dimension, ...] = (
    CONTEXT_CLARITY,
    SPECIFICITY,
    ITERATION_AWARENESS,
    AUDIENCE_AWARENESS,
    CONSTRAINT_SETTING,
    REFLECTION,
)

BY_ID: dict[str, Dimension] = {d.id: d for d in DIMENSIONS}

PLANNING_DIMENSIONS: tuple[Dimension, ...] = tuple(
    d for d in DIMENSIONS if d.kind is Kind.PLANNING
)
EVALUATIVE_DIMENSIONS: tuple[Dimension, ...] = tuple(
    d for d in DIMENSIONS if d.kind is Kind.EVALUATIVE
)


# ---------------------------------------------------------------------------
# Overall reliability, sec:build1 tab:agreement bottom row
# ---------------------------------------------------------------------------

#: The headline figure. ICC(2,2) on the overall score across 30 paired cases.
OVERALL_ICC_2_2 = 0.976
OVERALL_PEARSON_R = 0.968
OVERALL_SPEARMAN_RHO = 0.970

#: tab:agreement gives "n/a" for the overall weighted kappa. There is no such
#: number in the manuscript; only the six per-dimension kappas exist. None is
#: computed here either.
OVERALL_WEIGHTED_KAPPA: None = None

#: sec:build1
MEAN_GRADER_GAP_POINTS = 0.26
SENTINEL_CROSS_MODEL_PEARSON = 0.749

#: sec:build1, the paraphrase protocol
PARAPHRASE_MEAN_ABSOLUTE_SHIFT = 0.134
PARAPHRASE_P95_SHIFT = 0.38
PARAPHRASE_MAX_SHIFT = 0.50

#: sec:build1, the five agent pipeline
LATENCY_MEAN_SECONDS = 5.7
LATENCY_P95_SECONDS = 8.6

RELIABILITY_CAVEAT = (
    "Every figure is a point estimate on 30 items, and none carries an interval. "
    "At this sample size the sampling error on a weighted kappa is substantial, so "
    "the ordering of the six dimensions is indicative rather than established and a "
    "dimension's placement relative to a Landis and Koch threshold should not be "
    "treated as a finding on its own."
)

#: sec:measure, component 2. Which evaluative dimension had the lowest agreement
#: depends on the grader pair, so the per-dimension kappas above (Proem's pair)
#: must never be read as "Reflection is the hardest dimension".
REPLICATION_IA_KAPPA = 0.404
WEAKEST_DEPENDS_ON_PAIR = (
    "The two evaluative dimensions had the lowest agreement in both grader pairs, "
    "but which one was lowest changed: Reflection (kappa 0.645) in Proem and "
    "Iteration Awareness (kappa 0.404) in the replication. These are AI-grader "
    "statistics; they say nothing about students."
)

#: sec:build1. For a system that acts on which dimension is
#: weakest rather than on an exact number, the within-one column is the
#: operationally relevant one - and it is why the framework attaches lower
#: confidence to Reflection instead of discarding it.
OPERATIONALLY_RELEVANT_COLUMN = "within_one_pct"

#: sec:threats. Surfaced wherever agreement is displayed.
SHARED_PRIOR_THREAT = (
    "Both graders learned what a good prompt looks like from largely the same "
    "public text. If that shared notion is wrong in some systematic way, the two "
    "models will agree at ICC 0.976 and both will be wrong together, and no amount "
    "of cross model checking will reveal it."
)

#: sec:method. Reliability is perishable, so the app
#: ships a revalidation command rather than treating these numbers as permanent.
RELIABILITY_EXPIRY = (
    "A reliability coefficient tied to two specific model versions expires when "
    "either is retired, so a system built to this framework needs a revalidation "
    "procedure rather than a one time certificate."
)

#: sec:measure. The third bar. This one is not cleared, and the UI
#: says so permanently rather than in a footnote.
THIRD_BAR_UNCLEARED = (
    "The third bar is agreement with a human rater, and this thesis does not clear "
    "it. Cross model agreement is therefore necessary and not sufficient: it "
    "eliminates one failure mode and leaves another standing."
)

RUBRIC_COMPONENT = SIX_DIMENSION_RUBRIC
CONFIDENCE_COMPONENT = LOWER_CONFIDENCE_ON_EVALUATIVE

CITE = Cite(
    "sec:build1", "tab:dimensions", "the six dimension rubric"
)


def is_evaluative(dimension_id: str) -> bool:
    """sec:measure makes this normative, not advisory: a system
    "should attach lower confidence to them and should not escalate on their
    basis alone"."""
    return BY_ID[dimension_id].is_evaluative
