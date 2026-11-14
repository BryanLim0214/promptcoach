"""The decomposition validator Layer 1 owns.

sec:elicit states the constraint and not the numbers:

    "When the layer decomposes a task for the student, the decomposition must
    itself be validated before display, against explicit length, checkpoint, and
    count rules. An unvalidated support becomes the overload it was meant to
    remove."

sec:build3 gives Build 3's rules, for Python: "if any step
exceeds 200 characters, lacks a checkpoint, or the decomposition runs to more
than seven steps, the system warns the instructor and serves a validated backup",
with a target of "three to five steps of two to three minutes, each with a goal,
instructions, and a checkpoint".

sec:design lists "Decomposition validator for prompting
tasks" as new work. The three rule *kinds* are the thesis's; the numbers are
Build 3's, and Chapter 12 grades the whole thing Transferred with the limit
"Prompting tasks may decompose differently."
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Choice, register

MAX_STEP_CHARACTERS = 200
MAX_STEPS = 7
MIN_STEPS = 3

RULES = register(
    Choice(
        id="decomposition.rules",
        value={
            "max_step_characters": MAX_STEP_CHARACTERS,
            "max_steps": MAX_STEPS,
            "min_steps": MIN_STEPS,
            "checkpoint_required": True,
        },
        thesis_says=(
            "sec:elicit requires length, checkpoint, and count rules and "
            "gives no values for prompting. sec:design lists the "
            "validator as new work."
        ),
        borrowed_from=(
            "sec:build3 - 200 characters, a checkpoint per step, no "
            "more than seven steps, targeting three to five. These are Python values."
        ),
        caveat=(
            "Chapter 12 grades validated decomposition Transferred: 'Prompting tasks "
            "may decompose differently.' A Python exercise decomposes along a "
            "sequence of operations; a prompting task decomposes along dimensions "
            "that are not obviously ordered at all."
        ),
    )
)


@dataclass(frozen=True)
class Step:
    goal: str
    instructions: str
    checkpoint: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    failures: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.ok


def validate(steps: list[Step]) -> ValidationResult:
    """Check a decomposition before it is shown, never after.

    An unvalidated support becomes the overload it was meant to remove, so a
    failing decomposition is not displayed with a warning - it is not displayed.
    """
    failures: list[str] = []

    if len(steps) > MAX_STEPS:
        failures.append(
            f"{len(steps)} steps exceeds the maximum of {MAX_STEPS}"
        )
    if len(steps) < MIN_STEPS:
        failures.append(
            f"{len(steps)} steps is below the minimum of {MIN_STEPS}"
        )

    for i, step in enumerate(steps, start=1):
        length = len(step.instructions)
        if length > MAX_STEP_CHARACTERS:
            failures.append(
                f"step {i} is {length} characters, over {MAX_STEP_CHARACTERS}"
            )
        if not step.checkpoint.strip():
            failures.append(f"step {i} has no checkpoint")
        if not step.goal.strip():
            failures.append(f"step {i} has no goal")

    return ValidationResult(ok=not failures, failures=tuple(failures))
