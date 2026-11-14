"""Same-task revision with a stated reason (sec:elicit, component 21).

The student's attempt cycle in sec:framework ends with "Revise (the same task,
with a short stated reason)". The component table states it as a rule:
"Same-task revision with a stated reason, before a new task".

Two rules follow, and both are stated here as the thesis states them:

1. A revision of the same task needs a non-empty stated reason before it is
   scored. Without one it is not scored; Layer 1 asks for the reason instead.
2. A new task is held until one reasoned revision of the current task exists,
   unless the policy exit applies.

What the thesis leaves open - the minimum length a reason must have, and when
the hold is lifted without a reasoned revision - lives in `policy/revision.py`.
Nothing here imports it: the numbers arrive as arguments.

Why the rule exists (R3, sec:requirements): neither classroom game let a student
revise her own prompt. PicPrompt's players had one turn as Prompter; Promptemon's
picked chips per battle. The component is Argued: it has never been tested, it
could lower engagement, and the reason she types may be perfunctory. F7 is the
test that would show it does nothing, so the requirement must be switchable.
"""

from __future__ import annotations

from .grades import SAME_TASK_REVISION_WITH_REASON, Cite

COMPONENT = SAME_TASK_REVISION_WITH_REASON
CITE = Cite("sec:elicit", "component 21; the attempt cycle in sec:framework")

#: The framework's own floor: "a non-empty stated reason". Policy may raise it,
#: never lower it below one character of non-whitespace.
MIN_REASON_CHARS_FLOOR = 1

ASK_FOR_REASON = (
    "This is a new version of the same prompt. Before it is scored, say in a "
    "sentence why you changed it."
)

HOLD_MESSAGE = (
    "Before moving on, revise this prompt once and say why you changed it."
)

#: F7 (sec:falsify), verbatim from the spec: the result that would show this
#: component does nothing.
F7 = (
    "Requiring a reasoned revision produces no larger change between first and "
    "revised prompt scores than not requiring it."
)


def reason_is_stated(reason: str | None, min_chars: int = MIN_REASON_CHARS_FLOOR) -> bool:
    """True when the reason has at least `min_chars` non-whitespace characters."""
    floor = max(MIN_REASON_CHARS_FLOOR, min_chars)
    if reason is None:
        return False
    return len("".join(reason.split())) >= floor


def revision_may_be_scored(
    *,
    is_revision: bool,
    reason: str | None,
    required: bool,
    min_chars: int = MIN_REASON_CHARS_FLOOR,
) -> bool:
    """Rule 1. A first attempt is always scorable; a revision needs a reason
    while the requirement is on."""
    if not is_revision or not required:
        return True
    return reason_is_stated(reason, min_chars)


def new_task_held(
    *,
    reasoned_revisions_on_task: int,
    required: bool,
    exit_applies: bool,
) -> bool:
    """Rule 2. Held until one reasoned revision exists, unless the policy exit
    applies or the requirement is switched off."""
    if not required or exit_applies:
        return False
    return reasoned_revisions_on_task < 1
