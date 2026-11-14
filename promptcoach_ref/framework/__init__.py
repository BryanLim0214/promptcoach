"""The thesis, as code.

Everything in this package is transcribed from the manuscript. Every constant
carries a `Cite` to a section label, and every graded component carries a
mechanism `Grade` and a `NeedBasis`. Nothing here invents
a value, a threshold, or a name that the thesis does not state.

Anything an implementation needs but the thesis leaves open lives in
`promptcoach_ref.policy` instead, where each value carries the passage proving it
is open, the provenance of the number chosen, and the caveat that goes with it.

The split is the point. A reader can diff this package against Chapter 10 line by
line; anything they disagree with in `policy` is openly ours.
"""

from . import (
    classroom,
    commitments,
    contracts,
    grades,
    ladder,
    progression,
    revision,
    rubric,
    sentinel,
    taxonomy,
)

__all__ = [
    "classroom",
    "commitments",
    "contracts",
    "grades",
    "ladder",
    "progression",
    "revision",
    "rubric",
    "sentinel",
    "taxonomy",
]

#: sec:design. Stated on import because it governs every use of everything
#: below it.
STANDING_DISCLAIMER = (
    "The reference implementation demonstrates that the five layers fit together "
    "without contradiction, that each layer's output is sufficient for the next "
    "layer's input, and that the specification is implementable. It has not been "
    "used with students, and no claim made by running it is a claim about "
    "learning or performance."
)

#: sec:intro and sec:threats. The single most important sentence for anyone
#: reading a number this software displays.
NO_STUDENTS = (
    "No student has used the framework. The user studies used two games "
    "built before it, and their outcomes are self-report. The three builds "
    "involved no students at all: their numbers come from hand-built benchmark "
    "items, automated test harnesses, or simulated learner profiles. The "
    "reference implementation exists and has not been used with students."
)
