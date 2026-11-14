"""When help climbs a rung, and when it does not.

sec:respond, component 16: escalation on observable conditions - repeated failed
attempts and explicit requests for help. The framework dropped inactivity as a
trigger: a long pause before a prompt may be planning, not struggle, and an
implementation that read deliberation as frustration would help hardest exactly
the students who are thinking.

sec:build3 gives Build 3's triggers - PyPal moves up a level when the student
says "I'm stuck", after three errors in a row, or after three minutes without
activity - and the component is graded Transferred with the limit "The
thresholds were set for a task with a correct answer." The two that survive are
carried here; the third is recorded as removed.

One more rule narrows the repeated-attempt trigger. sec:measure attaches lower
confidence to the two evaluative dimensions and does not raise the level of help
on their basis alone. Three of the seven diagnoses (blind acceptance,
undiagnosed retry, delegated judgment) are paired with exactly one of those two
dimensions, so for them "the target persisted" would be read off the scores the
framework says not to escalate on. For those diagnoses help moves up only when
she asks, or when her new attempt leaves the prompt text unchanged - a fact that
needs no score at all. See `EVALUATIVE_PAIRING`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Choice, register

#: How many consecutive attempts on one task must have the same top-ranked
#: category before help moves up a rung. Counted over attempts, root or
#: revision; the attempt being answered counts. 2 means: the category ranked
#: first now was also ranked first on the attempt before, so help moves up one
#: rung on every attempt where the problem persists.
CONSECUTIVE_UNRESOLVED = 2

CONSECUTIVE_TRIGGER = register(
    Choice(
        id="escalation.consecutive_unresolved",
        value=CONSECUTIVE_UNRESOLVED,
        thesis_says=(
            "sec:respond requires escalation on observable conditions and "
            "names no thresholds for prompting."
        ),
        borrowed_from=(
            "sec:build3 - 'three consecutive errors', for Python "
            "exercises. Adapted, not copied: see the caveat."
        ),
        caveat=(
            "Chapter 12: 'The thresholds were set for a task with a correct answer.' A "
            "prompting attempt has no error state, so this counts consecutive "
            "attempts on one task (first attempts and revisions alike) whose "
            "top-ranked category is the same, which is a weaker signal than a "
            "failing test. The count includes the attempt being answered, so at 2 "
            "help moves up one rung on each attempt where the same category is "
            "ranked first again: a first attempt and three revisions reach level 4. "
            "This implementation first used 3, counted as help responses already "
            "issued; under that count a revision closed the cycle and help never "
            "rose above level 1 in the student's session. At 3 under the present "
            "count, level 4 would need a first attempt and four revisions."
        ),
    )
)

#: When a help cycle (one task, one top-ranked category) stays open and when it
#: closes. sec:respond specifies help that climbs across attempts; it does not
#: say what one cycle is.
CYCLE_RULE = register(
    Choice(
        id="escalation.cycle",
        value={
            "a_cycle_is": "the help given on one task for one top-ranked category",
            "stays_open_on_a_revision_when": [
                "the revision's top-ranked category is the cycle's category",
                "the paired dimension did not improve (Layer 5's paired delta is "
                "missing or not above 0)",
                "level 4 has not been issued",
            ],
            "closes_when": [
                "a revision improves the paired dimension",
                "level 4 has been issued (the next attempt closes it; level 4 is "
                "never repeated)",
                "the top-ranked category changes, or nothing is diagnosed",
                "she moves to another task",
            ],
            "a_revision_opens_a_new_cycle": "only when she asks for more help",
            "a_first_attempt_opens_a_new_cycle": "whenever no cycle for its "
            "top-ranked category is open",
            "unscored_attempts": "neither extend nor break the count (Layer 1 "
            "asked for something, or Layer 2 could not score)",
        },
        thesis_says=(
            "sec:respond: help 'climbs an ordered ladder', escalating on repeated "
            "failed attempts and explicit requests; sec:design: 'The student "
            "revises. Layer 5 records whether the dimension paired with that "
            "failure improved.' Neither says what one cycle of help is or when it "
            "ends."
        ),
        borrowed_from="none",
        caveat=(
            "A revision that improves the paired dimension closes the cycle even if "
            "the same category is still ranked first, so a student who makes slow "
            "progress keeps getting first-rung help. For the three diagnoses paired "
            "with an evaluative dimension, closing reads the evaluative score; "
            "raising the level never does (escalation.evaluative_pairing)."
        ),
    )
)

INACTIVITY_REMOVED = register(
    Choice(
        id="escalation.inactivity",
        value="removed",
        thesis_says=(
            "sec:respond, component 16, keeps escalation on repeated failed "
            "attempts and explicit help requests and drops inactivity as a trigger."
        ),
        borrowed_from=(
            "sec:build3 - 'three minutes of inactivity'. This implementation "
            "first carried it switched off; it is now absent."
        ),
        caveat=(
            "A long pause before submitting a prompt may be planning. Elapsed time "
            "is not read by any escalation rule."
        ),
    )
)

FRUSTRATION_TRIGGER = register(
    Choice(
        id="escalation.expressed_frustration_only",
        value=True,
        thesis_says="Build 3 escalates when the student says 'I'm stuck'.",
        borrowed_from="sec:build3",
        caveat=(
            "Only an explicit request or explicit statement counts. Inferring "
            "frustration from timing is exactly what sec:calibrate warns against, so it is "
            "not inferred here."
        ),
    )
)

#: sec:framework specifies no de-escalation rule and no stop condition
#: after level 4. Both choices below are ours.
RESET_ON_NEW_TASK = register(
    Choice(
        id="escalation.reset_scope",
        value="task_cycle",
        thesis_says=(
            "The thesis does not specify whether the level resets between attempts, "
            "tasks, or sessions."
        ),
        borrowed_from="none",
        caveat=(
            "Resetting per task cycle means a student who needed level 4 on one task "
            "starts the next at level 1. The alternative - carrying the level across "
            "tasks - would let one hard task set the help level for an easy one."
        ),
    )
)

AFTER_TERMINAL = register(
    Choice(
        id="escalation.after_terminal",
        value="close_cycle_and_record_unresolved",
        thesis_says=(
            "The thesis states no stop condition. Level 4 is terminal only because it "
            "is the last row of tab:ladder."
        ),
        borrowed_from="none",
        caveat=(
            "The cycle closes and names the category left unresolved rather than "
            "repeating level 4. Repeating would violate nothing stated, but it would "
            "leave a student at the level sec:build3 says is already "
            "'more work at the point where she has the least patience for it'."
        ),
    )
)


EVALUATIVE_PAIRING = register(
    Choice(
        id="escalation.evaluative_pairing",
        value={
            "applies_when_paired_dimension_is": ["iteration_awareness", "reflection"],
            "escalate_on": ["explicit_help_request", "prompt_text_unchanged"],
            "unchanged_means": (
                "the composed text of this attempt equals the composed text of the "
                "previous attempt in the same task cycle, after collapsing "
                "whitespace and ignoring letter case"
            ),
        },
        thesis_says=(
            "sec:measure attaches lower confidence to Iteration Awareness and "
            "Reflection and does not raise the level of help on their basis alone, "
            "while tab:improvement pairs blind acceptance and undiagnosed retry with "
            "Iteration Awareness and delegated judgment with Reflection. Without a "
            "rule, the repeated-attempt trigger would escalate on exactly those "
            "scores. The thesis does not say what counts as an unchanged prompt."
        ),
        borrowed_from=(
            "none. The help-request trigger is Build 3's ('I'm stuck', "
            "sec:build3); the unchanged-text test is ours."
        ),
        caveat=(
            "For these three diagnoses the repeated-attempt count is not used. A "
            "student who keeps making small, unhelpful edits stays at the same level "
            "until she asks; a one-character edit defeats the unchanged-text test. "
            "This trades some help for not acting on the two least reliable scores. "
            "It does not affect the other four diagnoses."
        ),
    )
)

#: The dimension ids the rule above applies to. Kept as data, not re-derived,
#: so the Choice's value and the code cannot drift apart.
EVALUATIVE_DIMENSION_IDS: frozenset[str] = frozenset(
    EVALUATIVE_PAIRING.value["applies_when_paired_dimension_is"]
)


def same_prompt_text(a: str | None, b: str | None) -> bool:
    """The unchanged-text test: equal after collapsing whitespace and case."""
    if a is None or b is None:
        return False
    return " ".join(a.split()).lower() == " ".join(b.split()).lower()


def paired_with_evaluative_only(paired_dimension_ids: tuple[str, ...]) -> bool:
    """True when every dimension the diagnosis is paired with is evaluative."""
    return bool(paired_dimension_ids) and all(
        d in EVALUATIVE_DIMENSION_IDS for d in paired_dimension_ids
    )


@dataclass(frozen=True)
class EscalationState:
    levels_issued: tuple[int, ...] = ()
    #: Consecutive attempts on this task, this one included, whose top-ranked
    #: category is the one being answered. Not the number of help responses.
    consecutive_unresolved: int = 0
    student_asked_for_help: bool = False
    #: The diagnosis is paired with Iteration Awareness or Reflection only.
    paired_dimension_is_evaluative: bool = False
    #: This attempt's text is the previous attempt's text (`same_prompt_text`).
    prompt_text_unchanged: bool = False

    @property
    def current_level(self) -> int | None:
        return max(self.levels_issued) if self.levels_issued else None


def should_escalate(state: EscalationState) -> tuple[bool, str]:
    """Observable conditions only. Nothing here reads elapsed time as affect."""
    if state.current_level is None:
        return False, "first help on this cycle is always the lowest level"

    if state.student_asked_for_help:
        return True, "the student asked for more help"

    if state.paired_dimension_is_evaluative:
        # The diagnosis is paired with an evaluative dimension. Do not read
        # "the target persisted" off those scores; only an unchanged prompt
        # (no score needed) or her own request moves help up.
        if state.prompt_text_unchanged:
            return True, (
                "the prompt text is unchanged from the previous attempt; the "
                "diagnosis is paired with an evaluative dimension, so this, not "
                "the score, is what moves help up"
            )
        return False, (
            "the diagnosis is paired with an evaluative dimension, whose scores "
            "the framework does not escalate on; help moves up only when she asks "
            "or when the prompt text is unchanged"
        )

    if state.consecutive_unresolved >= CONSECUTIVE_UNRESOLVED:
        return True, (
            f"the diagnosed target persisted across {state.consecutive_unresolved} "
            "consecutive attempts with the same top-ranked category"
        )

    return False, (
        "no observable escalation condition met; elapsed time alone does not "
        "escalate, because a pause before a prompt may be planning"
    )
