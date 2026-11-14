"""Layer 5's difficulty progression: five bands on two axes.

Transcribed from sec:framework tab:progression. Caption, verbatim:

    "Proposed difficulty progression for prompting tasks. Bands 1 to 3 are
    ordered by how many planning dimensions the task requires unprompted. Bands
    4 and 5 both require evaluative dimensions, and are ordered by whether the
    student can see an output while she evaluates."

The single most important fact in this module is that the ordering is NOT one
scale. sec:calibrate:

    "The two axes are not commensurable. Nothing in the construction says a band
    4 task is harder than a band 3 task; it says band 4 demands a different kind
    of work. The ordering across the join is the weakest link in the progression,
    and Chapter 12 treats the two halves as separately refutable for that reason."

`AXIS_JOIN` marks where. The UI must render a break there rather than a smooth
1-to-5 scale, and the falsifiability tests keep band performance on either side
of the join separable so F3 can actually be run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .grades import Cite, FIVE_BAND_PROGRESSION, Grade


class Axis(str, Enum):
    """The two orderings the progression lays end to end."""

    #: Bands 1-3: how many of the four planning dimensions the student must
    #: supply without being told.
    PLANNING_DIMENSION_COUNT = "planning_dimension_count"
    #: Bands 4-5: both require the two evaluative dimensions; what separates
    #: them is whether an output is visible at the moment she evaluates.
    EVALUATIVE_OUTPUT_VISIBILITY = "evaluative_output_visibility"


@dataclass(frozen=True)
class Band:
    number: int
    axis: Axis
    requires: str
    example: str
    cite: Cite
    #: Bands 1-2 name the dimensions in the task; band 3 implies them through a
    #: scenario. That explicitness change is part of what separates 2 from 3, in
    #: addition to the count.
    dimensions_named_in_task: bool | None = None

    @property
    def grade(self) -> Grade:
        return FIVE_BAND_PROGRESSION.grade



BAND_1 = Band(
    number=1,
    axis=Axis.PLANNING_DIMENSION_COUNT,
    requires="One planning dimension, named in the task",
    example="Ask for something at a stated reading level",
    dimensions_named_in_task=True,
    cite=Cite("sec:calibrate", "tab:progression row 1"),
)

BAND_2 = Band(
    number=2,
    axis=Axis.PLANNING_DIMENSION_COUNT,
    requires="Two planning dimensions, named",
    example="Reading level and length",
    dimensions_named_in_task=True,
    cite=Cite("sec:calibrate", "tab:progression row 2"),
)

BAND_3 = Band(
    number=3,
    axis=Axis.PLANNING_DIMENSION_COUNT,
    requires="Three or more, implied by a scenario and not named",
    example="Audience, format, and purpose inferred from the situation",
    dimensions_named_in_task=False,
    cite=Cite("sec:calibrate", "tab:progression row 3"),
)

BAND_4 = Band(
    number=4,
    axis=Axis.EVALUATIVE_OUTPUT_VISIBILITY,
    requires="An evaluative dimension, with an output in front of her",
    example="A follow up that repairs a specific weakness in a response she has read",
    cite=Cite("sec:calibrate", "tab:progression row 4"),
)

BAND_5 = Band(
    number=5,
    axis=Axis.EVALUATIVE_OUTPUT_VISIBILITY,
    requires="An evaluative dimension, with no output to look at",
    example="The standard for a good answer, stated before the model responds",
    cite=Cite("sec:calibrate", "tab:progression row 5"),
)


BANDS: tuple[Band, ...] = (BAND_1, BAND_2, BAND_3, BAND_4, BAND_5)
BY_NUMBER: dict[int, Band] = {b.number: b for b in BANDS}

MIN_BAND = BAND_1.number
MAX_BAND = BAND_5.number

#: The join. Bands below it are ordered by one axis, bands at or above it by
#: another, and the thesis does not claim the two can be compared.
AXIS_JOIN = (BAND_3.number, BAND_4.number)


AXES_NOT_COMMENSURABLE = (
    "The two axes are not commensurable. Nothing in the construction says a band 4 "
    "task is harder than a band 3 task; it says band 4 demands a different kind of "
    "work. The ordering across the join is the weakest link in the progression."
)

BAND_1_RESTS_ON_ARGUMENT = (
    "Band 1 rests on argument rather than data: setting it properly needs a base "
    "rate for how many middle schoolers already supply one named dimension "
    "unprompted, which no dataset in this document supplies and which a short "
    "placement pretest would settle."
)

WHY_4_AND_5_SPLIT = (
    "Band 4 gives her an output: she reads a response and repairs a specific "
    "weakness in it. Band 5 does not: she has to say what a good answer would look "
    "like before the model has produced anything. Judging text you can see is easier "
    "than specifying a standard in advance, and that is the prediction the band order "
    "makes and the one an implementation would test."
)


def crosses_join(from_band: int, to_band: int) -> bool:
    """True when a move steps over the 3-4 boundary in either direction.

    Layer 5 records this on every band change so that F3's third sub-test - "if
    band 4 is easier than band 3, the two axes cannot be laid end to end" - has
    the data it needs.
    """
    low, high = AXIS_JOIN
    return (from_band <= low < to_band) or (to_band <= low < from_band)


def axis_of(band: int) -> Axis:
    return BY_NUMBER[band].axis


def same_axis(a: int, b: int) -> bool:
    return axis_of(a) is axis_of(b)
