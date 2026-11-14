"""The open parts of the reasoned-revision rule.

`framework/revision.py` states the rule: a revision of the same task needs a
non-empty stated reason before it is scored, and a new task is held until one
reasoned revision exists unless a policy exit applies. The thesis does not say
how long a reason must be, when the hold lets go without one, or how to run the
F7 comparison. Those are here.
"""

from __future__ import annotations

from ..framework import revision as rule
from .base import Choice, register

REQUIRED = register(
    Choice(
        id="revision.required",
        value=True,
        thesis_says=(
            "sec:elicit, component 21, makes a reasoned same-task revision required "
            "before a new task. sec:falsify F7 asks whether requiring it produces a "
            "larger change between first and revised scores than not requiring it."
        ),
        borrowed_from="none",
        caveat=(
            "On by default because the framework requires it. It is a switch, not "
            "a constant, because F7 needs a control arm in which the requirement is "
            "off; a system that could only require it would make F7 unrunnable."
        ),
    )
)

MIN_REASON_CHARS = 10

MIN_REASON_LENGTH = register(
    Choice(
        id="revision.min_reason_chars",
        value=MIN_REASON_CHARS,
        thesis_says=(
            "The framework requires 'a short stated reason' and a non-empty one; it "
            "gives no minimum length."
        ),
        borrowed_from="none",
        caveat=(
            "Ten non-space characters rules out 'idk' and a single key, and admits "
            "'added who it is for'. Length is not quality: the component's own "
            "limit is that the reason may be perfunctory, and no length rule fixes "
            "that."
        ),
    )
)

EXIT_AFTER_ATTEMPTS = 4

GATE_EXIT = register(
    Choice(
        id="revision.gate_exit",
        value={"after_attempts_on_task": EXIT_AFTER_ATTEMPTS},
        thesis_says=(
            "The framework holds a new task 'unless policy exit applies' and does "
            "not say when the exit applies."
        ),
        borrowed_from=(
            "none. Set one above the escalation threshold (three unresolved "
            "attempts), so the ladder can climb before the hold lets go."
        ),
        caveat=(
            "Without an exit, a student who cannot or will not state a reason is "
            "trapped on one task. With one, the rule can be waited out. Every exit "
            "is recorded so an F7 analysis can count how often the hold was "
            "released without a reasoned revision."
        ),
    )
)


def min_chars() -> int:
    return max(rule.MIN_REASON_CHARS_FLOOR, int(MIN_REASON_LENGTH.value))


def exit_applies(attempts_on_task: int) -> bool:
    """The hold lets go after this many scored or unscored attempts on a task."""
    return attempts_on_task >= int(GATE_EXIT.value["after_attempts_on_task"])
