"""How long a response at each rung is allowed to be.

The thesis specifies what each level of the ladder *gives* and what the student
*must still do* (tab:ladder), and says nothing about length. It does not have to:
on paper a level is a description. In code it is a string, and a string with no
budget drifts - a level 1 "one question on the top ranked failure" becomes a
paragraph of encouragement with a question buried in it, which is a different
intervention wearing the same label.

So the budget is a check on fidelity, not on style. It is counted in *moves* -
sentences that ask or assert - because that is the unit tab:ladder is written in:
"one question" is one move; "names the dimension at fault" is one more.

The numbers rise with the rung because the specification does: level 1 is one
question, level 4 has to present a contrast, ask which is better, and hand the
protected judgment back.

Nothing in the thesis licenses these five values. They are ours.
"""

from __future__ import annotations

from .base import Choice, register

#: level number -> maximum moves. Level 1 is two rather than one so that a
#: question may be preceded by the observation that motivates it, which is how
#: sec:design's own model response is built: the threads named, then the question.
MAX_MOVES: dict[int, int] = {1: 2, 2: 3, 3: 4, 4: 6}

RESPONSE_LENGTH = register(
    Choice(
        id="response.max_moves_per_level",
        value=dict(MAX_MOVES),
        thesis_says=(
            "sec:framework tab:ladder specifies each level by what it gives "
            "and what the student must still supply, and states no length. "
            "Chapter 13 lists response templates per failure category as unbuilt."
        ),
        borrowed_from=(
            "none. Read off the arity of tab:ladder's own row text - 'one question' "
            "is one move, 'names the dimension at fault' is one more - and one move "
            "added at each rung for the observation that motivates the ask."
        ),
        caveat=(
            "A budget this small is a real constraint on the generated path, and it "
            "is the most frequent reason a live response is rejected in favour of "
            "the template floor. Loosening it would raise the generation rate and "
            "weaken the guarantee that a level is what tab:ladder says it is; there "
            "is no evidence here for where the right trade sits."
        ),
    )
)
