"""Difficulty gating: the dual condition, with values the thesis does not give.

sec:calibrate states the mechanism and not the numbers:

    "Gating requires both a rate condition and a streak condition, or the level
    oscillates."

sec:build2 tab:tiers gives concrete values, but for mathematics tiers
(Novice through Master), and Chapter 12 grades the whole mechanism Transferred
with the limit "Assumes an ordering that Build 2 inherited and prompting lacks."

So: the *structure* below is framework, and the *numbers* are borrowed. Both
conditions are required, because sec:build2 says requiring both
"is the detail that matters, because either alone makes the tier oscillate on a
single lucky or unlucky answer." That is the one thing here with a mechanism test.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..framework import progression, rubric
from .base import IMPLEMENTATION_CHOICE, Choice, register


@dataclass(frozen=True)
class GateRule:
    rate: float
    streak: int
    window: int


PROMOTION_RULE = GateRule(rate=0.85, streak=3, window=10)
DEMOTION_RULE = GateRule(rate=0.50, streak=2, window=10)


PROMOTION = register(
    Choice(
        id="gating.promotion",
        value={"rate": PROMOTION_RULE.rate, "streak": PROMOTION_RULE.streak,
               "window": PROMOTION_RULE.window},
        thesis_says=(
            "sec:calibrate requires both a rate condition and a streak "
            "condition and gives no values for prompting."
        ),
        borrowed_from=(
            "sec:build2 tab:tiers - 'Sustained accuracy above 85 percent "
            "and three consecutive correct', over a weighted ten most recent answers. "
            "These are mathematics values."
        ),
        caveat=(
            "Chapter 12 grades dual condition gating Transferred: 'Assumes an ordering "
            "that Build 2 inherited and prompting lacks.' The five bands are not a "
            "curriculum ordering and bands 4-5 sit on a different axis entirely."
        ),
    )
)

DEMOTION = register(
    Choice(
        id="gating.demotion",
        value={"rate": DEMOTION_RULE.rate, "streak": DEMOTION_RULE.streak,
               "window": DEMOTION_RULE.window},
        thesis_says="Same passage; no demotion values are given for prompting.",
        borrowed_from=(
            "sec:build2 tab:tiers - 'Accuracy below 50 percent and two "
            "consecutive incorrect'."
        ),
        caveat=(
            "Demoting across the 3-4 join is not a difficulty decrease, because the "
            "axes are not commensurable. `may_cross_join` is False for that reason."
        ),
    )
)

#: The progression's two halves measure different things, so moving between them
#: on an accuracy rule would be asserting a comparison sec:calibrate explicitly refuses
#: to make. Band changes stay within an axis unless a caller asks otherwise.
MAY_CROSS_JOIN = register(
    Choice(
        id="gating.may_cross_axis_join",
        value=False,
        thesis_says=(
            "sec:calibrate - 'Nothing in the construction says a band 4 task "
            "is harder than a band 3 task; it says band 4 demands a different kind of "
            "work.'"
        ),
        borrowed_from="none - this follows from the thesis's own warning",
        caveat=(
            "This makes bands 4 and 5 unreachable by accuracy alone. A placement "
            "decision or an explicit move is required, which is the honest "
            "consequence of an ordering the thesis does not claim."
        ),
    )
)


#: What one attempt contributes to the rate and the streak. MathEduAI counted
#: right and wrong answers; a prompt gets six scores on a 1-4 scale and no right
#: answer, so the conversion is ours.
SUCCESS_THRESHOLD = 3
BAND_3_MIN_PLANNING = 3

SUCCESS = register(
    Choice(
        id="gating.success",
        value={
            "threshold": SUCCESS_THRESHOLD,
            "bands_1_2": "every planning dimension the task names scores >= 3",
            "band_3": (
                f"at least {BAND_3_MIN_PLANNING} of the four planning dimensions "
                "score >= 3"
            ),
            "bands_4_5": "at least one of the two evaluative dimensions scores >= 3",
            "unscored": "a dimension that could not be scored counts as below 3",
        },
        thesis_says=(
            "sec:calibrate requires a rate condition and a streak condition and "
            "does not say what counts as a success for either. Build 2's values "
            "count right and wrong answers; a prompt has six scores and no right "
            "answer."
        ),
        borrowed_from=(
            "none. The band requirements are tab:progression's (bands 1-2: the "
            "named planning dimensions; band 3: three or more, implied; bands 4-5: "
            "an evaluative dimension). The threshold 3 is the rubric's upper half."
        ),
        caveat=(
            "A success means the scorer gave the band's required dimensions 3 or "
            "more on that attempt; it is a model score, so the shared-priors threat "
            "applies. Bands 4 and 5 rest on the two least reliable dimensions. The "
            "rule does not read whether the coaching worked: an earlier version "
            "counted a success only when the paired dimension rose on a revision, "
            "which made a clean first attempt a failure."
        ),
    )
)

STREAK_UNIT = register(
    Choice(
        id="gating.streak_unit",
        value="each_layer_5_run",
        thesis_says=(
            "sec:calibrate gives no unit for the rate window or the streak. Build "
            "2's unit is one answered problem."
        ),
        borrowed_from="none",
        caveat=(
            "One outcome is recorded each time Layer 5 runs: on every scored "
            "revision, whether or not the help cycle stays open (policy "
            "escalation.cycle), and on a first attempt with nothing to diagnose. "
            "The window and the streak "
            "therefore count attempts and revisions, not distinct tasks. With two "
            "tasks per band in this placeholder bank, a streak of three can only be "
            "reached by revising or repeating a task, so a promotion here says "
            "something about one or two tasks, not about the band."
        ),
    )
)


def required_dimensions(band: int, named: tuple[str, ...]) -> tuple[tuple[str, ...], int]:
    """(candidate dimension ids, how many must reach the threshold)."""
    if band in (1, 2):
        return tuple(named), len(named)
    if band == 3:
        return tuple(d.id for d in rubric.PLANNING_DIMENSIONS), BAND_3_MIN_PLANNING
    return (rubric.ITERATION_AWARENESS.id, rubric.REFLECTION.id), 1


def attempt_succeeded(band: int, named: tuple[str, ...], scores: dict | None) -> bool:
    """The `gating.success` rule. `scores` maps dimension id -> DimensionScore."""
    if not scores:
        return False
    candidates, needed = required_dimensions(band, named)
    if needed <= 0:
        return False
    met = 0
    for dim_id in candidates:
        s = scores.get(dim_id)
        value = getattr(s, "value", None)
        if value is not None and value >= SUCCESS_THRESHOLD:
            met += 1
    return met >= needed


def _rate(outcomes: tuple[bool, ...], window: int) -> float:
    recent = outcomes[-window:]
    if not recent:
        return 0.0
    return sum(1 for o in recent if o) / len(recent)


def _trailing_streak(outcomes: tuple[bool, ...], value: bool) -> int:
    n = 0
    for o in reversed(outcomes):
        if o is value:
            n += 1
        else:
            break
    return n


@dataclass(frozen=True)
class GateDecision:
    direction: int  # -1 demote, 0 hold, +1 promote
    reason: str
    rate: float
    streak: int
    rate_condition_met: bool
    streak_condition_met: bool


def evaluate(outcomes: tuple[bool, ...]) -> GateDecision:
    """Both conditions or neither.

    Returning the two conditions separately is not decoration: the mechanism test
    asserts that satisfying one alone never moves the band, which is the property
    sec:build2 calls the detail that matters.
    """
    up_rate = _rate(outcomes, PROMOTION_RULE.window)
    up_streak = _trailing_streak(outcomes, True)
    up_rate_ok = up_rate > PROMOTION_RULE.rate
    up_streak_ok = up_streak >= PROMOTION_RULE.streak

    if up_rate_ok and up_streak_ok:
        return GateDecision(
            direction=1,
            reason=(
                f"accuracy {up_rate:.0%} over the last {PROMOTION_RULE.window} is "
                f"above {PROMOTION_RULE.rate:.0%} and the last {up_streak} were "
                "correct; both conditions met"
            ),
            rate=up_rate,
            streak=up_streak,
            rate_condition_met=True,
            streak_condition_met=True,
        )

    down_rate = _rate(outcomes, DEMOTION_RULE.window)
    down_streak = _trailing_streak(outcomes, False)
    down_rate_ok = down_rate < DEMOTION_RULE.rate and len(outcomes) >= 2
    down_streak_ok = down_streak >= DEMOTION_RULE.streak

    if down_rate_ok and down_streak_ok:
        return GateDecision(
            direction=-1,
            reason=(
                f"accuracy {down_rate:.0%} is below {DEMOTION_RULE.rate:.0%} and the "
                f"last {down_streak} were not resolved; both conditions met"
            ),
            rate=down_rate,
            streak=down_streak,
            rate_condition_met=True,
            streak_condition_met=True,
        )

    if up_rate_ok and not up_streak_ok:
        reason = (
            f"accuracy {up_rate:.0%} clears the rate condition but the trailing "
            f"streak is {up_streak}, short of {PROMOTION_RULE.streak}; a single "
            "condition does not move the band"
        )
    elif up_streak_ok and not up_rate_ok:
        reason = (
            f"the last {up_streak} were correct but accuracy over the window is "
            f"{up_rate:.0%}, short of {PROMOTION_RULE.rate:.0%}; a single condition "
            "does not move the band"
        )
    else:
        reason = (
            f"accuracy {up_rate:.0%} with a trailing streak of {up_streak}; neither "
            "condition met"
        )

    return GateDecision(
        direction=0,
        reason=reason,
        rate=up_rate,
        streak=up_streak,
        rate_condition_met=up_rate_ok,
        streak_condition_met=up_streak_ok,
    )


def apply(band: int, decision: GateDecision) -> tuple[int, bool, str]:
    """Return (new_band, crossed_join, reason)."""
    if decision.direction == 0:
        return band, False, decision.reason

    target = band + decision.direction
    target = max(progression.MIN_BAND, min(progression.MAX_BAND, target))

    if target == band:
        return band, False, decision.reason + "; already at the edge of the progression"

    if progression.crosses_join(band, target) and not MAY_CROSS_JOIN.value:
        return (
            band,
            False,
            decision.reason
            + "; held at the axis join, because bands 3 and 4 sit on orderings the "
            "thesis does not claim are comparable",
        )

    return target, progression.crosses_join(band, target), decision.reason
