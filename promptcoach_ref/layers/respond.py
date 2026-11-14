"""Layer 4 - Respond.

    "The layer returns help that is graduated, targeted, and constrained."
    - sec:respond

    "Requirement passed downstream: the level issued, and whether the student's
    next attempt improved on the dimension that Table 7 pairs with the diagnosed
    category."
    - sec:respond

The whole layer exists to enforce one line, sec:respond:

    "Every level of the ladder is specified by what the student must still
    supply, not by how much help she receives, and no level supplies a missing
    element on her behalf. Guidance may narrow the search space and may not close
    it."

`validate()` below is that sentence as code. It is deliberately category-aware
and task-aware: a check that only counted words or looked for a question mark
would pass a level 1 response that handed over the missing audience, which is the
exact failure the boundary exists to prevent. sec:respond is explicit that "the
constraint lives in code, not in the model's instructions", so none of this is
delegated to a system prompt.

When generation fails validation, the template floor is served - and the floor is
validated too. A safe path that is not itself safe is not a safe path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..engines.base import ComposeRequest, Engine, EngineError
from ..engines.deterministic import (
    _dimension_evidence,
    dimensions_present,
    template_floor,
)
from ..framework import ladder, rubric
from ..framework.contracts import RespondInput, RespondOutput
from ..framework.taxonomy import BY_ID as TAXONOMY, Category
from ..policy import classifier, escalation

# The per-level sentence budget. It lives in policy/ because the thesis states
# no length for a response, and a bare dict here would not have said so.
from ..policy.response import MAX_MOVES

#: Phrases that hand the student a finished artifact rather than a direction.
HANDOVER = re.compile(
    r"(here'?s (a|your) (better|revised|improved|new) prompt|"
    r"try (typing|writing|asking) this|copy this|use this prompt|"
    r"your prompt should (say|read|be)|rewrite it as|"
    r"^\s*[\"“].{40,}[\"”]\s*$)",
    re.I | re.M,
)

QUESTION = re.compile(r"\?\s*$")
SLOT = re.compile(r"(‹[^›]*›|_{3,}|\[[^\]]*\])")
CONTRAST = re.compile(r"\bA\.\s.+\bB\.\s", re.S)
STUDENT_AUTHORSHIP = re.compile(
    r"(write a new prompt|write your own|revise (your|it)|then send it|"
    r"say which is better|explain (which|why)|in your own words)",
    re.I,
)


def _strip_scaffolding(text: str) -> str:
    """Remove what the interface contributes, leaving what the response asserts.

    A dimension's own name, an empty slot, and the student's own prompt echoed
    back are all scaffolding. None of them supplies a missing element, and
    treating them as if they did would make the ladder unable to climb.
    """
    probe = SLOT.sub(" ", text)
    for dim in rubric.DIMENSIONS:
        probe = re.sub(re.escape(dim.name), " ", probe, flags=re.I)
    return probe


def count_moves(text: str) -> int:
    """Sentences that ask or assert, ignoring the example scaffolding.

    Level 3 and 4 show the student her own prompt back; those lines are material
    to look at, not additional instructions, so they do not count against the
    budget.
    """
    body = "\n".join(
        line
        for line in text.splitlines()
        if not line.strip().startswith(("A.", "B.", "    ", "‹"))
    )
    return len([s for s in re.split(r"[.?!]+", body) if s.strip()])


@dataclass(frozen=True)
class Validation:
    ok: bool
    reason: str = ""


def validate(
    text: str,
    *,
    level: int,
    category: Category,
    protected_judgment: str,
    missing_from_prompt: tuple[str, ...],
    stated_by_student: tuple[str, ...] = (),
) -> Validation:
    """The authorship boundary, checked against this category and this task.

    `stated_by_student` is the dimensions she covered out loud and left out of
    the prompt. It is not a convenience. sec:respond forbids a level from supplying a
    missing element **on her behalf**, and something she said herself a minute
    ago is not on her behalf - replaying it is the entire mechanism intent drift
    calls for. sec:design's own model response is "you said out loud who this was for
    and how long it should be, and neither made it into what you typed", which
    an implementation without this exemption rejects as a violation.

    That was not a hypothetical. Every generated response on the worked example
    was refused and the template floor served in its place, so the live model
    was doing the specified thing and being silently overruled for it.

    The exemption is per dimension rather than per phrase because she and the
    model will not use the same words: she says "she's like seven", the model
    says "a seven-year-old". Matching strings there would refuse a paraphrase of
    her own sentence. The cost is that a response may elaborate slightly within
    a dimension she raised; the move budget bounds how far, and the dimensions
    she never mentioned are still closed.
    """
    if not text.strip():
        return Validation(False, "empty response")

    moves = count_moves(text)
    if moves > MAX_MOVES[level]:
        return Validation(
            False, f"{moves} moves exceeds the level {level} budget of {MAX_MOVES[level]}"
        )

    if HANDOVER.search(text):
        return Validation(
            False,
            "prohibited disclosure: the response hands over a prompt rather than "
            "narrowing the search space",
        )

    # The category-aware half. If a dimension is missing from the student's
    # prompt and the response supplies it in usable form, the response has
    # written that part of the prompt for her.
    #
    # Naming the dimension is not supplying it - that is precisely what level 2
    # is defined to do, "names the dimension at fault without saying what to
    # add". So the dimension names and the empty slot markers come out before
    # the check runs, or every level 2 and 3 response would fail against its own
    # specification.
    if level < ladder.TERMINAL_LEVEL:
        probe = _strip_scaffolding(text)
        for dim_id in missing_from_prompt:
            # She raised it herself. Handing it back is a replay, not a supply.
            if dim_id in stated_by_student:
                continue
            present, span = _dimension_evidence(dim_id, probe)
            if not present:
                continue
            name = rubric.BY_ID[dim_id].name
            return Validation(
                False,
                f"supplies {name} on the student's behalf ({span!r}); guidance "
                "may narrow the search space and may not close it",
            )

    # The task-aware half.
    if protected_judgment:
        stem = protected_judgment.split()[:3]
        if stem and all(w.lower() in text.lower() for w in stem):
            if not STUDENT_AUTHORSHIP.search(text):
                return Validation(
                    False,
                    f"appears to make the protected decision ({protected_judgment!r}) "
                    "without returning it to the student",
                )

    if level == 1 and not QUESTION.search(text.strip()):
        return Validation(False, "a level 1 response must end in a question")

    if level == 2:
        named = any(d.name.lower() in text.lower() for d in rubric.DIMENSIONS)
        if not named:
            return Validation(
                False, "a level 2 response must name the dimension at fault"
            )

    if level == 3 and not SLOT.search(text):
        return Validation(
            False, "a level 3 response must leave a slot for the student to fill"
        )

    if level == ladder.TERMINAL_LEVEL:
        if not CONTRAST.search(text):
            return Validation(
                False, "the terminal level must present a worked contrast"
            )
        if not STUDENT_AUTHORSHIP.search(text):
            return Validation(
                False,
                "the terminal level must still require the student to produce and "
                "explain",
            )

    return Validation(True)


@dataclass
class RespondLayer:
    READS: tuple[str, ...] = ("elicit", "measure", "diagnose")

    def __init__(self, engine: Engine, selection_mode: str | None = None) -> None:
        self.engine = engine
        self.selection_mode = selection_mode or classifier.SELECTION_MODE.value
        if self.selection_mode not in classifier.SELECTION_MODES:
            raise ValueError(f"unknown selection mode: {self.selection_mode}")

    def run(self, data: RespondInput, *, protected_judgment: str = "") -> RespondOutput:
        # Respond may not reclassify. The target arrives from Layer 3 and leaves
        # unchanged; choosing differently here would make the diagnosis decorative.
        target = data.target

        state = escalation.EscalationState(
            levels_issued=data.levels_already_issued,
            # Consecutive attempts with this top-ranked category, counted by the
            # session over first attempts and revisions alike. Not the number
            # of responses already issued, which climbed only on repeated first
            # attempts and never across revisions.
            consecutive_unresolved=data.consecutive_same_top,
            student_asked_for_help="asked_for_help" in data.escalation_signals,
            paired_dimension_is_evaluative=escalation.paired_with_evaluative_only(
                TAXONOMY[target].paired.dimension_ids
            ),
            prompt_text_unchanged=escalation.same_prompt_text(
                data.record.composed_text, data.previous_composed_text
            ),
        )
        escalate, why = escalation.should_escalate(state)
        level = (
            ladder.next_level(state.current_level)
            if escalate
            else (state.current_level or ladder.FIRST_LEVEL)
        )

        weakest = self._weakest(data)
        # Inserted text is not hers (component 24). A dimension that only an
        # inserted chip supplies is still missing from what she wrote, and the
        # prompt shown back to her at levels 3 and 4 is her own words only.
        hers = data.record.composed_text
        in_prompt = dimensions_present(hers)
        in_intent = dimensions_present(data.record.stated_intent)

        missing = tuple(
            d.id for d in rubric.PLANNING_DIMENSIONS if d.id not in in_prompt
        )
        # What she had and lost - ordered the way she said it, not the way the
        # rubric lists it. sec:design reads "who this was for and how long it should
        # be" because that is the order the words left her mouth; replaying them
        # in rubric order would make her own sentence sound like a form.
        dropped = _in_spoken_order(
            tuple(d.id for d in rubric.DIMENSIONS if d.id in in_intent - in_prompt),
            data.record.stated_intent,
        )

        request = ComposeRequest(
            level=level,
            category=target,
            prompt_text=hers,
            stated_intent=data.record.stated_intent,
            weakest_dimension_id=weakest,
            protected_judgment=protected_judgment,
            missing_from_prompt=missing,
            dropped_from_intent=dropped,
        )

        used_floor = False
        reason = why
        text: str | None = None

        try:
            text = self.engine.compose(request)
        except EngineError as exc:
            reason += f"; generation failed ({exc})"
            text = None

        if text:
            check = validate(
                text,
                level=level,
                category=target,
                protected_judgment=protected_judgment,
                missing_from_prompt=missing,
                stated_by_student=dropped,
            )
            if not check.ok:
                reason += f"; generated response rejected - {check.reason}"
                text = None

        if not text:
            used_floor = True
            text = template_floor(request)
            check = validate(
                text,
                level=level,
                category=target,
                protected_judgment=protected_judgment,
                missing_from_prompt=missing,
                stated_by_student=dropped,
            )
            if not check.ok:
                # The specified safe path must itself be safe.
                raise AssertionError(
                    f"template floor failed its own validation at level {level} "
                    f"for {target.value}: {check.reason}"
                )

        return RespondOutput(
            level=level,
            target=target,
            text=text,
            expected_action=_expected_action(level),
            used_template_floor=used_floor,
            selection_reason=reason,
        )

    def _weakest(self, data: RespondInput) -> str:
        """Which dimension the response points at.

        In `diagnosis` mode this is the dimension tab:improvement pairs with the
        diagnosed category. In `weakest_dimension` mode it is simply the lowest
        score, ignoring the diagnosis - which is the comparison F4 needs.
        """
        if self.selection_mode == "weakest_dimension":
            scored = [
                (s.value, k) for k, s in data.scores.items() if s.value is not None
            ]
            return min(scored)[1] if scored else rubric.CONTEXT_CLARITY.id

        paired = TAXONOMY[data.target].paired
        candidates = [
            d for d in paired.dimension_ids if d in data.scores
        ] or [rubric.CONTEXT_CLARITY.id]
        scored = [
            (data.scores[d].value or rubric.RUBRIC_MAX, d)
            for d in candidates
            if d in data.scores
        ]
        return min(scored)[1] if scored else candidates[0]


def _in_spoken_order(dimension_ids: tuple[str, ...], intent: str) -> tuple[str, ...]:
    """Sort dimensions by where their evidence sits in what she said."""
    haystack = intent.lower()

    def position(dim_id: str) -> int:
        _, span = _dimension_evidence(dim_id, intent)
        if not span:
            return len(haystack)
        found = haystack.find(span.lower())
        return found if found >= 0 else len(haystack)

    return tuple(sorted(dimension_ids, key=position))


def _expected_action(level: int) -> str:
    return {
        1: "Answer the question, then send a revised prompt.",
        2: "Look at the named part of your prompt, then send a revision.",
        3: "Fill the slot in your own words, then send a revision.",
        4: "Say which is better and why, then write a new prompt of your own.",
    }[level]
