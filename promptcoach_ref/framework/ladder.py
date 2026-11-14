"""Layer 4's response ladder: four levels, adapted from Build 3.

Transcribed from sec:framework tab:ladder. Caption: "The response ladder
proposed for prompt engineering, adapted from Build 3."

The levels are numbered 1-4 and the thesis gives them no names. They are not
named here either; inventing "hint", "cue", "scaffold", "worked example" would
import a vocabulary the manuscript does not use.

The governing constraint is sec:respond, and it is the strictest normative statement
in the document:

    "Every level of the ladder below is therefore specified by what the student
    must still supply, not by how much help she receives, and no level supplies a
    missing element on her behalf. Guidance may narrow the search space and may
    not close it."
"""

from __future__ import annotations

from dataclasses import dataclass

from .grades import (
    Cite,
    GRADUATED_LADDER,
    Grade,
    TEMPLATE_FLOOR,
    WORKED_CONTRAST_TERMINAL,
)


@dataclass(frozen=True)
class Level:
    number: int
    gives: str
    student_still_does: str
    cite: Cite
    #: Level 4 is graded separately from the ladder as a whole, because the
    #: worked contrast is a substitution the thesis flags as its most exposed
    #: single claim.
    grade: Grade = GRADUATED_LADDER.grade


LEVEL_1 = Level(
    number=1,
    gives="One question on the top ranked failure",
    student_still_does="Diagnoses and revises unaided",
    cite=Cite("sec:respond", "tab:ladder row 1"),
)

LEVEL_2 = Level(
    number=2,
    gives="Names the dimension at fault without saying what to add",
    student_still_does="Decides what to add and revises",
    cite=Cite("sec:respond", "tab:ladder row 2"),
)

LEVEL_3 = Level(
    number=3,
    gives="Shows her own prompt with the weak dimension marked",
    student_still_does="Supplies the missing element",
    cite=Cite("sec:respond", "tab:ladder row 3"),
)

LEVEL_4 = Level(
    number=4,
    gives=(
        "Worked contrast: two prompts differing on that dimension, with both outputs"
    ),
    student_still_does="States which is better and why, then revises her own",
    cite=Cite("sec:respond", "tab:ladder row 4"),
    grade=WORKED_CONTRAST_TERMINAL.grade,
)


LEVELS: tuple[Level, ...] = (LEVEL_1, LEVEL_2, LEVEL_3, LEVEL_4)
BY_NUMBER: dict[int, Level] = {lv.number: lv for lv in LEVELS}

FIRST_LEVEL = LEVEL_1.number
TERMINAL_LEVEL = LEVEL_4.number


# ---------------------------------------------------------------------------
# The authorship boundary
# ---------------------------------------------------------------------------

AUTHORSHIP_BOUNDARY = (
    "Scaffolding and authorship are separated by a line that is easy to cross "
    "without noticing: a scaffold that supplies the missing element has written the "
    "prompt, and the student has learned to recognize a good prompt rather than to "
    "write one. Guidance may narrow the search space and may not close it."
)

LEVEL_4_EXPOSURE = (
    "PyPal's level four shows the correct solution. There is no correct prompt to "
    "show. The framework's answer is that the terminal level presents a worked "
    "contrast in place of an answer. It also gives up something PyPal's level four "
    "had: a student stuck on a Python exercise at level four leaves with a working "
    "program, and a student at the terminal level here leaves with a comparison she "
    "must still convert into a revision, which is more work at the point where she "
    "has the least patience for it. Whether that substitution holds the student is "
    "the framework's most exposed single claim."
)

#: sec:respond. The constraint lives in code, not in the model's
#: instructions - which is why validate_response() in layers/respond.py is a
#: deterministic check over generated text, not a line in a system prompt.
TEMPLATE_FLOOR_RULE = (
    "A template floor sits beneath every generated response, matched to the "
    "diagnosed failure, and is served whenever the model call fails or its output "
    "violates the constraints. The constraint lives in code, not in the model's "
    "instructions."
)

TEMPLATE_FLOOR_COMPONENT = TEMPLATE_FLOOR

#: sec:respond. Reporting all six dimensions is a report card, not
#: coaching.
SINGLE_TARGET_RULE = (
    "The system addresses the top ranked failure only. Reporting all six dimensions "
    "is a report card, not coaching."
)

#: sec:build3 - why the ladder does not simply withhold.
WHY_NOT_WITHHOLD = (
    "A system that never gives the answer to a student stuck for ten minutes is not "
    "coaching, it is withholding. The commitment is that the student's hands stay on "
    "the keyboard at every level, not that help is rationed."
)


def next_level(current: int | None) -> int:
    """Escalate by exactly one rung, never past the terminal level.

    A ladder that can skip is not graduated, and sec:respond specifies help that
    "climbs an ordered ladder, not a single level of directness".
    """
    if current is None:
        return FIRST_LEVEL
    return min(TERMINAL_LEVEL, current + 1)


def is_terminal(level: int) -> bool:
    return level >= TERMINAL_LEVEL
